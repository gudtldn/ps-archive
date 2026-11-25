"""BOJ 문제 번호를 solved.ac 문제 번호로 바꿉니다.

solved.ac는 대부분 BOJ 번호를 그대로 쓰지만, 중복 문제를 합친 경우(BOJ 28955 -> 19759)와
소문제를 묶은 경우(BOJ 19918 -> 19917b)는 번호가 달라집니다. 이런 번호는 직접 조회하면
404가 나므로, 문제의 모든 저지 번호를 대상으로 하는 `id:B<번호>` 검색을 씁니다.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from solve.api import Problem, SolvedAcClient

BOJ_OJ_ID = "boj"
BOJ_SEARCH_PREFIX = "id:B"
# 사용자 토큰 없이 검색하면 100자, 8개 항까지만 허용됩니다.
MAX_QUERY_TERMS = 8
MAX_QUERY_CHARS = 100


class MappingStatus(Enum):
    SAME = "same"  # BOJ 번호와 같음
    MERGED = "merged"  # 중복 문제로 다른 번호에 합쳐짐
    SUBPROBLEM = "subproblem"  # 소문제로 묶여 subId가 붙음
    MISSING = "missing"  # solved.ac에 없음


@dataclass(frozen=True)
class Mapping:
    boj_id: int
    status: MappingStatus
    problem: Problem | None

    def to_json(self) -> dict[str, object]:
        base: dict[str, object] = {"boj": self.boj_id, "status": self.status.value}
        if self.problem is None:
            return base
        p = self.problem
        return base | {
            "key": p.key,
            "problemId": p.problem_id,
            "subId": p.sub_id,
            "title": p.title,
            "level": p.level,
            "tags": list(p.tags),
        }


def build_queries(boj_ids: Iterable[int]) -> list[str]:
    """`id:B<번호>`를 `|`로 묶은 검색어를 만듭니다. 각 검색어가 익명 검색 제한을 넘지 않게 나눕니다."""
    queries: list[str] = []
    terms: list[str] = []
    for boj_id in boj_ids:
        term = f"{BOJ_SEARCH_PREFIX}{boj_id}"
        candidate = "|".join([*terms, term])
        if terms and (len(terms) >= MAX_QUERY_TERMS or len(candidate) > MAX_QUERY_CHARS):
            queries.append("|".join(terms))
            terms = []
        terms.append(term)
    if terms:
        queries.append("|".join(terms))
    return queries


def classify(boj_id: int, problem: Problem | None) -> MappingStatus:
    if problem is None:
        return MappingStatus.MISSING
    if problem.sub_id:
        return MappingStatus.SUBPROBLEM
    if problem.problem_id != boj_id:
        return MappingStatus.MERGED
    return MappingStatus.SAME


def resolve_boj_ids(client: SolvedAcClient, boj_ids: list[int]) -> list[Mapping]:
    """입력한 번호마다 Mapping을 하나씩, 입력 순서대로 돌려줍니다."""
    found: dict[int, Problem] = {}
    for query in build_queries(boj_ids):
        for problem in client.search_problems(query):
            for native in problem.native_ids(BOJ_OJ_ID):
                found[int(native)] = problem
    return [Mapping(boj_id, classify(boj_id, found.get(boj_id)), found.get(boj_id)) for boj_id in boj_ids]
