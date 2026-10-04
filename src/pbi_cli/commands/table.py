"""Table CRUD commands."""

from __future__ import annotations

import sys

import click

from pbi_cli.commands._helpers import run_command
from pbi_cli.main import PbiContext, pass_context


@click.group()
def table() -> None:
    """Manage tables in a semantic model."""


@table.command(name="list")
@pass_context
def table_list(ctx: PbiContext) -> None:
    """List all tables."""
    from pbi_cli.core.session import get_session_for_command
    from pbi_cli.core.tom_backend import table_list as _table_list

    session = get_session_for_command(ctx)
    run_command(ctx, _table_list, model=session.model)


@table.command()
@click.argument("name")
@pass_context
def get(ctx: PbiContext, name: str) -> None:
    """Get details of a specific table."""
    from pbi_cli.core.session import get_session_for_command
    from pbi_cli.core.tom_backend import table_get

    session = get_session_for_command(ctx)
    run_command(ctx, table_get, model=session.model, table_name=name)


@table.command()
@click.argument("name")
@click.option(
    "--mode",
    type=click.Choice(["Import", "DirectQuery", "Dual"]),
    default="Import",
    help="Table mode.",
)
@click.option("--m-expression", default=None, help="M/Power Query expression (use - for stdin).")
@click.option("--dax-expression", default=None, help="DAX expression for calculated tables.")
@click.option("--description", default=None, help="Table description.")
@click.option("--hidden", is_flag=True, default=False, help="Hide from client tools.")
@pass_context
def create(
    ctx: PbiContext,
    name: str,
    mode: str,
    m_expression: str | None,
    dax_expression: str | None,
    description: str | None,
    hidden: bool,
) -> None:
    """Create a new table."""
    if m_expression == "-":
        m_expression = sys.stdin.read().strip()
    if dax_expression == "-":
        dax_expression = sys.stdin.read().strip()

    from pbi_cli.core.session import get_session_for_command
    from pbi_cli.core.tom_backend import table_create

    session = get_session_for_command(ctx)
    run_command(
        ctx,
        table_create,
        model=session.model,
        name=name,
        mode=mode,
        m_expression=m_expression,
        dax_expression=dax_expression,
        description=description,
        is_hidden=hidden,
    )


@table.command()
@click.argument("name")
@pass_context
def delete(ctx: PbiContext, name: str) -> None:
    """Delete a table."""
    from pbi_cli.core.session import get_session_for_command
    from pbi_cli.core.tom_backend import table_delete

    session = get_session_for_command(ctx)
    run_command(ctx, table_delete, model=session.model, table_name=name)


@table.command()
@click.argument("name")
@click.option(
    "--type",
    "refresh_type",
    type=click.Choice(["Full", "Automatic", "Calculate", "DataOnly"]),
    default="Automatic",
    help="Refresh type.",
)
@pass_context
def refresh(ctx: PbiContext, name: str, refresh_type: str) -> None:
    """Refresh a table."""
    from pbi_cli.core.session import get_session_for_command
    from pbi_cli.core.tom_backend import table_refresh

    session = get_session_for_command(ctx)
    run_command(
        ctx,
        table_refresh,
        model=session.model,
        table_name=name,
        refresh_type=refresh_type,
    )


@table.command()
@click.argument("name")
@pass_context
def schema(ctx: PbiContext, name: str) -> None:
    """Get the schema of a table."""
    from pbi_cli.core.session import get_session_for_command
    from pbi_cli.core.tom_backend import table_get_schema

    session = get_session_for_command(ctx)
    run_command(ctx, table_get_schema, model=session.model, table_name=name)


@table.command()
@click.argument("old_name")
@click.argument("new_name")
@pass_context
def rename(ctx: PbiContext, old_name: str, new_name: str) -> None:
    """Rename a table."""
    from pbi_cli.core.session import get_session_for_command
    from pbi_cli.core.tom_backend import table_rename

    session = get_session_for_command(ctx)
    run_command(
        ctx,
        table_rename,
        model=session.model,
        old_name=old_name,
        new_name=new_name,
    )


@table.command()
@click.argument("name")
@click.option("--description", default=None, help="New table description.")
@click.option(
    "--hidden/--visible",
    default=None,
    help="Hide or show the table (omit to leave unchanged).",
)
@pass_context
def update(ctx: PbiContext, name: str, description: str | None, hidden: bool | None) -> None:
    """Update a table's description and/or visibility."""
    from pbi_cli.core.session import get_session_for_command
    from pbi_cli.core.tom_backend import table_update

    session = get_session_for_command(ctx)
    run_command(
        ctx,
        table_update,
        model=session.model,
        table_name=name,
        description=description,
        is_hidden=hidden,
    )


@table.command(name="mark-date")
@click.argument("name")
@click.option("--date-column", required=True, help="Date column to use.")
@pass_context
def mark_date_table(ctx: PbiContext, name: str, date_column: str) -> None:
    """Mark a table as a date table."""
    from pbi_cli.core.session import get_session_for_command
    from pbi_cli.core.tom_backend import table_mark_as_date

    session = get_session_for_command(ctx)
    run_command(
        ctx,
        table_mark_as_date,
        model=session.model,
        table_name=name,
        date_column=date_column,
    )
