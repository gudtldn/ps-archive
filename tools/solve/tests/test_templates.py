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


# 템플릿 하나만 OJ에 붙여넣는다고 보고, 외부 의존 없이 단일 파일로 빌드·실행되는지 확인합니다.
_RUST_BODY = """\
    let (n, k) = parse_line!(usize, i64);
    let a = parse_line!([i64]);
    assert_eq!(a.len(), n);
    let word = parse_line!(String);
    println!("{}", a.iter().sum::<i64>() * k);
    print!("{} ", word);
    println!();"""


@pytest.mark.skipif(shutil.which("rustc") is None, reason="rustc가 없습니다")
@pytest.mark.parametrize("edition", ["2018", "2021"])
def test_rust_template_parses_tuple_and_vec_lines(tmp_path: Path, edition: str) -> None:
    source = render_template(get_language("rs"), TITLE, URL)
    assert '    todo!("solve here");' in source
    src = tmp_path / "main.rs"
    src.write_text(source.replace('    todo!("solve here");', _RUST_BODY), encoding="utf-8")
    exe = tmp_path / "main"

    build = subprocess.run(
        ["rustc", "--edition", edition, "-O", "-o", str(exe), str(src)],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr

    run = subprocess.run([str(exe)], input="3 2\r\n1 2 3\r\nhello\r\n", capture_output=True, text=True)

    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == ["12", "hello "]


# u8/i8은 std::format에서 문자가 아니라 정수로 출력되는지도 같이 확인합니다.
_CPP_BODY = """\
    i32 n;
    u64 k;
    cin >> n >> k;
    u8 b = 200;
    i8 c = -5;
    usize len = static_cast<usize>(n);
    f64 half = static_cast<f64>(k) / 2.0;
    println("{} {} {} {} {}", static_cast<u64>(n) * k, b, c, len, half);"""


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++가 없습니다")
def test_cpp_template_builds_standalone_with_aliases_and_println(tmp_path: Path) -> None:
    lang = get_language("cpp")
    source = render_template(lang, TITLE, URL)
    assert "    // code here" in source
    src = tmp_path / "main.cpp"
    src.write_text(source.replace("    // code here", _CPP_BODY), encoding="utf-8")
    assert lang.build is not None and lang.run is not None

    build = subprocess.run(
        [*lang.command(lang.build, src=str(src), out=str(tmp_path)), "-Wall", "-Wextra", "-Werror"],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr

    run = subprocess.run(lang.command(lang.run, out=str(tmp_path)), input="3 10\n", capture_output=True, text=True)

    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == ["30 200 -5 3 5"]
