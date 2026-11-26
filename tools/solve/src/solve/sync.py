"""solved.ac 메타데이터를 다시 받아 meta.json을 갱신하고 README를 다시 만듭니다."""

import json
from collections.abc import Callable, Iterable
from pathlib import Path

from solve.langs import LANGUAGES
from solve.layout import (
    iter_problem_dirs,
    meta_from_problem,
    problems_root,
    read_meta,
    refresh_meta,
    write_lf,
    write_meta,
)
from solve.readme import INDEX_TITLE, ReadmeEntry, render_index, render_overview, replace_section
from solve.resolve import ProblemSearcher, ProgressCallback, resolve_boj_ids

README_FILE = "README.md"
TAG_NAMES_FILE = "tags.json"


def refresh_metas(
    client: ProblemSearcher,
    repo_root: Path,
    url_patterns: dict[str, str],
    report: Callable[[str], None],
    on_progress: ProgressCallback | None = None,
) -> int:
    """BOJ 번호가 있는 모든 문제의 meta.json을 갱신하고, 바뀐 문제 수를 돌려줍니다.

    solved.ac 번호(키)가 바뀐 문제는 폴더를 옮겨야 하므로 자동으로 고치지 않고 알리기만 합니다.
    """
    by_boj = {}
    for directory in iter_problem_dirs(repo_root):
        meta = read_meta(directory)
        if (boj := meta.boj_id()) is not None:
            by_boj[int(boj)] = (directory, meta)

    changed = 0
    for mapping in resolve_boj_ids(client, list(by_boj), on_progress):
        directory, old = by_boj[mapping.boj_id]
        if mapping.problem is None:
            report(f"{old.key}: solved.ac에서 찾을 수 없어 그대로 둡니다")
            continue
        fresh = refresh_meta(old, meta_from_problem(mapping.problem, url_patterns))
        if fresh.key != old.key:
            report(f"{old.key}: solved.ac 번호가 {fresh.key}(으)로 바뀌었습니다. 폴더를 직접 옮겨 주세요")
            continue
        if fresh != old:
            write_meta(directory, fresh)
            changed += 1
            if fresh.level != old.level:
                report(f"{old.key}: 레벨 {old.level} -> {fresh.level}")
    return changed


def collect_entries(repo_root: Path) -> list[ReadmeEntry]:
    entries = []
    for directory in iter_problem_dirs(repo_root):
        langs = tuple(lang.ext for lang in LANGUAGES if (directory / lang.source_name).exists())
        entries.append(ReadmeEntry(read_meta(directory), directory.relative_to(repo_root).as_posix(), langs))
    return entries


def save_tag_names(repo_root: Path, all_names: dict[str, str], entries: list[ReadmeEntry]) -> dict[str, str]:
    """README에 쓰이는 태그 이름만 problems/tags.json에 저장합니다 (오프라인 재생성용)."""
    used = sorted({tag for entry in entries for tag in entry.meta.tags})
    names = {tag: all_names[tag] for tag in used if tag in all_names}
    write_lf(problems_root(repo_root) / TAG_NAMES_FILE, json.dumps(names, ensure_ascii=False, indent=2) + "\n")
    return names


def load_tag_names(repo_root: Path) -> dict[str, str]:
    path = problems_root(repo_root) / TAG_NAMES_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def missing_tag_names(repo_root: Path, tags: Iterable[str]) -> bool:
    """캐시에 이름이 없는 태그가 있으면 참입니다. 없으면 README에 태그 키가 그대로 찍힙니다."""
    cached = load_tag_names(repo_root)
    return any(tag not in cached for tag in tags)


def refresh_readmes(repo_root: Path, all_tag_names: dict[str, str] | None = None) -> tuple[list[Path], int]:
    """README를 다시 만들고 (갱신한 파일, 문제 수)를 돌려줍니다.

    `all_tag_names`(solved.ac 전체 태그 이름)를 주면 캐시도 갱신하고, 없으면 캐시만 읽어 네트워크 없이 끝냅니다.
    """
    entries = collect_entries(repo_root)
    if all_tag_names is None:
        tag_names = load_tag_names(repo_root)
    else:
        tag_names = save_tag_names(repo_root, all_tag_names, entries)
    return write_readmes(repo_root, entries, tag_names), len(entries)


def _update_readme(path: Path, section: str, default_header: str) -> Path:
    current = path.read_text(encoding="utf-8") if path.exists() else default_header
    write_lf(path, replace_section(current, section))
    return path


def write_readmes(repo_root: Path, entries: list[ReadmeEntry], tag_names: dict[str, str]) -> list[Path]:
    """루트 README에는 요약을, problems/README.md에는 전체 표를 씁니다."""
    return [
        _update_readme(repo_root / README_FILE, render_overview(entries, tag_names), ""),
        _update_readme(problems_root(repo_root) / README_FILE, render_index(entries, tag_names), f"{INDEX_TITLE}\n"),
    ]
