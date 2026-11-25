"""오래 걸리는 작업의 진행 상황을 터미널에 보여 줍니다.

도메인 모듈(resolve, sync, runner)은 콜백만 받고, rich 진행 표시는 이 모듈에서만 다룹니다.
터미널이 아니면(파이프·리다이렉트) rich가 막대를 그리지 않으므로 완료 줄만 남습니다.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text

# 한국어 Windows 기본 콘솔(cp949)은 점자 스피너와 ✓를 표현하지 못해 출력 중에 예외가 납니다.
UNICODE_SPINNER, ASCII_SPINNER = "dots", "line"
UNICODE_CHECK, ASCII_CHECK = "✓", "v"


def _can_encode(console: Console, text: str) -> bool:
    try:
        text.encode(console.encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


class _CountColumn(ProgressColumn):
    """`3/17`처럼 표시합니다. 전체 개수를 모르는 단계에서는 비워 둡니다."""

    def render(self, task: Task) -> Text:
        if task.total is None:
            return Text("")
        return Text(f"{int(task.completed)}/{int(task.total)}", style="progress.download")


class Step:
    """진행 중인 단계 하나. `update`는 `(끝낸 수, 전체 수)` 콜백으로 그대로 넘길 수 있습니다."""

    def __init__(self, progress: Progress, task: TaskID) -> None:
        self._progress = progress
        self._task = task

    def update(self, done: int, total: int) -> None:
        self._progress.update(self._task, completed=done, total=total)

    def advance(self) -> None:
        self._progress.advance(self._task)

    def detail(self, text: str) -> None:
        """지금 처리 중인 대상(문제 번호 등)을 막대 옆에 보여 줍니다."""
        self._progress.update(self._task, detail=text)


@contextmanager
def step(console: Console, description: str, total: int | None = None, announce: bool = True) -> Iterator[Step]:
    """단계가 진행되는 동안 스피너·진행 막대를 보여 주고, 끝나면 막대를 지웁니다.

    `announce`가 참이면 성공했을 때 `✓ 설명 (걸린 시간)` 한 줄을 남깁니다. 예외가 나면 남기지 않습니다.
    단계 안에서 `console.print`한 내용은 막대 위에 차례로 쌓입니다.
    """
    started = time.perf_counter()
    unicode_ok = _can_encode(console, UNICODE_CHECK + "⠋")
    progress = Progress(
        SpinnerColumn(UNICODE_SPINNER if unicode_ok else ASCII_SPINNER),
        TextColumn("{task.description}"),
        BarColumn(),
        _CountColumn(),
        TextColumn("[dim]{task.fields[detail]}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )
    with progress:
        task = progress.add_task(description, total=total, detail="")
        yield Step(progress, task)
    if announce:
        check = UNICODE_CHECK if unicode_ok else ASCII_CHECK
        console.print(f"[green]{check}[/green] {description} [dim]{time.perf_counter() - started:.1f}s[/dim]")
