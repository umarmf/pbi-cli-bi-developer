"""PBIR bookmark management commands."""

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
def bookmarks(ctx: click.Context, path: str | None, no_sync: bool) -> None:
    """Manage report bookmarks."""
    ctx.ensure_object(dict)
    ctx.obj["report_path"] = path
    ctx.obj["no_sync"] = no_sync


@bookmarks.command(name="list")
@click.pass_context
@pass_context
def list_bookmarks(ctx: PbiContext, click_ctx: click.Context) -> None:
    """List all bookmarks in the report."""
    from pbi_cli.core.bookmark_backend import bookmark_list
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(ctx, bookmark_list, definition_path=definition_path)


@bookmarks.command(name="get")
@click.argument("name")
@click.pass_context
@pass_context
def get_bookmark(ctx: PbiContext, click_ctx: click.Context, name: str) -> None:
    """Get full details for a bookmark by NAME."""
    from pbi_cli.core.bookmark_backend import bookmark_get
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(ctx, bookmark_get, definition_path=definition_path, name=name)


@bookmarks.command(name="add")
@click.option("--display-name", "-d", required=True, help="Human-readable bookmark name.")
@click.option("--page", "-g", required=True, help="Target page name (active section).")
@click.option("--name", "-n", default=None, help="Bookmark ID (auto-generated if omitted).")
@click.pass_context
@pass_context
def add_bookmark(
    ctx: PbiContext,
    click_ctx: click.Context,
    display_name: str,
    page: str,
    name: str | None,
) -> None:
    """Add a new bookmark pointing to a page."""
    from pbi_cli.core.bookmark_backend import bookmark_add
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        bookmark_add,
        definition_path=definition_path,
        display_name=display_name,
        target_page=page,
        name=name,
    )


@bookmarks.command(name="delete")
@click.argument("name")
@click.pass_context
@pass_context
def delete_bookmark(ctx: PbiContext, click_ctx: click.Context, name: str) -> None:
    """Delete a bookmark by NAME."""
    from pbi_cli.core.bookmark_backend import bookmark_delete
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(ctx, bookmark_delete, definition_path=definition_path, name=name)


@bookmarks.command(name="set-visibility")
@click.argument("name")
@click.option("--page", "-g", required=True, help="Page name (folder name).")
@click.option("--visual", "-v", required=True, help="Visual name (folder name).")
@click.option(
    "--hidden/--visible",
    default=True,
    help="Set the visual as hidden (default) or visible in the bookmark.",
)
@click.pass_context
@pass_context
def set_visibility(
    ctx: PbiContext,
    click_ctx: click.Context,
    name: str,
    page: str,
    visual: str,
    hidden: bool,
) -> None:
    """Set a visual hidden or visible inside bookmark NAME.

    NAME is the bookmark identifier (hex folder name).
    Use --hidden to hide the visual, --visible to show it.
    """
    from pbi_cli.core.bookmark_backend import bookmark_set_visibility
    from pbi_cli.core.pbir_path import resolve_report_path

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)
    run_command(
        ctx,
        bookmark_set_visibility,
        definition_path=definition_path,
        name=name,
        page_name=page,
        visual_name=visual,
        hidden=hidden,
    )


@bookmarks.command(name="set-scope")
@click.argument("name", required=False)
@click.option(
    "--all",
    "apply_all",
    is_flag=True,
    default=False,
    help="Apply to every bookmark in the report instead of a single NAME.",
)
@click.option(
    "--all-visuals",
    is_flag=True,
    default=False,
    help="Scope to all visuals (the Power BI default). This is the default scope.",
)
@click.option(
    "--visuals",
    default=None,
    help="Comma-separated visual IDs to target (selected-visuals scope).",
)
@click.option(
    "--data-visuals",
    is_flag=True,
    default=False,
    help="Scope to data visuals only (charts/tables/cards); excludes slicers, buttons and chrome.",
)
@click.option(
    "--suppress-data/--no-suppress-data",
    default=True,
    help="Uncheck/check the bookmark 'Data' setting (options.suppressData). "
    "Default --suppress-data keeps page filters from being saved/applied.",
)
@click.pass_context
@pass_context
def set_scope(
    ctx: PbiContext,
    click_ctx: click.Context,
    name: str | None,
    apply_all: bool,
    all_visuals: bool,
    visuals: str | None,
    data_visuals: bool,
    suppress_data: bool,
) -> None:
    """Change a bookmark's scope (All Visuals vs Selected Visuals) and its Data setting.

    NAME is the bookmark identifier (hex folder name). Use --all to target
    every bookmark.

    The recommended configuration for view-switch bookmarks is the default:
    all-visuals scope + "Data" unchecked (--suppress-data). It hides/shows every
    visual (navigation buttons included) without saving or re-applying filter
    state, so the time-period filter persists across bookmark clicks.

    \b
    Examples:
      pbi bookmarks set-scope <id>                        # all-visuals + no data (default)
      pbi bookmarks set-scope --all                       # same, every bookmark
      pbi bookmarks set-scope <id> --visuals a1b2,c3d4
      pbi bookmarks set-scope <id> --data-visuals
      pbi bookmarks set-scope <id> --no-suppress-data     # keep the Data setting
    """
    from pbi_cli.core.bookmark_backend import bookmark_list, bookmark_set_scope
    from pbi_cli.core.output import format_result
    from pbi_cli.core.pbir_path import resolve_report_path

    if not apply_all and not name:
        raise click.UsageError("Provide a bookmark NAME or use --all.")
    if apply_all and name:
        raise click.UsageError("Use either NAME or --all, not both.")

    report_path = click_ctx.parent.obj.get("report_path") if click_ctx.parent else None
    definition_path = resolve_report_path(report_path)

    visual_ids: list[str] | None = None
    if visuals is not None:
        visual_ids = [v.strip() for v in visuals.split(",") if v.strip()]

    if apply_all:
        names = [b["name"] for b in bookmark_list(definition_path)]
        if not names:
            raise click.UsageError("No bookmarks found in the report.")
        results = [
            bookmark_set_scope(
                definition_path,
                n,
                data_visuals=data_visuals,
                all_visuals=all_visuals,
                visuals=visual_ids,
                suppress_data=suppress_data,
            )
            for n in names
        ]
        if ctx.json_output:
            format_result(results, True)
        else:
            format_result(
                [
                    {
                        "bookmark": r["bookmark"],
                        "scope": r["scope"],
                        "suppress_data": r["suppress_data"],
                        "target_count": r["target_count"],
                    }
                    for r in results
                ],
                False,
            )
        return

    run_command(
        ctx,
        bookmark_set_scope,
        definition_path=definition_path,
        name=name,
        data_visuals=data_visuals,
        all_visuals=all_visuals,
        visuals=visual_ids,
        suppress_data=suppress_data,
    )
