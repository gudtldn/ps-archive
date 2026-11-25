"""언어와 상관없이 tests/*.in을 실행하고 기대 출력과 비교합니다."""

import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from solve.langs import Language
from solve.layout import BUILD_DIR, read_tests, rust_bin_name

DEFAULT_TIME_LIMIT_SEC = 2.0
# 로컬 환경 차이와 Python 시작 시간을 감안해 넉넉하게 잡습니다.
TIMEOUT_MULTIPLIER = 5
MIN_TIMEOUT_SEC = 5.0


class Verdict(Enum):
    AC = "AC"
    WA = "WA"
    TLE = "TLE"
    RTE = "RTE"


class BuildError(Exception):
    """컴파일러가 없거나 빌드에 실패했을 때 발생합니다."""


class UnsupportedLanguageError(Exception):
    pass


@dataclass(frozen=True)
class CaseResult:
    name: str
    verdict: Verdict
    elapsed: float
    expected: str
    actual: str
    stderr: str


def normalize_output(text: str) -> str:
    """BOJ처럼 줄 끝 공백과 마지막 빈 줄은 무시하고 비교합니다."""
    lines = text.replace("\r\n", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).rstrip("\n")


def outputs_match(expected: str, actual: str) -> bool:
    return normalize_output(expected) == normalize_output(actual)


def timeout_for(time_limit_sec: float | None) -> float:
    return max(MIN_TIMEOUT_SEC, (time_limit_sec or DEFAULT_TIME_LIMIT_SEC) * TIMEOUT_MULTIPLIER)


def _placeholders(repo_root: Path, directory: Path, lang: Language) -> dict[str, str]:
    out_dir = repo_root / BUILD_DIR / directory.name / lang.ext
    return {
        "src": str(directory / lang.source_name),
        "out": str(out_dir),
        "bin": rust_bin_name(directory.name),
        "root": str(repo_root),
    }


def build(repo_root: Path, directory: Path, lang: Language) -> list[str]:
    """필요하면 빌드하고, 실행할 명령을 돌려줍니다."""
    if lang.run is None:
        raise UnsupportedLanguageError(lang.unsupported_reason or f"{lang.name}는 로컬 실행을 지원하지 않습니다")
    values = _placeholders(repo_root, directory, lang)
    if not Path(values["src"]).exists():
        raise BuildError(f"{lang.source_name}이(가) 없습니다.")
    if lang.build is not None:
        Path(values["out"]).mkdir(parents=True, exist_ok=True)
        command = lang.command(lang.build, **values)
        try:
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        except FileNotFoundError as error:
            raise BuildError(f"`{command[0]}`을(를) 찾을 수 없습니다. 설치 여부와 PATH를 확인하세요.") from error
        if result.returncode != 0:
            raise BuildError((result.stderr or result.stdout).strip())
    return lang.command(lang.run, **values)


def run_case(command: list[str], name: str, input_text: str, expected: str, timeout: float, cwd: Path) -> CaseResult:
    # 텍스트 모드는 Windows에서 \n을 \r\n으로 바꿔 보내므로, BOJ처럼 LF 그대로 보내려고 바이트로 다룹니다.
    stdin = input_text.replace("\r\n", "\n").encode("utf-8")
    started = time.perf_counter()
    try:
        result = subprocess.run(command, input=stdin, capture_output=True, timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired:
        return CaseResult(name, Verdict.TLE, timeout, expected, "", "")
    elapsed = time.perf_counter() - started
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")

    if result.returncode != 0:
        verdict = Verdict.RTE
    elif outputs_match(expected, stdout):
        verdict = Verdict.AC
    else:
        verdict = Verdict.WA
    return CaseResult(name, verdict, elapsed, expected, stdout, stderr)


def run_tests(repo_root: Path, directory: Path, lang: Language, time_limit_sec: float | None) -> list[CaseResult]:
    command = build(repo_root, directory, lang)
    timeout = timeout_for(time_limit_sec)
    return [
        run_case(command, name, input_text, expected, timeout, directory)
        for name, input_text, expected in read_tests(directory)
    ]
