"""PBIR visual conditional formatting commands."""

from __future__ import annotations

import click

from pbi_cli.commands._helpers import run_command
from pbi_cli.main import PbiContext, pass_context


@click.group(name="format")
@click.option(
    "--report-path",
    default=None,
    help="Path to .Report folder (auto-detected from CWD if omitted).",
)
@click.pass_context
def format_cmd(ctx: click.Context, report_path: str | None) -> None:
    """Manage visual conditional formatting."""
    ctx.ensure_object(dict)
    ctx.obj["report_path"] = report_path


@format_cmd.command(name="get")
@click.argument("visual")
@click.option("--page", "-p", required=True, help="Page name (folder name, not display name).")
@click.pass_context
@pass_context
def format_get(ctx: PbiContext, click_ctx: click.Context, visual: str, page: str) -> None:
    """Show current formatting objects for a visual.

    VISUAL is the visual folder name (e.g. 5b30ba9c6ce5b695a8df).
    """
    from pbi_cli.core.format_backend import format_get as _format_get
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        _format_get,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual,
    )


@format_cmd.command(name="clear")
@click.argument("visual")
@click.option("--page", "-p", required=True, help="Page name (folder name, not display name).")
@click.pass_context
@pass_context
def format_clear(ctx: PbiContext, click_ctx: click.Context, visual: str, page: str) -> None:
    """Remove all conditional formatting from a visual.

    VISUAL is the visual folder name (e.g. 5b30ba9c6ce5b695a8df).
    """
    from pbi_cli.core.format_backend import format_clear as _format_clear
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        _format_clear,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual,
    )


@format_cmd.command(name="background-gradient")
@click.argument("visual")
@click.option("--page", "-p", required=True, help="Page name (folder name, not display name).")
@click.option("--input-table", required=True, help="Table name driving the gradient.")
@click.option("--input-column", required=True, help="Column name driving the gradient.")
@click.option(
    "--field",
    "field_query_ref",
    required=True,
    help='queryRef of the target field (e.g. "Sum(financials.Profit)").',
)
@click.option("--min-color", default="#FFFFFF", show_default=True, help="Gradient minimum color.")
@click.option("--max-color", default="#118DFF", show_default=True, help="Gradient maximum color.")
@click.pass_context
@pass_context
def background_gradient(
    ctx: PbiContext,
    click_ctx: click.Context,
    visual: str,
    page: str,
    input_table: str,
    input_column: str,
    field_query_ref: str,
    min_color: str,
    max_color: str,
) -> None:
    """Apply a linear gradient background color rule to a visual column.

    VISUAL is the visual folder name (e.g. 5b30ba9c6ce5b695a8df).

    Example:

      pbi format background-gradient MyVisual --page overview
        --input-table financials --input-column Profit
        --field "Sum(financials.Profit)"
    """
    from pbi_cli.core.format_backend import format_background_gradient
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        format_background_gradient,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual,
        input_table=input_table,
        input_column=input_column,
        field_query_ref=field_query_ref,
        min_color=min_color,
        max_color=max_color,
    )


@format_cmd.command(name="background-conditional")
@click.argument("visual")
@click.option("--page", "-p", required=True, help="Page name (folder name, not display name).")
@click.option("--input-table", required=True, help="Table containing the evaluated column.")
@click.option("--input-column", required=True, help="Column whose aggregation is tested.")
@click.option(
    "--threshold",
    type=float,
    required=True,
    help="Numeric threshold value to compare against.",
)
@click.option(
    "--color",
    "color_hex",
    required=True,
    help="Hex color to apply when condition is met (e.g. #12239E).",
)
@click.option(
    "--comparison",
    default="gt",
    show_default=True,
    help="Comparison: eq, neq, gt, gte, lt, lte.",
)
@click.option(
    "--field",
    "field_query_ref",
    default=None,
    help='queryRef of the target field. Defaults to "Sum(table.column)".',
)
@click.pass_context
@pass_context
def background_conditional(
    ctx: PbiContext,
    click_ctx: click.Context,
    visual: str,
    page: str,
    input_table: str,
    input_column: str,
    threshold: float,
    color_hex: str,
    comparison: str,
    field_query_ref: str | None,
) -> None:
    """Apply a rule-based conditional background color to a visual column.

    VISUAL is the visual folder name (e.g. 5b30ba9c6ce5b695a8df).
    Colors the cell when Sum(input_column) satisfies the comparison.

    Example:

      pbi format background-conditional MyVisual --page overview
        --input-table financials --input-column "Units Sold"
        --threshold 100000 --color "#12239E" --comparison gt
    """
    from pbi_cli.core.format_backend import format_background_conditional
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        format_background_conditional,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual,
        input_table=input_table,
        input_column=input_column,
        threshold=threshold,
        color_hex=color_hex,
        comparison=comparison,
        field_query_ref=field_query_ref,
    )


@format_cmd.command(name="background-measure")
@click.argument("visual")
@click.option("--page", "-p", required=True, help="Page name (folder name, not display name).")
@click.option("--measure-table", required=True, help="Table containing the color measure.")
@click.option(
    "--measure-property", required=True, help="Name of the DAX measure returning hex color."
)
@click.option(
    "--field",
    "field_query_ref",
    required=True,
    help='queryRef of the target field (e.g. "Sum(financials.Sales)").',
)
@click.pass_context
@pass_context
def background_measure(
    ctx: PbiContext,
    click_ctx: click.Context,
    visual: str,
    page: str,
    measure_table: str,
    measure_property: str,
    field_query_ref: str,
) -> None:
    """Apply a DAX measure-driven background color rule to a visual column.

    VISUAL is the visual folder name (e.g. 5b30ba9c6ce5b695a8df).
    The DAX measure must return a valid hex color string.

    Example:

      pbi format background-measure MyVisual --page overview
        --measure-table financials
        --measure-property "Conditional Formatting Sales"
        --field "Sum(financials.Sales)"
    """
    from pbi_cli.core.format_backend import format_background_measure
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        format_background_measure,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual,
        measure_table=measure_table,
        measure_property=measure_property,
        field_query_ref=field_query_ref,
    )


@format_cmd.command(name="set-object")
@click.argument("visual")
@click.option("--page", "-p", required=True, help="Page name (folder name, not display name).")
@click.option(
    "--object",
    "object_name",
    default=None,
    help="Visual-level object name (e.g. labels, valueAxis, categoryAxis). "
    "Ignored when --field is given.",
)
@click.option(
    "--property",
    "property_name",
    required=True,
    help="Property name (e.g. show, labelDisplayUnits, fontSize, scale).",
)
@click.option(
    "--value",
    default=None,
    help="Value, auto-encoded. Use 'true'/'false', '#RRGGBB', '10D', '0L', or plain text.",
)
@click.option(
    "--field",
    "field_query_ref",
    default=None,
    help="Per-field queryRef (e.g. '_Measures Table.Clicks'). Targets objects.values "
    "instead of a visual-level object.",
)
@click.option(
    "--kind",
    default=None,
    help="Force value encoding: bool | num | color | str (auto-detected by default).",
)
@click.option(
    "--remove",
    is_flag=True,
    default=False,
    help="Delete the property instead of setting it.",
)
@click.pass_context
@pass_context
def set_object(
    ctx: PbiContext,
    click_ctx: click.Context,
    visual: str,
    page: str,
    object_name: str | None,
    property_name: str,
    value: str | None,
    field_query_ref: str | None,
    kind: str | None,
    remove: bool,
) -> None:
    """Set (or remove) any visual objects property.

    VISUAL is the visual folder name (e.g. 5b30ba9c6ce5b695a8df).

    Two scopes, picked by the flags:

    * Visual-level: ``--object labels --property show --value false``
    * Per-field:    ``--field "T.Revenue" --property labelDisplayUnits --value 1000000D``

    Example (whole numbers on a count measure):

      pbi format set-object MyCard -p overview \\
        --field "_Measures Table.Clicks" --property labelDisplayUnits --value 1D
    """
    from pbi_cli.core.format_backend import format_set_object
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        format_set_object,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual,
        property_name=property_name,
        object_name=object_name,
        value=value,
        field_query_ref=field_query_ref,
        remove=remove,
        kind=kind,
    )


@format_cmd.command(name="display-units")
@click.argument("visual")
@click.option("--page", "-p", required=True, help="Page name (folder name, not display name).")
@click.option(
    "--field",
    "field_query_ref",
    required=True,
    help='queryRef of the field whose display units to change (e.g. "_Measures Table.Clicks").',
)
@click.option(
    "--units",
    required=True,
    help="none/thousands/millions/billions/auto, or an integer multiplier.",
)
@click.option(
    "--object",
    "object_name",
    default=None,
    help="Force a per-field container (auto-located by default; e.g. 'value' for cardVisual).",
)
@click.pass_context
@pass_context
def display_units(
    ctx: PbiContext,
    click_ctx: click.Context,
    visual: str,
    page: str,
    field_query_ref: str,
    units: str,
    object_name: str | None,
) -> None:
    """Set the display units (abbreviation) of a single visual field.

    VISUAL is the visual folder name. Display units are stored per-field,
    so --field (the field queryRef) is required. The container is
    auto-located (values/value); use --object to force it.

    Examples:

      pbi format display-units MyCard -p overview --field "_Measures Table.Clicks" --units none
      pbi format display-units MyCard -p overview --field "_Measures Table.Revenue" --units millions
    """
    from pbi_cli.core.format_backend import format_display_units
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        format_display_units,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual,
        field_query_ref=field_query_ref,
        units=units,
        object_name=object_name,
    )


@format_cmd.command(name="data-labels")
@click.argument("visual")
@click.option("--page", "-p", required=True, help="Page name (folder name, not display name).")
@click.option(
    "--show/--hide",
    default=True,
    help="Show (default) or hide data labels.",
)
@click.option(
    "--field",
    "field_query_ref",
    default=None,
    help="Limit to a single field queryRef (default: visual-level labels).",
)
@click.pass_context
@pass_context
def data_labels(
    ctx: PbiContext,
    click_ctx: click.Context,
    visual: str,
    page: str,
    show: bool,
    field_query_ref: str | None,
) -> None:
    """Show or hide data labels on a visual (or a single field).

    VISUAL is the visual folder name. Without --field this toggles the
    visual-level ``labels.show``; with --field it sets the per-field label.

    Examples:

      pbi format data-labels MyChart -p overview --hide
      pbi format data-labels MyChart -p overview --show --field "_Measures Table.Revenue"
    """
    from pbi_cli.core.format_backend import format_data_labels
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        format_data_labels,
        definition_path=definition_path,
        page_name=page,
        visual_name=visual,
        show=show,
        field_query_ref=field_query_ref,
    )
