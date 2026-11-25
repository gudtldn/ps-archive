"""문제 폴더 레이아웃, meta.json, 테스트 파일, 루트 Cargo.toml을 다룹니다.

problems/<1000번 단위 범위, 예: 01000-01999>/<solved.ac 키>/
    meta.json
    tests/1.in, tests/1.out, ...
    main.py, main.rs, ...
"""

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from solve.api import Problem

PROBLEMS_DIR = "problems"
BUCKET_SIZE = 1000
BUCKET_DIGITS = 5  # solved.ac 번호가 5자리라 이만큼 0을 채웁니다
META_FILE = "meta.json"
TESTS_DIR = "tests"
BUILD_DIR = ".build"
CARGO_FILE = "Cargo.toml"
RUST_EDITION = "2024"
RUST_EDITION_KEY = "rustEdition"  # meta.json에 둘 때만 기본 에디션 대신 사용
STATUS_SOLVING = "solving"
STATUS_SOLVED = "solved"
STATUSES = (STATUS_SOLVING, STATUS_SOLVED)


class ProblemNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class JudgeRef:
    oj: str
    id: str
    url: str


@dataclass(frozen=True)
class Meta:
    key: str
    problem_id: int
    sub_id: str
    title: str
    level: int
    tags: tuple[str, ...]
    judges: tuple[JudgeRef, ...]
    time_limit_sec: float | None = None
    memory_limit_mb: int | None = None
    status: str = STATUS_SOLVING
    # 모르는 키도 지우지 않고 그대로 다시 씁니다.
    extra: dict[str, Any] = field(default_factory=dict)

    def boj_id(self) -> str | None:
        return next((j.id for j in self.judges if j.oj == "boj"), None)

    def url(self) -> str:
        return self.judges[0].url if self.judges else ""


# 파이썬 필드 이름 -> meta.json 키 (solved.ac API와 같은 camelCase)
_JSON_KEYS = {
    "key": "key",
    "problem_id": "problemId",
    "sub_id": "subId",
    "title": "title",
    "level": "level",
    "tags": "tags",
    "judges": "judges",
    "time_limit_sec": "timeLimitSec",
    "memory_limit_mb": "memoryLimitMb",
    "status": "status",
}


def meta_to_json(meta: Meta) -> dict[str, Any]:
    data: dict[str, Any] = {json_key: getattr(meta, name) for name, json_key in _JSON_KEYS.items()}
    data["tags"] = list(meta.tags)
    data["judges"] = [{"oj": j.oj, "id": j.id, "url": j.url} for j in meta.judges]
    return data | meta.extra


def meta_from_json(raw: dict[str, Any]) -> Meta:
    values = {name: raw[json_key] for name, json_key in _JSON_KEYS.items() if json_key in raw}
    values["tags"] = tuple(raw.get("tags", []))
    values["judges"] = tuple(JudgeRef(**j) for j in raw.get("judges", []))
    extra = {k: v for k, v in raw.items() if k not in _JSON_KEYS.values()}
    return Meta(**values, extra=extra)


def meta_from_problem(problem: Problem, url_patterns: dict[str, str]) -> Meta:
    judges = tuple(
        JudgeRef(j.oj_id, j.problem_id, url_patterns.get(j.oj_id, "").format(problemId=j.problem_id))
        for j in problem.judge_ids
    )
    return Meta(problem.key, problem.problem_id, problem.sub_id, problem.title, problem.level, problem.tags, judges)


def refresh_meta(old: Meta, fresh: Meta) -> Meta:
    """solved.ac에서 받은 값으로 갱신하되, 로컬에서만 아는 값(제한·상태)은 유지합니다."""
    return replace(
        fresh,
        time_limit_sec=old.time_limit_sec,
        memory_limit_mb=old.memory_limit_mb,
        status=old.status,
        extra=old.extra,
    )


def problems_root(repo_root: Path) -> Path:
    return repo_root / PROBLEMS_DIR


def bucket_name(problem_id: int) -> str:
    """1000번 단위 범위 폴더 이름. 예: 1000 -> `01000-01999`.

    0을 채워야 GitHub과 탐색기의 문자열 정렬이 번호순과 같아집니다.
    """
    start = problem_id // BUCKET_SIZE * BUCKET_SIZE
    return f"{start:0{BUCKET_DIGITS}d}-{start + BUCKET_SIZE - 1:0{BUCKET_DIGITS}d}"


def problem_dir(repo_root: Path, problem_id: int, key: str) -> Path:
    return problems_root(repo_root) / bucket_name(problem_id) / key


def read_meta(directory: Path) -> Meta:
    return meta_from_json(json.loads((directory / META_FILE).read_text(encoding="utf-8")))


def write_lf(path: Path, text: str) -> None:
    """Windows에서도 줄바꿈을 LF로 씁니다. BOJ(Linux)와 같은 입력이 되도록 하기 위함입니다."""
    path.write_text(text, encoding="utf-8", newline="\n")


def write_meta(directory: Path, meta: Meta) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    text = json.dumps(meta_to_json(meta), ensure_ascii=False, indent=2)
    write_lf(directory / META_FILE, text + "\n")


def _sort_key(path: Path) -> tuple[int, str]:
    digits = "".join(ch for ch in path.name if ch.isdigit())
    return (int(digits) if digits else 0, path.name)


def iter_problem_dirs(repo_root: Path) -> list[Path]:
    root = problems_root(repo_root)
    if not root.exists():
        return []
    return sorted((p.parent for p in root.glob(f"*/*/{META_FILE}")), key=_sort_key)


def find_problem(repo_root: Path, ident: str) -> Path:
    """solved.ac 키(`1000`, `19917b`)로 먼저 찾고, 없으면 BOJ 번호로 찾습니다."""
    directories = iter_problem_dirs(repo_root)
    for directory in directories:
        if directory.name == ident:
            return directory
    for directory in directories:
        if read_meta(directory).boj_id() == ident:
            return directory
    raise ProblemNotFoundError(f"문제 {ident}를 찾을 수 없습니다. `solve new {ident}`로 먼저 만드세요.")


def read_tests(directory: Path) -> list[tuple[str, str, str]]:
    """(이름, 입력, 기대 출력) 목록을 번호 순으로 돌려줍니다. 짝이 없는 .in은 건너뜁니다."""
    tests_dir = directory / TESTS_DIR
    if not tests_dir.exists():
        return []
    cases = []
    for in_file in sorted(tests_dir.glob("*.in"), key=lambda p: _sort_key(p.with_suffix(""))):
        out_file = in_file.with_suffix(".out")
        if out_file.exists():
            cases.append((in_file.stem, in_file.read_text(encoding="utf-8"), out_file.read_text(encoding="utf-8")))
    return cases


def add_test(directory: Path, input_text: str, output_text: str) -> str:
    """다음 번호로 테스트를 추가하고 그 이름을 돌려줍니다."""
    tests_dir = directory / TESTS_DIR
    tests_dir.mkdir(parents=True, exist_ok=True)
    taken = [int(p.stem) for p in tests_dir.glob("*.in") if p.stem.isdigit()]
    name = str(max(taken, default=0) + 1)
    write_lf(tests_dir / f"{name}.in", input_text.rstrip("\n") + "\n")
    write_lf(tests_dir / f"{name}.out", output_text.rstrip("\n") + "\n")
    return name


def rust_bin_name(key: str) -> str:
    return f"p{key}"


def render_cargo_manifest(repo_root: Path) -> str:
    """problems/ 아래의 모든 main.rs를 바이너리로 등록한 루트 Cargo.toml 내용."""
    lines = [
        "# `solve`가 생성하는 파일입니다. 직접 고치면 덮어써집니다.",
        "[package]",
        'name = "ps-archive"',
        'version = "0.1.0"',
        f'edition = "{RUST_EDITION}"',
        "publish = false",
        "autobins = false",
        "",
    ]
    for directory in iter_problem_dirs(repo_root):
        if not (directory / "main.rs").exists():
            continue
        path = (directory / "main.rs").relative_to(repo_root).as_posix()
        lines += ["[[bin]]", f'name = "{rust_bin_name(directory.name)}"', f'path = "{path}"']
        # 예전 crate가 다른 에디션이었다면 그 에디션으로 빌드합니다 (2021 코드가 2024에서 깨지지 않게).
        edition = read_meta(directory).extra.get(RUST_EDITION_KEY)
        if edition and edition != RUST_EDITION:
            lines.append(f'edition = "{edition}"')
        lines.append("")
    return "\n".join(lines)


def sync_cargo_manifest(repo_root: Path) -> None:
    write_lf(repo_root / CARGO_FILE, render_cargo_manifest(repo_root))
