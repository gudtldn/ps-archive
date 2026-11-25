"""README의 자동 생성 구역(통계와 문제 표)을 만듭니다.

README에서 START_MARKER와 END_MARKER 사이만 바꾸고, 나머지는 직접 쓴 내용으로 보고 건드리지 않습니다.
"""

import posixpath
from collections import Counter
from dataclasses import dataclass

from solve.layout import PROBLEMS_DIR, STATUS_SOLVED, STATUS_SOLVING, Meta

START_MARKER = "<!-- solve:start -->"
END_MARKER = "<!-- solve:end -->"
TIER_ICON_URL = "https://static.solved.ac/tier_small/{level}.svg"
TIER_GROUPS = ("Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ruby")
TIER_STEPS = ("V", "IV", "III", "II", "I")
LEVELS_PER_GROUP = len(TIER_STEPS)
STATUS_ICON = {STATUS_SOLVED: "✅", STATUS_SOLVING: "🚧"}
INDEX_DIR = PROBLEMS_DIR  # 전체 표는 problems/README.md에 둡니다 (GitHub이 폴더를 열면 보여 줌)
INDEX_TITLE = "# 문제 목록"
GENERATED_NOTE = "<!-- 이 구역은 `solve sync`가 생성합니다. 직접 고치면 덮어써집니다. -->"


@dataclass(frozen=True)
class ReadmeEntry:
    meta: Meta
    path: str  # 저장소 루트 기준 문제 폴더 (POSIX 구분자)
    langs: tuple[str, ...]  # 풀이가 있는 언어의 확장자 (py, rs, ...)


def tier_group(level: int) -> str:
    return "Unrated" if level <= 0 else TIER_GROUPS[(level - 1) // LEVELS_PER_GROUP]


def tier_name(level: int) -> str:
    if level <= 0:
        return "Unrated"
    return f"{tier_group(level)} {TIER_STEPS[(level - 1) % LEVELS_PER_GROUP]}"


def _cell(text: str) -> str:
    """표 칸 안에서 열 구분자로 해석되지 않게 `|`를 이스케이프합니다."""
    return text.replace("|", "\\|")


def _row(entry: ReadmeEntry, tag_names: dict[str, str], base: str) -> str:
    """`base`(README가 있는 폴더, 저장소 루트 기준) 기준 상대 링크로 표 한 줄을 만듭니다."""
    meta = entry.meta
    path = posixpath.relpath(entry.path, base)
    number = f"[{meta.key}]({meta.url()})" if meta.url() else meta.key
    title = f"[{_cell(meta.title)}]({path})"
    tier = f'<img src="{TIER_ICON_URL.format(level=meta.level)}" alt="{tier_name(meta.level)}" height="16">'
    tags = ", ".join(_cell(tag_names.get(tag, tag)) for tag in meta.tags)
    solutions = " ".join(f"[{ext}]({path}/main.{ext})" for ext in entry.langs)
    status = STATUS_ICON.get(meta.status, meta.status)
    return f"| {number} | {title} | {tier} | {tags} | {solutions} | {status} |"


def _table(entries: list[ReadmeEntry], tag_names: dict[str, str], base: str) -> list[str]:
    return [
        "| 번호 | 제목 | 티어 | 태그 | 풀이 | 상태 |",
        "| ---: | --- | :---: | --- | --- | :---: |",
        *(_row(entry, tag_names, base) for entry in entries),
    ]


def render_overview(entries: list[ReadmeEntry], tag_names: dict[str, str]) -> str:
    """루트 README용: 통계, 푸는 중인 문제, 전체 목록 링크."""
    statuses = Counter(e.meta.status for e in entries)
    langs = Counter(ext for e in entries for ext in e.langs)
    tiers = Counter(tier_group(e.meta.level) for e in entries)
    solving = [e for e in entries if e.meta.status == STATUS_SOLVING]

    lines = [
        GENERATED_NOTE,
        "",
        "## 통계",
        "",
        f"전체 {len(entries)}문제 · 해결 {statuses[STATUS_SOLVED]} · 푸는 중 {statuses[STATUS_SOLVING]}",
        "",
        "언어: " + " · ".join(f"{ext} {count}" for ext, count in langs.most_common()),
        "",
        "| 티어 | 문제 수 |",
        "| --- | ---: |",
        *(f"| {group} | {tiers[group]} |" for group in (*TIER_GROUPS, "Unrated") if tiers[group]),
    ]
    if solving:
        lines += ["", "## 푸는 중인 문제", "", *_table(solving, tag_names, base=".")]
    lines += ["", f"[전체 문제 목록]({INDEX_DIR}/)"]
    return "\n".join(lines)


def render_index(entries: list[ReadmeEntry], tag_names: dict[str, str]) -> str:
    """problems/README.md용: 전체 문제 표. 링크는 problems/ 기준입니다."""
    return "\n".join([GENERATED_NOTE, "", *_table(entries, tag_names, base=INDEX_DIR)])


def replace_section(readme: str, section: str) -> str:
    """표식 사이를 `section`으로 바꿉니다. 표식이 없으면 문서 끝에 새로 붙입니다."""
    block = f"{START_MARKER}\n{section}\n{END_MARKER}"
    start = readme.find(START_MARKER)
    end = readme.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        return f"{readme.rstrip()}\n\n{block}\n"
    return readme[:start] + block + readme[end + len(END_MARKER) :]
