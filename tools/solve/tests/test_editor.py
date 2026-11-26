import subprocess
from pathlib import Path

import pytest

from solve.editor import EditorError, open_in_editor, resolve_editor_command


class RecordingRunner:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[list[str]] = []
        self.error = error

    def __call__(self, args: list[str], check: bool) -> None:
        self.calls.append(args)
        if self.error:
            raise self.error


def which_in(*known: str):
    return lambda name: f"/bin/{name}" if name in known else None


def test_defaults_to_vscode_reusing_window_when_no_env_is_set() -> None:
    assert resolve_editor_command({}) == ["code", "-r"]


def test_solve_editor_takes_priority_over_visual_and_editor() -> None:
    env = {"SOLVE_EDITOR": "nvim", "VISUAL": "vim", "EDITOR": "nano"}
    assert resolve_editor_command(env) == ["nvim"]


def test_falls_back_to_visual_then_editor_and_skips_blank_values() -> None:
    assert resolve_editor_command({"SOLVE_EDITOR": "  ", "VISUAL": "vim", "EDITOR": "nano"}) == ["vim"]
    assert resolve_editor_command({"EDITOR": "nano"}) == ["nano"]


def test_keeps_quoted_path_with_spaces_as_one_token() -> None:
    env = {"SOLVE_EDITOR": r'"C:\Program Files\Editor\ed.exe" --wait'}
    assert resolve_editor_command(env) == [r"C:\Program Files\Editor\ed.exe", "--wait"]


def test_runs_resolved_program_with_args_and_paths() -> None:
    runner = RecordingRunner()
    open_in_editor([Path("a/main.py"), Path("a/main.rs")], env={}, which=which_in("code"), run=runner)
    assert runner.calls == [["/bin/code", "-r", str(Path("a/main.py")), str(Path("a/main.rs"))]]


def test_raises_with_hint_when_editor_is_not_installed() -> None:
    with pytest.raises(EditorError, match="SOLVE_EDITOR"):
        open_in_editor([Path("main.py")], env={}, which=which_in(), run=RecordingRunner())


@pytest.mark.parametrize("error", [OSError("boom"), subprocess.CalledProcessError(1, "code")])
def test_wraps_launch_failures_in_editor_error(error: Exception) -> None:
    with pytest.raises(EditorError):
        open_in_editor([Path("main.py")], env={}, which=which_in("code"), run=RecordingRunner(error))
