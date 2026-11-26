"""풀이 파일을 에디터로 엽니다."""

import os
import shlex
import shutil
import subprocess
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

EDITOR_ENV_VARS = ("SOLVE_EDITOR", "VISUAL", "EDITOR")
# -r: 새 창을 띄우지 않고 지금 열려 있는 창(보통 ps-archive 루트)에서 엽니다.
DEFAULT_EDITOR = "code -r"

Which = Callable[[str], str | None]
Runner = Callable[..., object]


class EditorError(Exception):
    pass


def _split_command(value: str) -> list[str]:
    # posix 모드는 Windows 경로의 역슬래시를 이스케이프로 먹어 버리므로 쓰지 않고, 따옴표만 직접 벗깁니다.
    return [token.strip("\"'") for token in shlex.split(value, posix=False)]


def should_open(flag: bool | None, interactive: bool) -> bool:
    """`--open`/`--no-open`을 줬으면 그대로 따르고, 안 줬으면 사람이 터미널 앞에 있을 때만 엽니다."""
    return interactive if flag is None else flag


def resolve_editor_command(env: Mapping[str, str]) -> list[str]:
    """SOLVE_EDITOR → VISUAL → EDITOR 순서로 처음 값이 있는 것을 쓰고, 없으면 VSCode를 씁니다."""
    for name in EDITOR_ENV_VARS:
        value = env.get(name, "").strip()
        if value:
            return _split_command(value)
    return _split_command(DEFAULT_EDITOR)


def open_in_editor(
    paths: Iterable[Path],
    env: Mapping[str, str] = os.environ,
    which: Which = shutil.which,
    run: Runner = subprocess.run,
) -> None:
    command = resolve_editor_command(env)
    # Windows의 `code`는 code.cmd라서 which로 실제 경로를 찾아야 실행됩니다.
    program = which(command[0])
    if program is None:
        raise EditorError(f"에디터 '{command[0]}'를 찾을 수 없습니다. SOLVE_EDITOR 환경 변수로 지정하세요.")
    # 터미널 에디터(vim 등)는 끝날 때까지 기다려야 셸과 화면이 엉키지 않습니다. `code`는 바로 돌아옵니다.
    try:
        run([program, *command[1:], *(str(p) for p in paths)], check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise EditorError(f"에디터를 실행하지 못했습니다: {error}") from error
