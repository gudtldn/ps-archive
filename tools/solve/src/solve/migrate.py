"""예전 레이아웃(<BOJ 번호>/<언어>/...)을 problems/ 레이아웃으로 옮깁니다.

- tracked 파일은 `git mv`로 옮겨 히스토리를 유지합니다.
- 언어별 풀이는 main.<ext>로, 그 밖의 소스 파일은 원래 이름 그대로 옮깁니다.
- 예전 *_test.py에 있던 테스트 케이스는 tests/로 추출하고, 모두 추출되면 파일을 지웁니다.
- 문제마다 있던 Cargo.toml·Cargo.lock은 루트 Cargo.toml 하나로 대체합니다.
"""

import ast
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from solve.langs import language_for_file
from solve.layout import (
    RUST_EDITION_KEY,
    STATUS_SOLVED,
    STATUS_SOLVING,
    Meta,
    problem_dir,
    sync_cargo_manifest,
)
from solve.scaffold import add_new_tests, save_meta
from solve.scrape import ProblemPage, ScrapeError

JUNK_DIRS = {"target", ".vscode", ".idea", "__pycache__"}
JUNK_SUFFIXES = {".bat", ".gdb", ".exe", ".jar", ".o", ".pdb", ".class", ".kotlin_module"}
_EDITION = re.compile(r'^\s*edition\s*=\s*"(\d{4})"', re.MULTILINE)
CARGO_FILES = {"Cargo.toml", "Cargo.lock"}
SCRAPE_DELAY_SEC = 1.0  # BOJ에 부담을 주지 않도록 요청 사이에 쉽니다

_STRING_LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
_RUST_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "0": "\0"}


@dataclass(frozen=True)
class Move:
    source: Path
    target: Path
    tracked: bool


@dataclass
class ProblemPlan:
    legacy_dir: Path
    meta: Meta
    moves: list[Move] = field(default_factory=list)
    removals: list[Move] = field(default_factory=list)  # target은 쓰지 않고 source·tracked만 씁니다
    extracted: list[tuple[str, str]] = field(default_factory=list)
    kept_test_files: list[Path] = field(default_factory=list)
    rust_edition: str | None = None

    @property
    def status(self) -> str:
        return STATUS_SOLVED if any(m.tracked for m in self.moves) else STATUS_SOLVING


def _decode(literal: str, lang: str) -> str:
    if lang == "py":
        return ast.literal_eval(f'"{literal}"')
    return re.sub(r"\\(.)", lambda m: _RUST_ESCAPES.get(m.group(1), m.group(0)), literal)


def extract_cases(text: str, lang: str) -> tuple[list[tuple[str, str]], bool]:
    """예전 테스트 코드에서 (입력, 출력) 쌍을 뽑습니다. 두 번째 값은 모두 뽑았는지 여부입니다.

    테스트 함수 하나에 문자열 리터럴이 정확히 두 개(입력, 기대 출력)일 때만 케이스로 인정합니다.
    """
    marker = r"\n\s*def test_" if lang == "py" else r"#\[test\]"
    end = r"\nif __name__" if lang == "py" else r"\n}\n"
    cases: list[tuple[str, str]] = []
    complete = True
    for block in re.split(marker, text)[1:]:
        body = re.split(end, block, maxsplit=1)[0]
        literals = _STRING_LITERAL.findall(body)
        if len(literals) == 2:
            cases.append((_decode(literals[0], lang), _decode(literals[1], lang)))
        else:
            complete = False
    return cases, complete


def _tracked_files(repo_root: Path, directory: Path) -> set[Path]:
    output = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", directory.relative_to(repo_root).as_posix()],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {(repo_root / p).resolve() for p in output.split("\0") if p}


def plan_problem(repo_root: Path, legacy_dir: Path, meta: Meta) -> ProblemPlan:
    plan = ProblemPlan(legacy_dir, meta)
    target_dir = problem_dir(repo_root, meta.problem_id, meta.key)
    tracked = _tracked_files(repo_root, legacy_dir)
    boj = legacy_dir.name
    taken: set[str] = set()

    for path in sorted(p for p in legacy_dir.rglob("*") if p.is_file()):
        relative = path.relative_to(legacy_dir)
        is_tracked = path.resolve() in tracked
        if JUNK_DIRS & set(relative.parts) or path.suffix in JUNK_SUFFIXES:
            continue  # 빌드 산출물·에디터 설정은 마지막에 폴더째 지웁니다
        if path.name in CARGO_FILES:
            if path.name == "Cargo.toml" and (edition := _EDITION.search(path.read_text(encoding="utf-8"))):
                plan.rust_edition = edition.group(1)
            plan.removals.append(Move(path, path, is_tracked))
            continue
        if path.name.endswith("_test.py"):
            cases, complete = extract_cases(path.read_text(encoding="utf-8"), "py")
            plan.extracted += cases
            if complete and cases:
                plan.removals.append(Move(path, path, is_tracked))
            else:
                plan.kept_test_files.append(path)
                plan.moves.append(Move(path, target_dir / path.name, is_tracked))
            continue

        lang = language_for_file(path.name)
        if lang is not None and lang.ext == "rs":
            plan.extracted += extract_cases(path.read_text(encoding="utf-8"), "rs")[0]
        is_main = lang is not None and path.stem in (f"boj_{boj}", boj, "main") and lang.source_name not in taken
        name = lang.source_name if is_main else path.name
        if name in taken:
            name = f"{relative.parts[0]}_{path.name}"
        taken.add(name)
        plan.moves.append(Move(path, target_dir / name, is_tracked))
    return plan


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True)


def apply_plan(repo_root: Path, plan: ProblemPlan, page: ProblemPage | None) -> Path:
    meta = replace(plan.meta, status=plan.status)
    if plan.rust_edition:
        meta = replace(meta, extra={**meta.extra, RUST_EDITION_KEY: plan.rust_edition})
    directory = save_meta(repo_root, meta, page)
    if page is not None:
        add_new_tests(directory, [(s.input, s.output) for s in page.samples])
    add_new_tests(directory, plan.extracted)

    for move in plan.moves:
        move.target.parent.mkdir(parents=True, exist_ok=True)
        if move.tracked:
            _git(repo_root, "mv", str(move.source), str(move.target))
        else:
            shutil.move(move.source, move.target)
    for removal in plan.removals:
        if removal.tracked:
            _git(repo_root, "rm", "-q", str(removal.source))
        else:
            removal.source.unlink(missing_ok=True)
    shutil.rmtree(plan.legacy_dir, ignore_errors=True)
    return directory


def migrate(
    repo_root: Path,
    metas: dict[int, Meta],
    fetch_page: Callable[[str], ProblemPage],
    report: Callable[[str], None],
    dry_run: bool = False,
) -> list[ProblemPlan]:
    plans = []
    for boj_id, meta in metas.items():
        plan = plan_problem(repo_root, repo_root / str(boj_id), meta)
        if not plan.moves:
            # 소스 없이 빌드 결과물만 남은 폴더 등. 빈 문제를 만들지 않고 그대로 둡니다.
            report(f"{boj_id}: 옮길 소스 파일이 없어 건너뜁니다 (폴더는 그대로 둠)")
            continue
        plans.append(plan)
        moves = ", ".join(f"{m.source.relative_to(plan.legacy_dir).as_posix()}→{m.target.name}" for m in plan.moves)
        report(f"{boj_id} → {meta.key} [{plan.status}] {moves} | 추출 {len(plan.extracted)}개")
        for kept in plan.kept_test_files:
            report(f"  ! 테스트 일부를 추출하지 못해 {kept.name}을(를) 남깁니다")
        if dry_run:
            continue
        page = None
        try:
            page = fetch_page(meta.boj_id() or str(boj_id))
        except ScrapeError as error:
            report(f"  ! 예제를 가져오지 못했습니다: {error}")
        apply_plan(repo_root, plan, page)
        time.sleep(SCRAPE_DELAY_SEC)
    if not dry_run:
        sync_cargo_manifest(repo_root)
    return plans
