from collections.abc import Sequence

import pytest

from solve.langs import LANGUAGES, Language
from solve.prompts import NotInteractiveError, SelectionCancelled, choose_languages, language_title


def answering(picked: list[str] | None):
    def ask(languages: Sequence[Language]) -> list[str] | None:
        assert tuple(languages) == LANGUAGES
        return picked

    return ask


def test_returns_picked_languages_in_menu_order() -> None:
    langs = choose_languages(interactive=True, ask=answering(["python", "rust"]))
    assert [lang.name for lang in langs] == ["python", "rust"]


def test_refuses_to_prompt_without_terminal_and_hints_lang_option() -> None:
    with pytest.raises(NotInteractiveError, match="-l"):
        choose_languages(interactive=False, ask=answering(["rust"]))


@pytest.mark.parametrize("picked", [None, []])
def test_cancels_when_user_aborts_or_picks_nothing(picked: list[str] | None) -> None:
    with pytest.raises(SelectionCancelled):
        choose_languages(interactive=True, ask=answering(picked))


def test_menu_title_shows_name_and_short_option_for_lang_flag() -> None:
    rust = next(lang for lang in LANGUAGES if lang.name == "rust")
    assert "".join(text for _, text in language_title(rust)) == "rust  -l rs"
