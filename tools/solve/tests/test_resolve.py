import httpx
import pytest

from solve.api import ApiError, JudgeId, Problem, SolvedAcClient, parse_problem
from solve.config import Credentials, parse_env_file
from solve.resolve import (
    MAX_QUERY_CHARS,
    MAX_QUERY_TERMS,
    MappingStatus,
    build_queries,
    classify,
    resolve_boj_ids,
)

CREDS = Credentials("id", "secret")


def boj_problem(problem_id: int, sub_id: str = "", natives: tuple[str, ...] = ()) -> Problem:
    ids = natives or (str(problem_id),)
    return Problem(problem_id, sub_id, f"P{problem_id}{sub_id}", 5, (), tuple(JudgeId("boj", n, "") for n in ids))


def raw_problem(problem: Problem) -> dict:
    return {
        "problemId": problem.problem_id,
        "subId": problem.sub_id,
        "titles": [{"language": "ko", "title": problem.title}],
        "level": problem.level,
        "tags": [],
        "judgeIds": [{"ojId": j.oj_id, "problemId": j.problem_id, "subId": j.sub_id} for j in problem.judge_ids],
    }


class TestBuildQueries:
    def test_groups_ids_within_term_limit(self) -> None:
        queries = build_queries(list(range(1000, 1020)))
        assert len(queries) == 3
        assert all(q.count("|") + 1 <= MAX_QUERY_TERMS for q in queries)
        assert queries[0].startswith("id:B1000|id:B1001")

    def test_respects_char_limit(self) -> None:
        queries = build_queries([10**9 + i for i in range(30)])
        assert all(len(q) <= MAX_QUERY_CHARS for q in queries)

    def test_empty_input_gives_no_queries(self) -> None:
        assert build_queries([]) == []


class TestClassify:
    def test_identity(self) -> None:
        assert classify(1000, boj_problem(1000)) is MappingStatus.SAME

    def test_merged_duplicate(self) -> None:
        assert classify(28955, boj_problem(19759, natives=("19759", "28955"))) is MappingStatus.MERGED

    def test_subproblem(self) -> None:
        assert classify(19918, boj_problem(19917, "b", natives=("19918",))) is MappingStatus.SUBPROBLEM

    def test_missing(self) -> None:
        assert classify(99999, None) is MappingStatus.MISSING


def fake_search(problems: list[Problem]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        wanted = {term.removeprefix("id:B") for term in request.url.params["q"].split("|")}
        hits = [raw_problem(p) for p in problems if wanted & set(p.native_ids("boj"))]
        return httpx.Response(200, json={"problems": hits, "total": len(hits), "page": 1, "pageSize": 50})

    return httpx.MockTransport(handler)


class TestResolveBojIds:
    def test_maps_every_id_including_exceptions(self) -> None:
        catalog = [
            boj_problem(1000),
            boj_problem(19759, natives=("19759", "28955")),
            boj_problem(19917, "b", ("19918",)),
        ]
        with SolvedAcClient(CREDS, transport=fake_search(catalog)) as client:
            rows = resolve_boj_ids(client, [1000, 28955, 19918, 42])

        by_boj = {row.boj_id: row for row in rows}
        assert by_boj[1000].status is MappingStatus.SAME
        assert by_boj[28955].problem.key == "19759"
        assert by_boj[19918].problem.key == "19917b"
        assert by_boj[42].status is MappingStatus.MISSING
        assert [row.boj_id for row in rows] == [1000, 28955, 19918, 42]


class TestClient:
    def test_retries_after_rate_limit(self) -> None:
        calls = iter(
            [httpx.Response(429, headers={"Retry-After": "0"}), httpx.Response(200, json={"problems": [], "total": 0})]
        )
        slept: list[float] = []
        transport = httpx.MockTransport(lambda _: next(calls))
        with SolvedAcClient(CREDS, transport=transport, sleep=slept.append) as client:
            assert client.search_problems("id:B1") == []
        assert slept == [0.0]

    def test_raises_api_error_with_code(self) -> None:
        transport = httpx.MockTransport(
            lambda _: httpx.Response(401, json={"error": {"code": "SIGN_IN_REQUIRED", "message": "too long"}})
        )
        with SolvedAcClient(CREDS, transport=transport) as client, pytest.raises(ApiError) as info:
            client.search_problems("x")
        assert info.value.code == "SIGN_IN_REQUIRED"

    def test_parse_prefers_korean_title(self) -> None:
        raw = raw_problem(boj_problem(1000)) | {
            "titles": [{"language": "en", "title": "A+B en"}, {"language": "ko", "title": "A+B"}]
        }
        assert parse_problem(raw).title == "A+B"


def test_parse_env_file_handles_comments_and_quotes() -> None:
    text = "# comment\nSOLVEDAC_CLIENT_ID='abc'\n\nSOLVEDAC_CLIENT_SECRET=\"x=y\"\n"
    assert parse_env_file(text) == {"SOLVEDAC_CLIENT_ID": "abc", "SOLVEDAC_CLIENT_SECRET": "x=y"}
