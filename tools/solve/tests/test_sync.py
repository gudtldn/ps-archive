from dataclasses import replace
from pathlib import Path

from solve.api import JudgeId, Problem
from solve.layout import STATUS_SOLVED, meta_from_problem, problem_dir, read_meta, write_meta
from solve.readme import START_MARKER
from solve.sync import collect_entries, load_tag_names, refresh_metas, save_tag_names, write_readmes

PATTERNS = {"boj": "https://www.acmicpc.net/problem/{problemId}"}


def problem(problem_id: int, level: int, tags: tuple[str, ...] = (), sub_id: str = "", boj: int | None = None):
    return Problem(problem_id, sub_id, f"P{problem_id}", level, tags, (JudgeId("boj", str(boj or problem_id), ""),))


class FakeSearcher:
    """`id:B<n>|...` 검색에 catalog에서 BOJ 번호가 맞는 문제를 돌려줍니다."""

    def __init__(self, catalog: list[Problem]) -> None:
        self.catalog = catalog

    def search_problems(self, query: str) -> list[Problem]:
        wanted = {term.removeprefix("id:B") for term in query.split("|")}
        return [p for p in self.catalog if wanted & set(p.native_ids("boj"))]


def save(repo: Path, p: Problem, **changes: object) -> Path:
    directory = problem_dir(repo, p.problem_id, p.key)
    write_meta(directory, replace(meta_from_problem(p, PATTERNS), **changes))
    return directory


class TestRefreshMetas:
    def test_updates_solved_ac_fields_and_keeps_local_ones(self, tmp_path: Path) -> None:
        directory = save(tmp_path, problem(1000, 1), status=STATUS_SOLVED, time_limit_sec=2.0)
        logs: list[str] = []
        changed = refresh_metas(FakeSearcher([problem(1000, 3, ("math",))]), tmp_path, PATTERNS, logs.append)

        meta = read_meta(directory)
        assert changed == 1
        assert (meta.level, meta.tags) == (3, ("math",))
        assert (meta.status, meta.time_limit_sec) == (STATUS_SOLVED, 2.0)
        assert logs == ["1000: 레벨 1 -> 3"]

    def test_unchanged_problem_is_not_rewritten(self, tmp_path: Path) -> None:
        save(tmp_path, problem(1000, 1))
        assert refresh_metas(FakeSearcher([problem(1000, 1)]), tmp_path, PATTERNS, lambda _: None) == 0

    def test_forwards_query_progress(self, tmp_path: Path) -> None:
        save(tmp_path, problem(1000, 1))
        calls: list[tuple[int, int]] = []
        refresh_metas(
            FakeSearcher([problem(1000, 1)]),
            tmp_path,
            PATTERNS,
            lambda _: None,
            on_progress=lambda done, total: calls.append((done, total)),
        )
        assert calls == [(0, 1), (1, 1)]

    def test_key_change_is_reported_not_applied(self, tmp_path: Path) -> None:
        directory = save(tmp_path, problem(28955, 4))
        logs: list[str] = []
        refresh_metas(FakeSearcher([problem(19759, 4, boj=28955)]), tmp_path, PATTERNS, logs.append)
        assert read_meta(directory).key == "28955"
        assert "19759" in logs[0]


def test_collect_entries_lists_solution_languages(tmp_path: Path) -> None:
    directory = save(tmp_path, problem(1000, 1))
    (directory / "main.rs").write_text("", encoding="utf-8")
    (directory / "main.py").write_text("", encoding="utf-8")
    [entry] = collect_entries(tmp_path)
    assert entry.langs == ("py", "rs")
    assert entry.path == "problems/01000-01999/1000"


def test_tag_names_round_trip_only_used_tags(tmp_path: Path) -> None:
    save(tmp_path, problem(1000, 1, ("math",)))
    save_tag_names(tmp_path, {"math": "수학", "dp": "다이나믹 프로그래밍"}, collect_entries(tmp_path))
    assert load_tag_names(tmp_path) == {"math": "수학"}


def test_write_readmes_keeps_hand_written_header_and_writes_index(tmp_path: Path) -> None:
    save(tmp_path, problem(1000, 1, ("math",)), status=STATUS_SOLVED)
    (tmp_path / "README.md").write_text("# 내 풀이\n\n배지\n", encoding="utf-8")
    written = write_readmes(tmp_path, collect_entries(tmp_path), {"math": "수학"})

    root = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert root.startswith("# 내 풀이\n\n배지\n\n" + START_MARKER)
    assert "[전체 문제 목록](problems/)" in root
    assert "| [1000]" not in root  # 전체 표는 루트에 두지 않습니다

    index = (tmp_path / "problems" / "README.md").read_text(encoding="utf-8")
    assert index.startswith("# 문제 목록\n")
    assert "[P1000](01000-01999/1000)" in index and "수학" in index
    assert [p.relative_to(tmp_path).as_posix() for p in written] == ["README.md", "problems/README.md"]
