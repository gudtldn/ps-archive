"""`solve` 명령의 진입점."""

import json
from collections import Counter
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from solve.api import ApiError, SolvedAcClient
from solve.config import ConfigError, find_repo_root, load_credentials
from solve.resolve import MappingStatus, resolve_boj_ids

app = typer.Typer(help="ps-archive: 문제 생성·테스트·solved.ac 동기화", no_args_is_help=True)
console = Console()

STATUS_STYLE = {
    MappingStatus.SAME: "green",
    MappingStatus.MERGED: "yellow",
    MappingStatus.SUBPROBLEM: "cyan",
    MappingStatus.MISSING: "red",
}


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
        out.write_text(json.dumps([m.to_json() for m in mappings], ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"저장: {out}")
