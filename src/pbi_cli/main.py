"""Main CLI entry point for pbi-cli."""

from __future__ import annotations

import click

from pbi_cli import __version__


class PbiContext:
    """Shared context passed to all CLI commands."""

    def __init__(
        self,
        json_output: bool = False,
        connection: str | None = None,
        repl_mode: bool = False,
    ) -> None:
        self.json_output = json_output
        self.connection = connection
        self.repl_mode = repl_mode


pass_context = click.make_pass_decorator(PbiContext, ensure=True)


@click.group(invoke_without_command=True)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Output raw JSON for agent consumption.",
)
@click.option(
    "--connection", "-c", default=None, help="Named connection to use (defaults to last-used)."
)
@click.version_option(version=__version__, prog_name="pbi-cli")
@click.pass_context
def cli(ctx: click.Context, json_output: bool, connection: str | None) -> None:
    """pbi-cli: Power BI semantic model CLI.

    Connects directly to Power BI Desktop's Analysis Services engine
    for token-efficient usage with Claude Code and other AI agents.

    Run 'pbi connect' to auto-detect a running Power BI Desktop instance.
    """
    ctx.ensure_object(PbiContext)
    ctx.obj = PbiContext(json_output=json_output, connection=connection)

    if ctx.invoked_subcommand is None and not json_output:
        from pbi_cli.core.banner import print_banner

        print_banner(__version__)
        click.echo(ctx.get_help())


def _register_commands() -> None:
    """Lazily import and register all command groups."""
    from pbi_cli.commands.advanced import advanced
    from pbi_cli.commands.bookmarks import bookmarks
    from pbi_cli.commands.calc_group import calc_group
    from pbi_cli.commands.calendar import calendar
    from pbi_cli.commands.column import column
    from pbi_cli.commands.connection import connect, connections, disconnect
    from pbi_cli.commands.database import database
    from pbi_cli.commands.dax import dax
    from pbi_cli.commands.desktop import desktop
    from pbi_cli.commands.expression import expression
    from pbi_cli.commands.filters import filters
    from pbi_cli.commands.format_cmd import format_cmd
    from pbi_cli.commands.hierarchy import hierarchy
    from pbi_cli.commands.measure import measure
    from pbi_cli.commands.model import model
    from pbi_cli.commands.partition import partition
    from pbi_cli.commands.perspective import perspective
    from pbi_cli.commands.relationship import relationship
    from pbi_cli.commands.repl_cmd import repl
    from pbi_cli.commands.report import report
    from pbi_cli.commands.security import security_role
    from pbi_cli.commands.setup_cmd import setup
    from pbi_cli.commands.static import static
    from pbi_cli.commands.table import table
    from pbi_cli.commands.trace import trace
    from pbi_cli.commands.transaction import transaction
    from pbi_cli.commands.visual import visual

    cli.add_command(setup)
    cli.add_command(desktop)
    cli.add_command(connect)
    cli.add_command(disconnect)
    cli.add_command(connections)
    cli.add_command(dax)
    cli.add_command(measure)
    cli.add_command(table)
    cli.add_command(column)
    cli.add_command(relationship)
    cli.add_command(model)
    cli.add_command(database)
    cli.add_command(security_role)
    cli.add_command(calc_group)
    cli.add_command(partition)
    cli.add_command(perspective)
    cli.add_command(hierarchy)
    cli.add_command(expression)
    cli.add_command(calendar)
    cli.add_command(trace)
    cli.add_command(transaction)
    cli.add_command(advanced)
    cli.add_command(repl)
    cli.add_command(report)
    cli.add_command(visual)
    cli.add_command(filters)
    cli.add_command(format_cmd)
    cli.add_command(bookmarks)
    cli.add_command(static)


_register_commands()
