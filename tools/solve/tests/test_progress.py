from io import BytesIO, StringIO, TextIOWrapper

import pytest
from rich.console import Console

from solve.progress import step


def plain_console() -> tuple[Console, StringIO]:
    buffer = StringIO()
    return Console(file=buffer, force_terminal=False, width=80), buffer


def test_prints_check_line_with_elapsed_time_when_step_finishes() -> None:
    console, buffer = plain_console()
    with step(console, "태그 이름 받기") as current:
        current.update(1, 2)
        current.detail("1000")
        current.advance()
    assert "✓ 태그 이름 받기" in buffer.getvalue()
    assert buffer.getvalue().rstrip().endswith("s")


def test_failed_step_does_not_print_check_line() -> None:
    console, buffer = plain_console()
    with pytest.raises(RuntimeError), step(console, "메타데이터 갱신"):
        raise RuntimeError("boom")
    assert "✓" not in buffer.getvalue()


def test_falls_back_to_ascii_on_legacy_korean_console() -> None:
    raw = BytesIO()
    stream = TextIOWrapper(raw, encoding="cp949")
    console = Console(file=stream, force_terminal=True, color_system=None, width=80)
    with step(console, "태그 이름 받기"):
        pass  # cp949로 표현할 수 없는 스피너·체크 문자를 쓰면 여기서 UnicodeEncodeError가 납니다
    stream.flush()
    assert "v 태그 이름 받기" in raw.getvalue().decode("cp949")


def test_quiet_step_prints_nothing_on_finish() -> None:
    console, buffer = plain_console()
    with step(console, "테스트 실행", total=1, announce=False) as current:
        current.advance()
    assert buffer.getvalue().strip() == ""  # rich는 Live를 닫을 때 빈 줄을 남길 수 있습니다
