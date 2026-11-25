"""`solve` 명령의 진입점."""

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from solve.api import ApiError, SolvedAcClient
from solve.config import ConfigError, find_repo_root, load_credentials
from solve.langs import LANGUAGES, Language, UnknownLanguageError, parse_languages
from solve.layout import (
    STATUS_SOLVED,
    ProblemNotFoundError,
    find_problem,
    iter_problem_dirs,
    meta_from_problem,
    read_meta,
    read_tests,
    write_lf,
    write_meta,
)
from solve.migrate import migrate as run_migration
from solve.resolve import MappingStatus, resolve_boj_ids
from solve.runner import BuildError, CaseResult, UnsupportedLanguageError, Verdict, run_tests
from solve.scaffold import ResolveError, add_new_tests, fetch_meta, save_meta, write_templates
from solve.scrape import ScrapeError, fetch_problem_page

app = typer.Typer(help="ps-archive: 문제 생성·테스트·solved.ac 동기화", no_args_is_help=True)
console = Console()

STATUS_STYLE = {
    MappingStatus.SAME: "green",
    MappingStatus.MERGED: "yellow",
    MappingStatus.SUBPROBLEM: "cyan",
    MappingStatus.MISSING: "red",
}
VERDICT_STYLE = {Verdict.AC: "green", Verdict.WA: "red", Verdict.TLE: "yellow", Verdict.RTE: "magenta"}
DIFF_PREVIEW_CHARS = 500
EXPECTED_ERRORS = (ConfigError, ApiError, ProblemNotFoundError, ResolveError, UnknownLanguageError)


def fail(error: Exception) -> typer.Exit:
    console.print(f"[red]오류:[/red] {error}")
    return typer.Exit(1)


def legacy_problem_ids(repo_root: Path) -> list[int]:
    """예전 레이아웃에서 BOJ 번호를 모읍니다. 저장소 루트의 숫자 이름 폴더가 대상입니다."""
    return sorted(int(p.name) for p in repo_root.iterdir() if p.is_dir() and p.name.isdigit())


@app.callback()
def main() -> None:
    """ps-archive CLI."""


@app.command()
def resolve(
    boj_ids: Annotated[list[int] | None, typer.Argument(help="BOJ 번호. 생략하면 저장소의 기존 문제 폴더 전체")] = None,
    out: Annotated[Path | None, typer.Option("--out", "-o", help="매핑 결과를 JSON으로 저장")] = None,
    only_changed: Annotated[bool, typer.Option("--changed", help="번호가 달라지는 문제만 표시")] = False,
) -> None:
    """BOJ 번호를 solved.ac 문제 번호로 매핑합니다."""
    try:
        repo_root = find_repo_root()
        ids = boj_ids or legacy_problem_ids(repo_root)
        with SolvedAcClient(load_credentials(repo_root)) as client:
            mappings = resolve_boj_ids(client, ids)
    except (ConfigError, ApiError) as error:
        console.print(f"[red]오류:[/red] {error}")
        raise typer.Exit(1) from error

    table = Table("BOJ", "solved.ac", "상태", "제목", "레벨")
    for m in mappings:
        if only_changed and m.status is MappingStatus.SAME:
            continue
        style = STATUS_STYLE[m.status]
        p = m.problem
        table.add_row(
            str(m.boj_id),
            p.key if p else "-",
            f"[{style}]{m.status.value}[/{style}]",
            p.title if p else "",
            str(p.level) if p else "",
        )
    console.print(table)

    counts = Counter(m.status for m in mappings)
    console.print(" · ".join(f"{s.value} {counts[s]}" for s in MappingStatus) + f" (총 {len(mappings)})")

    if out:
        write_lf(out, json.dumps([m.to_json() for m in mappings], ensure_ascii=False, indent=2))
        console.print(f"저장: {out}")


@app.command()
def new(
    boj_id: Annotated[int, typer.Argument(help="BOJ 문제 번호")],
    lang: Annotated[str, typer.Option("--lang", "-l", help="쉼표로 구분한 언어 (예: py,rs)")] = "py",
) -> None:
    """문제 폴더를 만들고 예제와 언어별 시작 코드를 준비합니다."""
    try:
        langs = parse_languages(lang)
        repo_root = find_repo_root()
        with SolvedAcClient(load_credentials(repo_root)) as client:
            meta = fetch_meta(client, boj_id, client.judge_url_patterns())
    except EXPECTED_ERRORS as error:
        raise fail(error) from error

    page = None
    try:
        page = fetch_problem_page(meta.boj_id() or str(boj_id))
    except ScrapeError as error:
        console.print(f"[yellow]경고:[/yellow] 예제를 가져오지 못했습니다. {error}")

    directory = save_meta(repo_root, meta, page)
    added = add_new_tests(directory, [(s.input, s.output) for s in page.samples]) if page else []
    created = write_templates(repo_root, directory, meta, langs)

    console.print(f"[bold]{meta.key}[/bold] {meta.title} (level {meta.level})")
    console.print(f"  폴더: {directory.relative_to(repo_root).as_posix()}")
    console.print(f"  예제: {len(added)}개 추가 (전체 {len(read_tests(directory))}개)")
    for path in created:
        console.print(f"  생성: {path.name}")


def _show_result(result: CaseResult, verbose: bool) -> None:
    style = VERDICT_STYLE[result.verdict]
    console.print(f"  #{result.name:<3} [{style}]{result.verdict.value:<3}[/{style}] {result.elapsed:.2f}s")
    if result.verdict is Verdict.AC or not verbose:
        return
    if result.verdict is Verdict.WA:
        console.print(f"[dim]    기대:[/dim]\n{result.expected[:DIFF_PREVIEW_CHARS]}")
        console.print(f"[dim]    출력:[/dim]\n{result.actual[:DIFF_PREVIEW_CHARS]}")
    if result.stderr.strip():
        console.print(f"[dim]    stderr:[/dim]\n{result.stderr[-DIFF_PREVIEW_CHARS:]}")


def _languages_in(directory: Path) -> tuple[Language, ...]:
    return tuple(lang for lang in LANGUAGES if (directory / lang.source_name).exists())


def _test_problem(repo_root: Path, directory: Path, langs: tuple[Language, ...], verbose: bool, brief: bool) -> bool:
    """한 문제의 언어별 테스트를 실행하고 모두 통과했는지 돌려줍니다."""
    meta = read_meta(directory)
    if not read_tests(directory):
        console.print(f"[yellow]{meta.key}: 테스트가 없습니다[/yellow]")
        return True

    all_passed = True
    for language in langs:
        label = f"{meta.key} · {language.name}"
        try:
            results = run_tests(repo_root, directory, language, meta.time_limit_sec)
        except UnsupportedLanguageError as error:
            if not brief:
                console.print(f"[bold]{label}[/bold]\n  [dim]건너뜀: {error}[/dim]")
            continue
        except BuildError as error:
            console.print(f"[bold]{label}[/bold] [red]빌드 실패[/red]")
            if not brief or verbose:
                console.print(str(error), markup=False)
            all_passed = False
            continue

        passed = all(r.verdict is Verdict.AC for r in results)
        all_passed = all_passed and passed
        if brief and passed:
            continue
        console.print(f"[bold]{label}[/bold]")
        for result in results:
            _show_result(result, verbose)
    return all_passed


@app.command()
def test(
    ident: Annotated[str | None, typer.Argument(help="solved.ac 키(1000, 19917b) 또는 BOJ 번호")] = None,
    lang: Annotated[str | None, typer.Option("--lang", "-l", help="이 언어만 테스트 (기본: 모든 언어)")] = None,
    run_all: Annotated[bool, typer.Option("--all", help="모든 문제를 테스트하고 실패한 것만 표시")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="틀린 케이스의 기대·실제 출력 표시")] = False,
) -> None:
    """tests/의 모든 케이스를 실행해 결과를 비교합니다."""
    try:
        repo_root = find_repo_root()
        if run_all:
            directories = iter_problem_dirs(repo_root)
        elif ident:
            directories = [find_problem(repo_root, ident)]
        else:
            raise fail(Exception("문제 번호를 주거나 --all을 쓰세요."))
        fixed_langs = parse_languages(lang) if lang else None
    except EXPECTED_ERRORS as error:
        raise fail(error) from error

    failed = [
        d.name
        for d in directories
        if not _test_problem(repo_root, d, fixed_langs or _languages_in(d), verbose, brief=run_all)
    ]
    if run_all:
        console.print(f"[bold]{len(directories) - len(failed)}/{len(directories)} 통과[/bold]")
        if failed:
            console.print(f"실패: {' '.join(failed)}", markup=False)
    if failed:
        raise typer.Exit(1)


@app.command()
def done(ident: Annotated[str, typer.Argument(help="solved.ac 키 또는 BOJ 번호")]) -> None:
    """문제 상태를 solved로 바꿉니다."""
    try:
        directory = find_problem(find_repo_root(), ident)
    except EXPECTED_ERRORS as error:
        raise fail(error) from error
    meta = read_meta(directory)
    write_meta(directory, replace(meta, status=STATUS_SOLVED))
    console.print(f"{meta.key} {meta.title}: [green]{STATUS_SOLVED}[/green]")


@app.command()
def migrate(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="바꾸지 않고 계획만 출력")] = False,
) -> None:
    """예전 <BOJ 번호>/ 폴더들을 problems/ 레이아웃으로 옮깁니다."""
    try:
        repo_root = find_repo_root()
        ids = legacy_problem_ids(repo_root)
        with SolvedAcClient(load_credentials(repo_root)) as client:
            patterns = client.judge_url_patterns()
            mappings = resolve_boj_ids(client, ids)
    except EXPECTED_ERRORS as error:
        raise fail(error) from error

    missing = [m.boj_id for m in mappings if m.problem is None]
    if missing:
        raise fail(Exception(f"solved.ac에서 찾지 못한 문제가 있어 중단합니다: {missing}"))
    metas = {m.boj_id: meta_from_problem(m.problem, patterns) for m in mappings if m.problem}

    # 로그의 [solved] 같은 문자열을 rich가 스타일 태그로 해석하지 않게 합니다.
    def report(line: str) -> None:
        console.print(line, markup=False, highlight=False, soft_wrap=True)

    plans = run_migration(repo_root, metas, fetch_problem_page, report, dry_run=dry_run)
    verb = "옮길 예정" if dry_run else "옮김"
    console.print(f"[bold]{len(plans)}개 문제 {verb}[/bold]")
