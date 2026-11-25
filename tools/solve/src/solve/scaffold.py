"""문제 폴더를 만들고 채웁니다. `solve new`와 마이그레이션이 함께 씁니다."""

from dataclasses import replace
from pathlib import Path

from solve.api import SolvedAcClient
from solve.langs import Language
from solve.layout import (
    Meta,
    add_test,
    meta_from_problem,
    problem_dir,
    read_meta,
    read_tests,
    refresh_meta,
    sync_cargo_manifest,
    write_lf,
    write_meta,
)
from solve.resolve import resolve_boj_ids
from solve.runner import outputs_match
from solve.scrape import ProblemPage
from solve.templates import render_template


class ResolveError(LookupError):
    pass


def fetch_meta(client: SolvedAcClient, boj_id: int, url_patterns: dict[str, str]) -> Meta:
    """BOJ 번호로 solved.ac 문제를 찾아 Meta를 만듭니다 (제한·상태는 비어 있음)."""
    mapping = resolve_boj_ids(client, [boj_id])[0]
    if mapping.problem is None:
        raise ResolveError(f"solved.ac에서 BOJ {boj_id}를 찾을 수 없습니다.")
    return meta_from_problem(mapping.problem, url_patterns)


def save_meta(repo_root: Path, meta: Meta, page: ProblemPage | None) -> Path:
    """meta.json을 쓰고 폴더 경로를 돌려줍니다. 이미 있으면 로컬 값(상태 등)을 유지합니다."""
    directory = problem_dir(repo_root, meta.problem_id, meta.key)
    if (directory / "meta.json").exists():
        meta = refresh_meta(read_meta(directory), meta)
    if page is not None:
        meta = replace(meta, time_limit_sec=page.time_limit_sec, memory_limit_mb=page.memory_limit_mb)
    write_meta(directory, meta)
    return directory


def add_new_tests(directory: Path, cases: list[tuple[str, str]]) -> list[str]:
    """이미 있는 테스트와 겹치지 않는 케이스만 추가하고, 추가한 이름을 돌려줍니다."""
    existing = [(i, o) for _, i, o in read_tests(directory)]
    added = []
    for input_text, output_text in cases:
        if any(outputs_match(i, input_text) and outputs_match(o, output_text) for i, o in existing):
            continue
        added.append(add_test(directory, input_text, output_text))
        existing.append((input_text, output_text))
    return added


def write_templates(repo_root: Path, directory: Path, meta: Meta, langs: tuple[Language, ...]) -> list[Path]:
    """없는 언어 파일만 만듭니다. 기존 풀이는 절대 덮어쓰지 않습니다."""
    created = []
    for lang in langs:
        target = directory / lang.source_name
        if target.exists():
            continue
        write_lf(target, render_template(lang, meta.title, meta.url()))
        created.append(target)
    if any(p.suffix == ".rs" for p in created):
        sync_cargo_manifest(repo_root)
    return created
