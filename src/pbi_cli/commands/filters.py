"""PBIR filter management commands."""

from __future__ import annotations

import click

from pbi_cli.commands._helpers import run_command
from pbi_cli.main import PbiContext, pass_context


@click.group()
@click.option(
    "--path",
    "-p",
    default=None,
    help="Path to .Report folder (auto-detected from CWD if omitted).",
)
@click.option(
    "--no-sync",
    is_flag=True,
    default=False,
    help="Skip Desktop auto-sync after write commands. Use for scripted multi-step builds.",
)
@click.pass_context
def filters(ctx: click.Context, path: str | None, no_sync: bool) -> None:
    """Manage page and visual filters."""
    ctx.ensure_object(dict)
    ctx.obj["report_path"] = path
    ctx.obj["no_sync"] = no_sync


@filters.command(name="list")
@click.option("--page", required=True, help="Page name (folder name, not display name).")
@click.option("--visual", default=None, help="Visual name (returns visual filters if given).")
@click.option(
    "--condition",
    is_flag=True,
    default=False,
    help="Return a summarized view (name, type, field, condition) instead of raw filter JSON.",
)
@click.pass_context
@pass_context
def filter_list_cmd(
    ctx: PbiContext,
    click_ctx: click.Context,
    page: str,
    visual: str | None,
    condition: bool,
) -> None:
    """List filters on a page or visual."""
    from pbi_cli.core.filter_backend import filter_list
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        filter_list,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual,
        summarize=condition,
    )


@filters.command(name="where")
@click.option("--page", required=True, help="Page name (folder name, not display name).")
@click.option("--visual", default=None, help="Visual name (searches visual filters if given).")
@click.option(
    "--field",
    "field_specs",
    multiple=True,
    required=True,
    help="Field spec to match: Table[Field] or bare Field. Repeatable (OR semantics).",
)
@click.option(
    "--type",
    "type_filter",
    default=None,
    help="Restrict to a filter type: Categorical, TopN, RelativeDate, Advanced.",
)
@click.option(
    "--condition",
    is_flag=True,
    default=False,
    help="Return a summarized view instead of raw filter JSON.",
)
@click.pass_context
@pass_context
def filter_where_cmd(
    ctx: PbiContext,
    click_ctx: click.Context,
    page: str,
    visual: str | None,
    field_specs: tuple[str, ...],
    type_filter: str | None,
    condition: bool,
) -> None:
    """Find filters whose field matches a spec.

    Examples:

      pbi filters where --page p1 --field "Manager Level Selector[Valid Manager (L2-L5 Only)]"

      pbi filters where --page p1 --visual vis1 --field "Revenue" --condition
    """
    from pbi_cli.core.filter_backend import filter_where
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        filter_where,
        definition_path=definition_path,
        page_name=page,
        field_specs=list(field_specs),
        visual_name=visual,
        type_filter=type_filter,
        summarize=condition,
    )


@filters.command(name="add-categorical")
@click.option("--page", required=True, help="Page name (folder name, not display name).")
@click.option("--table", required=True, help="Table name.")
@click.option("--column", required=True, help="Column name.")
@click.option(
    "--value",
    "values",
    multiple=True,
    required=True,
    help="Value to include (repeat for multiple).",
)
@click.option("--visual", default=None, help="Visual name (adds visual filter if given).")
@click.option("--name", "-n", default=None, help="Filter ID (auto-generated if omitted).")
@click.pass_context
@pass_context
def add_categorical_cmd(
    ctx: PbiContext,
    click_ctx: click.Context,
    page: str,
    table: str,
    column: str,
    values: tuple[str, ...],
    visual: str | None,
    name: str | None,
) -> None:
    """Add a categorical filter to a page or visual."""
    from pbi_cli.core.filter_backend import filter_add_categorical
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        filter_add_categorical,
        definition_path=definition_path,
        page_name=page,
        table=table,
        column=column,
        values=list(values),
        visual_name=visual,
        name=name,
    )


@filters.command(name="add-topn")
@click.option("--page", required=True, help="Page name (folder name, not display name).")
@click.option("--table", required=True, help="Table containing the filtered column.")
@click.option("--column", required=True, help="Column to filter (e.g. Country).")
@click.option("--n", type=int, required=True, help="Number of items to keep.")
@click.option("--order-by-table", required=True, help="Table containing the ordering column.")
@click.option("--order-by-column", required=True, help="Column to rank by (e.g. Sales).")
@click.option(
    "--direction",
    default="Top",
    show_default=True,
    help="'Top' (highest N) or 'Bottom' (lowest N).",
)
@click.option("--visual", default=None, help="Visual name (adds visual filter if given).")
@click.option("--name", "-n_", default=None, help="Filter ID (auto-generated if omitted).")
@click.pass_context
@pass_context
def add_topn_cmd(
    ctx: PbiContext,
    click_ctx: click.Context,
    page: str,
    table: str,
    column: str,
    n: int,
    order_by_table: str,
    order_by_column: str,
    direction: str,
    visual: str | None,
    name: str | None,
) -> None:
    """Add a TopN filter (keep top/bottom N rows by a ranking column)."""
    from pbi_cli.core.filter_backend import filter_add_topn
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        filter_add_topn,
        definition_path=definition_path,
        page_name=page,
        table=table,
        column=column,
        n=n,
        order_by_table=order_by_table,
        order_by_column=order_by_column,
        direction=direction,
        visual_name=visual,
        name=name,
    )


@filters.command(name="add-relative-date")
@click.option("--page", required=True, help="Page name (folder name, not display name).")
@click.option("--table", required=True, help="Table containing the date column.")
@click.option("--column", required=True, help="Date column to filter (e.g. Date).")
@click.option("--amount", type=int, required=True, help="Number of periods (e.g. 3).")
@click.option(
    "--unit",
    required=True,
    help="Time unit: days, weeks, months, or years.",
)
@click.option("--visual", default=None, help="Visual name (adds visual filter if given).")
@click.option("--name", "-n", default=None, help="Filter ID (auto-generated if omitted).")
@click.pass_context
@pass_context
def add_relative_date_cmd(
    ctx: PbiContext,
    click_ctx: click.Context,
    page: str,
    table: str,
    column: str,
    amount: int,
    unit: str,
    visual: str | None,
    name: str | None,
) -> None:
    """Add a RelativeDate filter (e.g. last 3 months)."""
    from pbi_cli.core.filter_backend import filter_add_relative_date
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        filter_add_relative_date,
        definition_path=definition_path,
        page_name=page,
        table=table,
        column=column,
        amount=amount,
        time_unit=unit,
        visual_name=visual,
        name=name,
    )


@filters.command(name="add-advanced")
@click.option("--page", required=True, help="Page name (folder name, not display name).")
@click.option(
    "--measure",
    default=None,
    help="Measure to filter on, Table[Measure] notation (e.g. 'T[Valid Manager]').",
)
@click.option(
    "--column",
    default=None,
    help="Column to filter on, Table[Column] notation (alternative to --measure).",
)
@click.option(
    "--op",
    default="eq",
    show_default=True,
    help="Comparison operator: eq, neq, gt, gte, lt, lte.",
)
@click.option("--value", default="1", show_default=True, help="Comparison literal value.")
@click.option("--visual", default=None, help="Visual name (adds visual filter if given).")
@click.option("--name", "-n", default=None, help="Filter ID (auto-generated if omitted).")
@click.pass_context
@pass_context
def add_advanced_cmd(
    ctx: PbiContext,
    click_ctx: click.Context,
    page: str,
    measure: str | None,
    column: str | None,
    op: str,
    value: str,
    visual: str | None,
    name: str | None,
) -> None:
    """Add an Advanced comparison filter (measure/column vs literal).

    Examples:

      pbi filters add-advanced --page p1 --measure "T[Valid Manager (L2-L5 Only)]"

      pbi filters add-advanced --page p1 --column "Sales[Year]" --op gte --value 2024

      pbi filters add-advanced --page p1 --visual vis1 --measure "T[M]" --op eq --value 1
    """
    from pbi_cli.core.filter_backend import filter_add_advanced
    from pbi_cli.core.pbir_path import resolve_report_path
    from pbi_cli.core.visual_backend import parse_field_spec

    if (measure is None) == (column is None):
        raise click.UsageError("Provide exactly one of --measure or --column.")

    field_ref = measure if measure is not None else column
    assert field_ref is not None
    table, prop = parse_field_spec(field_ref)
    if not table or not prop:
        raise click.UsageError(f"Expected 'Table[Field]' notation, got '{field_ref}'.")

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        filter_add_advanced,
        definition_path=definition_path,
        page_name=page,
        table=table,
        property_name=prop,
        is_measure=measure is not None,
        op=op,
        value=value,
        visual_name=visual,
        name=name,
    )


@filters.command(name="remove")
@click.argument("filter_name")
@click.option("--page", required=True, help="Page name (folder name, not display name).")
@click.option("--visual", default=None, help="Visual name (removes from visual if given).")
@click.pass_context
@pass_context
def remove_cmd(
    ctx: PbiContext,
    click_ctx: click.Context,
    filter_name: str,
    page: str,
    visual: str | None,
) -> None:
    """Remove a filter by name from a page or visual."""
    from pbi_cli.core.filter_backend import filter_remove
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        filter_remove,
        definition_path=definition_path,
        page_name=page,
        filter_name=filter_name,
        visual_name=visual,
    )


@filters.command(name="clear")
@click.option("--page", required=True, help="Page name (folder name, not display name).")
@click.option("--visual", default=None, help="Visual name (clears visual filters if given).")
@click.pass_context
@pass_context
def clear_cmd(
    ctx: PbiContext,
    click_ctx: click.Context,
    page: str,
    visual: str | None,
) -> None:
    """Remove all filters from a page or visual."""
    from pbi_cli.core.filter_backend import filter_clear
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        filter_clear,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual,
    )
