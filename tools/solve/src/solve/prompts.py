"""터미널에서 직접 고르게 하는 대화형 입력. questionary는 이 모듈에서만 다룹니다.

색은 rich로 찍는 나머지 출력과 맞춥니다: 완료·선택은 green, 제목은 bold, 보조 설명은 dim.
"""

import sys
from collections.abc import Callable, Sequence

import questionary

from solve.langs import LANGUAGES, Language, get_language

STYLE = questionary.Style(
    [
        ("qmark", "fg:ansigreen bold"),
        ("question", "bold"),
        ("instruction", "fg:ansibrightblack"),
        ("pointer", "fg:ansigreen bold"),
        ("highlighted", "bold"),
        ("selected", "fg:ansigreen"),
        ("answer", "fg:ansigreen"),
    ]
)
INSTRUCTION = "(↑↓ 이동 · 스페이스 선택 · 엔터 확정)"
# npm(inquirer) 메뉴와 같은 커서 모양입니다. 일부러 쓴 문자라 혼동 문자 경고를 끕니다.
POINTER = "❯"  # noqa: RUF001

AskLanguages = Callable[[Sequence[Language]], list[str] | None]


class NotInteractiveError(Exception):
    pass


class SelectionCancelled(Exception):
    pass


def language_title(language: Language) -> list[tuple[str, str]]:
    """메뉴 한 줄. 다음부터 바로 칠 수 있게 `-l` 짧은 이름을 흐리게 덧붙입니다."""
    return [("class:text", language.name), ("class:instruction", f"  -l {language.ext}")]


def _ask_checkbox(languages: Sequence[Language]) -> list[str] | None:
    question = questionary.checkbox(
        "언어를 고르세요",
        choices=[questionary.Choice(language_title(lang), value=lang.name) for lang in languages],
        validate=lambda picked: bool(picked) or "하나 이상 고르세요",
        instruction=INSTRUCTION,
        pointer=POINTER,
        style=STYLE,
    )
    # ask()는 Ctrl+C를 삼키고 영어 안내를 찍으므로, 직접 받아서 취소 메시지를 한국어로 통일합니다.
    try:
        return question.unsafe_ask()
    except KeyboardInterrupt:
        return None


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def choose_languages(interactive: bool, ask: AskLanguages = _ask_checkbox) -> tuple[Language, ...]:
    if not interactive:
        raise NotInteractiveError("언어를 고를 수 있는 터미널이 아닙니다. -l로 지정하세요 (예: -l rs, -l py,rs)")
    picked = ask(LANGUAGES)
    if not picked:
        raise SelectionCancelled("언어를 고르지 않아 취소했습니다")
    return tuple(get_language(name) for name in picked)
