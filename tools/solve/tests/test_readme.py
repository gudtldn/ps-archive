from dataclasses import replace

from solve.api import JudgeId, Problem
from solve.layout import STATUS_SOLVED, STATUS_SOLVING, bucket_name, meta_from_problem
from solve.readme import (
    END_MARKER,
    START_MARKER,
    ReadmeEntry,
    render_index,
    render_overview,
    replace_section,
    tier_name,
)

PATTERNS = {"boj": "https://www.acmicpc.net/problem/{problemId}"}


def entry(
    problem_id: int, level: int, tags: tuple[str, ...], langs: tuple[str, ...], status: str, title: str = "T"
) -> ReadmeEntry:
    problem = Problem(problem_id, "", title, level, tags, (JudgeId("boj", str(problem_id), ""),))
    meta = replace(meta_from_problem(problem, PATTERNS), status=status)
    return ReadmeEntry(meta, f"problems/{bucket_name(problem_id)}/{problem_id}", langs)


class TestTierName:
    def test_boundaries(self) -> None:
        assert tier_name(0) == "Unrated"
        assert tier_name(1) == "Bronze V"
        assert tier_name(5) == "Bronze I"
        assert tier_name(6) == "Silver V"
        assert tier_name(15) == "Gold I"
        assert tier_name(30) == "Ruby I"


class TestRenderIndex:
    def test_links_are_relative_to_problems_dir(self) -> None:
        text = render_index([entry(1000, 1, ("math", "impl"), ("py", "rs"), STATUS_SOLVED, "A+B")], {"math": "수학"})
        row = next(line for line in text.splitlines() if line.startswith("| [1000]"))
        assert "[1000](https://www.acmicpc.net/problem/1000)" in row
        assert "[A+B](01000-01999/1000)" in row
        assert "https://static.solved.ac/tier_small/1.svg" in row
        assert "수학, impl" in row  # 이름을 모르는 태그는 키 그대로
        assert "[py](01000-01999/1000/main.py) [rs](01000-01999/1000/main.rs)" in row
        assert row.rstrip().endswith("✅ |")
        assert "problems/" not in text

    def test_escapes_pipe_in_title(self) -> None:
        text = render_index([entry(1, 1, (), ("py",), STATUS_SOLVED, "a|b")], {})
        assert "[a\\|b]" in text


class TestRenderOverview:
    def test_counts_solving_list_and_index_link(self) -> None:
        entries = [
            entry(1000, 1, (), ("py", "rs"), STATUS_SOLVED),
            entry(1001, 7, (), ("py",), STATUS_SOLVED),
            entry(2000, 7, ("dp",), ("cpp",), STATUS_SOLVING, "Hard"),
        ]
        text = render_overview(entries, {"dp": "다이나믹 프로그래밍"})
        assert "전체 3문제 · 해결 2 · 푸는 중 1" in text
        assert "py 2" in text and "rs 1" in text and "cpp 1" in text
        assert "| Silver | 2 |" in text
        assert "[전체 문제 목록](problems/)" in text
        solving = [line for line in text.splitlines() if line.startswith("| [")]
        assert len(solving) == 1
        assert "[Hard](problems/02000-02999/2000)" in solving[0]
        assert "다이나믹 프로그래밍" in solving[0]

    def test_no_solving_table_when_nothing_in_progress(self) -> None:
        text = render_overview([entry(1000, 1, (), ("py",), STATUS_SOLVED)], {})
        assert "푸는 중인 문제" not in text


class TestReplaceSection:
    def test_appends_when_markers_missing(self) -> None:
        result = replace_section("# 제목\n\n소개\n", "BODY")
        assert result == f"# 제목\n\n소개\n\n{START_MARKER}\nBODY\n{END_MARKER}\n"

    def test_replaces_only_between_markers(self) -> None:
        original = f"# 제목\n{START_MARKER}\nOLD\n{END_MARKER}\n\n직접 쓴 꼬리말\n"
        result = replace_section(original, "NEW")
        assert result == f"# 제목\n{START_MARKER}\nNEW\n{END_MARKER}\n\n직접 쓴 꼬리말\n"

    def test_is_idempotent(self) -> None:
        once = replace_section("# 제목\n", "BODY")
        assert replace_section(once, "BODY") == once
