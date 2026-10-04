"""Model-level operations."""

from __future__ import annotations

from pathlib import Path

import click

from pbi_cli.commands._helpers import run_command
from pbi_cli.core.session import get_session_for_command
from pbi_cli.core.tom_backend import model_get, model_get_stats
from pbi_cli.main import PbiContext, pass_context


@click.group()
def model() -> None:
    """Manage the semantic model."""


@model.command()
@pass_context
def get(ctx: PbiContext) -> None:
    """Get model metadata."""
    session = get_session_for_command(ctx)
    run_command(ctx, model_get, model=session.model, database=session.database)


@model.command()
@pass_context
def stats(ctx: PbiContext) -> None:
    """Get model statistics."""
    session = get_session_for_command(ctx)
    run_command(ctx, model_get_stats, model=session.model)


@model.command()
@click.option(
    "--path",
    "-p",
    default=None,
    help="Path to .SemanticModel folder, .pbip file, or parent folder "
    "(auto-detected from CWD if omitted).",
)
@click.option(
    "--report",
    "report_path",
    default=None,
    help="Path to .Report folder (auto-detected as sibling if omitted).",
)
@click.option(
    "--include-auto-date",
    is_flag=True,
    default=False,
    help="Include LocalDateTable_*/DateTableTemplate_* background tables.",
)
@pass_context
def deps(
    ctx: PbiContext,
    path: str | None,
    report_path: str | None,
    include_auto_date: bool,
) -> None:
    """Assess per-table usage statically (no Desktop / connection needed).

    Scans TMDL files + the PBIR report to classify each table as
    used-report, used-model, review, or unused (deletion candidate).
    Auto date/time background tables are excluded unless --include-auto-date.
    """
    from pbi_cli.core.deps_backend import model_deps

    model_path = Path(path) if path else _detect_model_from_cwd()
    run_command(
        ctx,
        model_deps,
        model_path=model_path,
        report_path=Path(report_path) if report_path else None,
        include_auto_date=include_auto_date,
    )


def _detect_model_from_cwd() -> Path:
    """Find a .SemanticModel by walking up from CWD."""
    cwd = Path.cwd()
    for current in (cwd, *cwd.parents):
        candidates = [
            c for c in current.iterdir() if c.is_dir() and c.name.endswith(".SemanticModel")
        ]
        if len(candidates) == 1:
            return candidates[0]
        for pbip in current.glob("*.pbip"):
            sm = current / f"{pbip.stem}.SemanticModel"
            if sm.is_dir():
                return sm
    raise FileNotFoundError("No .SemanticModel found from CWD. Pass --path explicitly.")
