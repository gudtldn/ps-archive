import shutil
import subprocess
from pathlib import Path

import pytest

from solve.langs import LANGUAGES, Language, get_language
from solve.templates import render_template

TITLE = "A+B"
URL = "https://example.com/problem/1000"


@pytest.mark.parametrize("lang", LANGUAGES, ids=lambda lang: lang.name)
def test_every_language_has_template(lang: Language) -> None:
    rendered = render_template(lang, TITLE, URL)

    assert TITLE in rendered
    assert URL in rendered
    assert "{{" not in rendered


@pytest.mark.skipif(shutil.which("rustc") is None, reason="rustc가 없습니다")
def test_rust_template_compiles_without_warnings(tmp_path: Path) -> None:
    src = tmp_path / "main.rs"
    src.write_text(render_template(get_language("rs"), TITLE, URL), encoding="utf-8")

    result = subprocess.run(
        ["rustc", "--edition", "2021", "-D", "warnings", "-o", str(tmp_path / "main"), str(src)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
