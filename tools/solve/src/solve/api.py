"""ps-archive에서 쓰는 호출만 구현한 solved.ac v4 클라이언트."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Self

import httpx

from solve.config import Credentials

BASE_URL = "https://solved.ac/api/v4"
USER_AGENT = "ps-archive/0.1"
TIMEOUT_SECONDS = 15
MAX_RETRIES = 3
DEFAULT_RETRY_AFTER_SECONDS = 5


class ApiError(Exception):
    """재시도로는 해결되지 않는 solved.ac 오류. HTTP 상태와 오류 코드를 함께 담습니다."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"solved.ac {status} {code}: {message}")
        self.status = status
        self.code = code


@dataclass(frozen=True)
class JudgeId:
    oj_id: str
    problem_id: str
    sub_id: str


@dataclass(frozen=True)
class Problem:
    problem_id: int
    sub_id: str
    title: str
    level: int
    tags: tuple[str, ...]
    judge_ids: tuple[JudgeId, ...]

    @property
    def key(self) -> str:
        """solved.ac에서 쓰는 문제 번호. 예: `1000`, `19917b`"""
        return f"{self.problem_id}{self.sub_id}"

    def native_ids(self, oj_id: str) -> tuple[str, ...]:
        """해당 저지에서 쓰는 문제 번호들. 저지 안에 중복 문제가 있으면 여러 개입니다."""
        return tuple(j.problem_id for j in self.judge_ids if j.oj_id == oj_id)


def _pick_title(titles: list[dict[str, Any]]) -> str:
    """한국어 제목이 있으면 그것을, 없으면 첫 번째 제목을 씁니다."""
    korean = [entry["title"] for entry in titles if entry.get("language") == "ko"]
    if korean:
        return korean[0]
    return titles[0]["title"] if titles else ""


def parse_problem(raw: dict[str, Any]) -> Problem:
    return Problem(
        problem_id=int(raw["problemId"]),
        sub_id=raw.get("subId", ""),
        title=_pick_title(raw.get("titles", [])),
        level=int(raw.get("level", 0)),
        tags=tuple(tag["key"] for tag in raw.get("tags", [])),
        judge_ids=tuple(JudgeId(j["ojId"], j["problemId"], j.get("subId", "")) for j in raw.get("judgeIds", [])),
    )


class SolvedAcClient:
    def __init__(
        self,
        credentials: Credentials,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        on_wait: Callable[[float, int], None] | None = None,
    ) -> None:
        """`on_wait(초, 시도 횟수)`는 요청 한도에 걸려 기다리기 직전에 불립니다."""
        self._sleep = sleep
        self._on_wait = on_wait
        self._http = httpx.Client(
            base_url=BASE_URL,
            headers={
                "x-client-id": credentials.client_id,
                "x-client-secret": credentials.client_secret,
                "User-Agent": USER_AGENT,
            },
            timeout=TIMEOUT_SECONDS,
            transport=transport,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self._http.close()

    def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        for attempt in range(1, MAX_RETRIES + 1):
            response = self._http.get(path, params=params)
            # 요청 한도 초과: Retry-After만큼 기다렸다가 다시 시도
            if response.status_code == 429:
                seconds = float(response.headers.get("Retry-After", DEFAULT_RETRY_AFTER_SECONDS))
                if self._on_wait is not None:
                    self._on_wait(seconds, attempt)
                self._sleep(seconds)
                continue
            if response.is_error:
                error = _error_body(response)
                raise ApiError(
                    response.status_code,
                    error.get("code", "UNKNOWN"),
                    error.get("message", response.text[:200]),
                )
            return response.json()
        raise ApiError(429, "RATE_LIMITED", f"{MAX_RETRIES}회 재시도 후에도 요청 한도 초과")

    def judge_url_patterns(self) -> dict[str, str]:
        """저지 id -> 문제 URL 패턴 (`{problemId}` 자리표시자 포함)."""
        return {judge["id"]: judge["problemUrlPattern"] for judge in self._get("/judges")["judges"]}

    def tag_names(self, language: str = "ko") -> dict[str, str]:
        """태그 키 -> 표시 이름. 해당 언어 이름이 없으면 영어, 그것도 없으면 키를 씁니다."""
        names = {}
        for tag in self._get("/tags")["tags"]:
            localized = tag.get("names", {})
            names[tag["key"]] = localized.get(language) or localized.get("en") or tag["key"]
        return names

    def search_problems(self, query: str) -> list[Problem]:
        """검색 결과를 마지막 페이지까지 모두 가져옵니다. 페이지 크기는 API가 50으로 고정합니다."""
        problems: list[Problem] = []
        page = 1
        while True:
            data = self._get("/problems", {"q": query, "page": str(page)})
            batch = [parse_problem(raw) for raw in data["problems"]]
            problems.extend(batch)
            if not batch or len(problems) >= data["total"]:
                return problems
            page += 1


def _error_body(response: httpx.Response) -> dict[str, Any]:
    try:
        return response.json().get("error", {})
    except ValueError:
        return {}
