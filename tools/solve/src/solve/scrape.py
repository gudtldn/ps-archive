"""BOJ 문제 페이지에서 예제 입출력과 시간·메모리 제한만 가져옵니다.

solved.ac API는 문제 본문을 주지 않아서 이 부분만 스크래핑에 의존합니다.
BOJ는 운영사가 바뀐 적이 있어 페이지 구조가 언제든 달라질 수 있으므로,
필요한 요소를 못 찾으면 빈 결과 대신 ScrapeError를 냅니다.
"""

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup, Tag

BOJ_PROBLEM_URL = "https://www.acmicpc.net/problem/{problem_id}"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
TIMEOUT_SECONDS = 15
CHALLENGE_MARKER = "Just a moment..."


class ScrapeError(Exception):
    """BOJ 페이지를 받지 못했거나 구조가 예상과 다를 때 발생합니다."""


@dataclass(frozen=True)
class Sample:
    input: str
    output: str


@dataclass(frozen=True)
class ProblemPage:
    time_limit_sec: float
    memory_limit_mb: int
    samples: tuple[Sample, ...]


def _normalize(text: str) -> str:
    """줄바꿈을 LF로 통일하고 끝의 공백만 정리합니다. 줄 안의 공백은 그대로 둡니다."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def _first_number(text: str, what: str) -> float:
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        raise ScrapeError(f"{what}을(를) 읽을 수 없습니다: {text!r}")
    return float(match.group())


def _require(soup: BeautifulSoup, selector: str) -> Tag:
    element = soup.select_one(selector)
    if element is None:
        raise ScrapeError(f"BOJ 페이지에서 `{selector}`를 찾지 못했습니다. 페이지 구조가 바뀌었을 수 있습니다.")
    return element


def parse_problem_page(html: str) -> ProblemPage:
    if CHALLENGE_MARKER in html:
        raise ScrapeError("Cloudflare 확인 페이지가 돌아왔습니다. 잠시 후 다시 시도하세요.")

    soup = BeautifulSoup(html, "lxml")
    _require(soup, "#problem_title")
    info = _require(soup, "#problem-info")
    cells = info.select("tbody tr:first-child td")
    if len(cells) < 2:
        raise ScrapeError("BOJ 페이지의 제한 정보 표를 읽을 수 없습니다.")

    inputs = soup.select('pre[id^="sample-input-"]')
    outputs = soup.select('pre[id^="sample-output-"]')
    if len(inputs) != len(outputs):
        raise ScrapeError(f"예제 입력({len(inputs)})과 출력({len(outputs)}) 개수가 다릅니다.")

    return ProblemPage(
        time_limit_sec=_first_number(cells[0].get_text(), "시간 제한"),
        memory_limit_mb=int(_first_number(cells[1].get_text(), "메모리 제한")),
        samples=tuple(
            Sample(_normalize(i.get_text()), _normalize(o.get_text())) for i, o in zip(inputs, outputs, strict=True)
        ),
    )


def fetch_problem_page(problem_id: str, client: httpx.Client | None = None) -> ProblemPage:
    """BOJ 문제 번호(solved.ac 번호가 아님)로 페이지를 받아 파싱합니다."""
    url = BOJ_PROBLEM_URL.format(problem_id=problem_id)
    owns_client = client is None
    http = client or httpx.Client(
        headers={"User-Agent": BROWSER_USER_AGENT}, timeout=TIMEOUT_SECONDS, follow_redirects=True
    )
    try:
        response = http.get(url)
    except httpx.HTTPError as error:
        raise ScrapeError(f"BOJ 요청 실패 ({url}): {error}") from error
    finally:
        if owns_client:
            http.close()
    if response.is_error:
        raise ScrapeError(f"BOJ가 {response.status_code}를 돌려줬습니다: {url}")
    return parse_problem_page(response.text)
