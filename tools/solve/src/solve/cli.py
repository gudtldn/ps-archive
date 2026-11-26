"""`solve` 명령의 진입점."""

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from solve.api import MAX_RETRIES, ApiError, SolvedAcClient
from solve.config import ConfigError, find_repo_root, load_credentials
from solve.editor import EditorError, open_in_editor, should_open
from solve.langs import LANGUAGES, Language, UnknownLanguageError, parse_languages
from solve.layout import (
    STATUS_SOLVED,
    Meta,
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
from solve.progress import step
from solve.prompts import NotInteractiveError, SelectionCancelled, choose_languages, is_interactive
from solve.resolve import Mapping, MappingStatus, resolve_boj_ids
from solve.runner import BuildError, CaseResult, UnsupportedLanguageError, Verdict, run_tests
from solve.scaffold import ResolveError, add_new_tests, fetch_meta, save_meta, write_templates
from solve.scrape import ScrapeError, fetch_problem_page
from solve.sync import missing_tag_names, refresh_metas, refresh_readmes

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


def report(line: str) -> None:
    """로그의 [solved] 같은 문자열을 rich가 스타일 태그로 해석하지 않게 그대로 출력합니다."""
    console.print(line, markup=False, highlight=False, soft_wrap=True)


def _announce_wait(seconds: float, attempt: int) -> None:
    message = f"solved.ac 요청 한도 초과: {seconds:.0f}초 기다린 뒤 다시 시도합니다 ({attempt}/{MAX_RETRIES})"
    console.print(f"[yellow]{message}[/yellow]")


def open_client(repo_root: Path) -> SolvedAcClient:
    """요청 한도에 걸려 기다릴 때 그 사실을 알려 주는 클라이언트를 만듭니다."""
    return SolvedAcClient(load_credentials(repo_root), on_wait=_announce_wait)


def map_ids(client: SolvedAcClient, ids: list[int]) -> list[Mapping]:
    with step(console, f"solved.ac에서 문제 {len(ids)}개 조회") as current:
        return resolve_boj_ids(client, ids, current.update)


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
        with open_client(repo_root) as client:
            mappings = map_ids(client, ids)
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


def _fetch_tag_names_if_missing(
    client: SolvedAcClient, repo_root: Path, tags: tuple[str, ...]
) -> dict[str, str] | None:
    """README에 쓸 태그 이름이 캐시에 없을 때만 받습니다. 실패해도 문제 만들기는 계속합니다."""
    if not missing_tag_names(repo_root, tags):
        return None
    try:
        with step(console, "태그 이름 받기"):
            return client.tag_names()
    except ApiError as error:
        console.print(f"[yellow]경고:[/yellow] 태그 이름을 받지 못해 README에 태그 키를 그대로 씁니다. {error}")
        return None


def _print_new_summary(
    repo_root: Path, meta: Meta, directory: Path, added: list[str], sources: list[Path], created: list[Path]
) -> None:
    console.print(f"[bold]{meta.key}[/bold] {meta.title} (level {meta.level})")
    if meta.url():
        console.print(f"  링크: {meta.url()}")
    console.print(f"  예제: {len(added)}개 추가 (전체 {len(read_tests(directory))}개)")
    # 터미널에서 Ctrl+클릭으로 바로 열 수 있게 저장소 기준 상대 경로를 그대로 출력합니다.
    for path in sources:
        label = "생성" if path in created else "기존"
        console.print(f"  {label}: {path.relative_to(repo_root).as_posix()}")


@app.command()
def new(
    boj_id: Annotated[int, typer.Argument(help="BOJ 문제 번호")],
    lang: Annotated[
        str | None, typer.Option("--lang", "-l", help="쉼표로 구분한 언어 (예: rs, py,rs). 생략하면 목록에서 고릅니다")
    ] = None,
    open_editor: Annotated[
        bool | None,
        typer.Option(
            "--open/--no-open",
            "-e/-E",
            help="풀이 파일을 에디터로 열지 정합니다. 생략하면 터미널에서만 엽니다 "
            "(SOLVE_EDITOR → VISUAL → EDITOR → code)",
            show_default=False,
        ),
    ] = None,
) -> None:
    """문제 폴더를 만들고 예제와 언어별 시작 코드를 준비합니다."""
    # 네트워크 요청 전에 언어부터 정해야 취소했을 때 아무것도 하지 않고 끝납니다.
    try:
        langs = parse_languages(lang) if lang else choose_languages(is_interactive())
    except SelectionCancelled as error:
        console.print(f"[yellow]{error}[/yellow]")
        raise typer.Exit(1) from error
    except (UnknownLanguageError, NotInteractiveError) as error:
        raise fail(error) from error

    try:
        repo_root = find_repo_root()
        with open_client(repo_root) as client:
            with step(console, "solved.ac에서 문제 정보 받기"):
                meta = fetch_meta(client, boj_id, client.judge_url_patterns())
            all_tag_names = _fetch_tag_names_if_missing(client, repo_root, meta.tags)
    except EXPECTED_ERRORS as error:
        raise fail(error) from error

    page = None
    try:
        with step(console, "BOJ에서 예제 받기"):
            page = fetch_problem_page(meta.boj_id() or str(boj_id))
    except ScrapeError as error:
        console.print(f"[yellow]경고:[/yellow] 예제를 가져오지 못했습니다. {error}")

    directory = save_meta(repo_root, meta, page)
    added = add_new_tests(directory, [(s.input, s.output) for s in page.samples]) if page else []
    created = write_templates(repo_root, directory, meta, langs)
    with step(console, "README 갱신"):
        refresh_readmes(repo_root, all_tag_names)

    sources = [directory / language.source_name for language in langs]
    _print_new_summary(repo_root, meta, directory, added, sources, created)
    if should_open(open_editor, is_interactive()):
        try:
            open_in_editor(sources)
        except EditorError as error:
            console.print(f"[yellow]경고:[/yellow] {error}")


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


def _test_problem(
    repo_root: Path,
    directory: Path,
    langs: tuple[Language, ...],
    verbose: bool,
    brief: bool,
    on_stage: Callable[[str], None],
) -> bool:
    """한 문제의 언어별 테스트를 실행하고 모두 통과했는지 돌려줍니다. `on_stage`로 지금 하는 일을 알립니다."""
    meta = read_meta(directory)
    if not read_tests(directory):
        console.print(f"[yellow]{meta.key}: 테스트가 없습니다[/yellow]")
        return True

    all_passed = True
    for language in langs:
        label = f"{meta.key} · {language.name}"
        on_stage(f"{label} 빌드·실행 중")
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

    failed = []
    with step(console, "테스트", total=len(directories), announce=False) as current:
        for d in directories:
            if not _test_problem(repo_root, d, fixed_langs or _languages_in(d), verbose, run_all, current.detail):
                failed.append(d.name)
            current.advance()
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
        repo_root = find_repo_root()
        directory = find_problem(repo_root, ident)
    except EXPECTED_ERRORS as error:
        raise fail(error) from error
    meta = read_meta(directory)
    write_meta(directory, replace(meta, status=STATUS_SOLVED))
    # 상태 아이콘만 바뀌므로 태그 이름 캐시로 충분합니다 (네트워크 없음).
    with step(console, "README 갱신"):
        refresh_readmes(repo_root)
    console.print(f"{meta.key} {meta.title}: [green]{STATUS_SOLVED}[/green]")


@app.command()
def migrate(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="바꾸지 않고 계획만 출력")] = False,
) -> None:
    """예전 <BOJ 번호>/ 폴더들을 problems/ 레이아웃으로 옮깁니다."""
    try:
        repo_root = find_repo_root()
        ids = legacy_problem_ids(repo_root)
        with open_client(repo_root) as client:
            with step(console, "solved.ac 저지 정보 받기"):
                patterns = client.judge_url_patterns()
            mappings = map_ids(client, ids)
    except EXPECTED_ERRORS as error:
        raise fail(error) from error

    missing = [m.boj_id for m in mappings if m.problem is None]
    if missing:
        raise fail(Exception(f"solved.ac에서 찾지 못한 문제가 있어 중단합니다: {missing}"))
    metas = {m.boj_id: meta_from_problem(m.problem, patterns) for m in mappings if m.problem}

    plans = run_migration(repo_root, metas, fetch_problem_page, report, dry_run=dry_run)
    verb = "옮길 예정" if dry_run else "옮김"
    console.print(f"[bold]{len(plans)}개 문제 {verb}[/bold]")


@app.command()
def sync(
    offline: Annotated[bool, typer.Option("--offline", help="solved.ac를 부르지 않고 README만 다시 만듦")] = False,
) -> None:
    """solved.ac에서 티어·태그를 다시 받아 meta.json을 갱신하고 README를 다시 만듭니다."""
    all_tag_names: dict[str, str] | None = None
    try:
        repo_root = find_repo_root()
        if not offline:
            with open_client(repo_root) as client:
                with step(console, "solved.ac 저지 정보 받기"):
                    patterns = client.judge_url_patterns()
                with step(console, "티어·태그 다시 받아 meta.json 갱신") as current:
                    changed = refresh_metas(client, repo_root, patterns, report, current.update)
                with step(console, "태그 이름 받기"):
                    all_tag_names = client.tag_names()
            console.print(f"meta.json {changed}개 바뀜")
    except EXPECTED_ERRORS as error:
        raise fail(error) from error

    with step(console, "README 다시 만들기"):
        paths, count = refresh_readmes(repo_root, all_tag_names)
    console.print(f"README {len(paths)}개 갱신: 문제 {count}개")
