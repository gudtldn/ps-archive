from pathlib import Path

import pytest

from solve.api import JudgeId, Problem
from solve.langs import UnknownLanguageError, get_language, language_for_file, parse_languages
from solve.layout import (
    Meta,
    add_test,
    bucket_name,
    find_problem,
    meta_from_problem,
    problem_dir,
    read_meta,
    read_tests,
    render_cargo_manifest,
    write_meta,
)
from solve.runner import Verdict, outputs_match, run_tests
from solve.scaffold import add_new_tests, write_templates
from solve.scrape import ScrapeError, parse_problem_page

PATTERNS = {"boj": "https://www.acmicpc.net/problem/{problemId}"}


def page_html(samples: list[tuple[str, str]], limits: tuple[str, str] = ("2 초", "128 MB")) -> str:
    pres = "".join(
        f'<pre id="sample-input-{n}">{i}</pre><pre id="sample-output-{n}">{o}</pre>'
        for n, (i, o) in enumerate(samples, start=1)
    )
    return (
        '<span id="problem_title">T</span>'
        f'<table id="problem-info"><tbody><tr><td>{limits[0]}</td><td>{limits[1]}</td></tr></tbody></table>{pres}'
    )


def make_meta(key: str = "1000", problem_id: int = 1000, boj: str = "1000") -> Meta:
    problem = Problem(problem_id, key.removeprefix(str(problem_id)), "A+B", 1, ("math",), (JudgeId("boj", boj, ""),))
    return meta_from_problem(problem, PATTERNS)


class TestScrape:
    def test_parses_limits_and_normalizes_samples(self) -> None:
        page = parse_problem_page(page_html([("1 2  \r\n", "3\r\n\r\n")], ("0.5 초 (추가 시간 없음)", "256 MB")))
        assert page.time_limit_sec == 0.5
        assert page.memory_limit_mb == 256
        assert [(s.input, s.output) for s in page.samples] == [("1 2", "3")]

    def test_rejects_cloudflare_challenge(self) -> None:
        with pytest.raises(ScrapeError, match="Cloudflare"):
            parse_problem_page("<title>Just a moment...</title>")

    def test_rejects_changed_layout(self) -> None:
        with pytest.raises(ScrapeError, match="problem_title"):
            parse_problem_page("<html><body>new site</body></html>")


class TestLangs:
    def test_aliases_and_dedup(self) -> None:
        assert [lang.name for lang in parse_languages("py, rs,python,c++")] == ["python", "rust", "cpp"]

    def test_unknown_language(self) -> None:
        with pytest.raises(UnknownLanguageError):
            get_language("brainfuck")

    def test_language_for_file(self) -> None:
        assert language_for_file("boj_1000.asm").name == "asm"
        assert language_for_file("notes.txt") is None


class TestLayout:
    def test_bucket_and_directory(self, tmp_path: Path) -> None:
        assert bucket_name(999) == "0xxx"
        assert problem_dir(tmp_path, 19917, "19917b") == tmp_path / "problems" / "19xxx" / "19917b"

    def test_meta_round_trip_keeps_unknown_keys(self, tmp_path: Path) -> None:
        directory = tmp_path / "p"
        write_meta(directory, make_meta())
        raw = (directory / "meta.json").read_text(encoding="utf-8")
        assert '"problemId": 1000' in raw
        (directory / "meta.json").write_text(raw.replace('"status"', '"note": "x",\n  "status"'), encoding="utf-8")
        meta = read_meta(directory)
        assert meta.extra == {"note": "x"}
        assert meta.url() == "https://www.acmicpc.net/problem/1000"

    def test_find_problem_by_key_then_boj_number(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        target = problem_dir(tmp_path, 19759, "19759")
        write_meta(target, make_meta("19759", 19759, "28955"))
        assert find_problem(tmp_path, "19759") == target
        assert find_problem(tmp_path, "28955") == target

    def test_tests_are_numbered_and_sorted(self, tmp_path: Path) -> None:
        for n in range(1, 12):
            add_test(tmp_path, f"in{n}", f"out{n}")
        assert [name for name, _, _ in read_tests(tmp_path)][:3] == ["1", "2", "3"]
        assert read_tests(tmp_path)[-1] == ("11", "in11\n", "out11\n")

    def test_cargo_manifest_lists_rust_problems(self, tmp_path: Path) -> None:
        directory = problem_dir(tmp_path, 1000, "1000")
        write_meta(directory, make_meta())
        (directory / "main.rs").write_text("fn main() {}", encoding="utf-8")
        manifest = render_cargo_manifest(tmp_path)
        assert 'name = "p1000"' in manifest
        assert 'path = "problems/1xxx/1000/main.rs"' in manifest
        assert "autobins = false" in manifest


class TestScaffold:
    def test_add_new_tests_skips_duplicates(self, tmp_path: Path) -> None:
        add_test(tmp_path, "1 2", "3")
        assert add_new_tests(tmp_path, [("1 2\n", "3  "), ("5 5", "10")]) == ["2"]

    def test_templates_never_overwrite(self, tmp_path: Path) -> None:
        directory = problem_dir(tmp_path, 1000, "1000")
        write_meta(directory, make_meta())
        (directory / "main.py").write_text("print('mine')", encoding="utf-8")
        created = write_templates(tmp_path, directory, make_meta(), parse_languages("py,cpp"))
        assert [p.name for p in created] == ["main.cpp"]
        assert (directory / "main.py").read_text(encoding="utf-8") == "print('mine')"
        assert "https://www.acmicpc.net/problem/1000" in (directory / "main.cpp").read_text(encoding="utf-8")


class TestRunner:
    def test_outputs_match_ignores_trailing_whitespace(self) -> None:
        assert outputs_match("1 2\n3\n", "1 2   \r\n3\r\n\r\n")
        assert not outputs_match("1 2", "1  2")

    def test_sends_input_with_lf_only(self, tmp_path: Path) -> None:
        directory = problem_dir(tmp_path, 1000, "1000")
        write_meta(directory, make_meta())
        program = "import sys\ndata = sys.stdin.buffer.read()\nprint('crlf' if b'\\r' in data else 'lf')\n"
        (directory / "main.py").write_text(program, encoding="utf-8")
        add_test(directory, "1\n2\n3", "lf")
        assert (directory / "tests/1.in").read_bytes() == b"1\n2\n3\n"
        assert [r.verdict for r in run_tests(tmp_path, directory, get_language("py"), 1.0)] == [Verdict.AC]

    def test_runs_python_and_reports_verdicts(self, tmp_path: Path) -> None:
        directory = problem_dir(tmp_path, 1000, "1000")
        write_meta(directory, make_meta())
        (directory / "main.py").write_text("a, b = map(int, input().split())\nprint(a + b)\n", encoding="utf-8")
        add_test(directory, "1 2", "3")
        add_test(directory, "2 2", "5")
        add_test(directory, "x", "0")
        results = run_tests(tmp_path, directory, get_language("py"), 1.0)
        assert [r.verdict for r in results] == [Verdict.AC, Verdict.WA, Verdict.RTE]
