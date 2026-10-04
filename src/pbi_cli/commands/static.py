"""Static-table decode/encode commands (file-static; no connection / Desktop)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import click

from pbi_cli.core.output import print_error, print_success
from pbi_cli.main import PbiContext, pass_context


@click.group()
def static() -> None:
    """Decode/encode Power BI static tables (Base64 + DEFLATE M payloads)."""


@static.command()
@click.argument("source", required=False, default=None)
@click.option("--b64", default=None, help="Base64 payload (alternative to <source>).")
@click.option(
    "--b64-file",
    default=None,
    type=click.Path(),
    help="Read the Base64 payload from a file.",
)
@click.option(
    "--json",
    "as_full",
    is_flag=True,
    default=False,
    help="Emit full structured JSON ({columns,rows,format}).",
)
@click.option(
    "--csv",
    "as_csv",
    is_flag=True,
    default=False,
    help="Emit decoded rows as CSV text.",
)
@click.option("--out", default=None, type=click.Path(), help="Write the decoded output to a file.")
@pass_context
def decode(
    ctx: PbiContext,
    source: str | None,
    b64: str | None,
    b64_file: str | None,
    as_full: bool,
    as_csv: bool,
    out: str | None,
) -> None:
    """Decode a static-table payload into rows.

    <source> may be @path/to/file.m, @path/to/model.tmdl, @- (stdin), or a
    literal Base64/M string. The default output is rows as a JSON
    array-of-arrays; --json adds the declared columns/format.
    """
    from pbi_cli.core.static_table_backend import decode_static_table, rows_to_csv

    if as_csv and (as_full or ctx.json_output):
        print_error("--csv cannot be combined with --json.")
        raise SystemExit(1)

    try:
        text = _resolve_payload_source(source, b64, b64_file)
        result = decode_static_table(text)
    except click.UsageError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface backend failures as CLI errors
        print_error(str(exc))
        raise SystemExit(1)

    if as_csv:
        output = rows_to_csv(result["rows"])
    elif as_full or ctx.json_output:
        output = json.dumps(result, indent=2, ensure_ascii=False, default=str)
    else:
        output = json.dumps(result["rows"], indent=2, ensure_ascii=False, default=str)

    _maybe_write(out, output)
    click.echo(output)


@static.command()
@click.option(
    "--rows",
    "rows_input",
    default=None,
    metavar="PATH",
    help="JSON array-of-arrays (or CSV) input; @path, @- for stdin.",
)
@click.option(
    "--b64-file",
    default=None,
    type=click.Path(),
    help="Re-encode from an existing Base64 payload file.",
)
@click.option(
    "--columns",
    default=None,
    help='Column types "Name:type,Name2:int" (text,int,number,date,datetime,bool,any).',
)
@click.option(
    "--form",
    "form",
    type=click.Choice(["json", "csv", "auto"]),
    default="auto",
    help="Payload form (auto resolves to json, the lossless default).",
)
@click.option(
    "--template",
    is_flag=True,
    default=False,
    help="Reproduce the exact let _t = ... type table wrapper.",
)
@click.option(
    "--base64-only",
    is_flag=True,
    default=False,
    help="Print only the Base64 payload.",
)
@click.option(
    "--out",
    default=None,
    type=click.Path(),
    help="Write the M expression (or Base64) to a file.",
)
@pass_context
def encode(
    ctx: PbiContext,
    rows_input: str | None,
    b64_file: str | None,
    columns: str | None,
    form: str,
    template: bool,
    base64_only: bool,
    out: str | None,
) -> None:
    """Encode rows into a paste-ready static-table M expression + Base64.

    Reads a JSON array-of-arrays (or CSV) and emits the M you paste into the
    Advanced Editor. Use --template for the exact Power BI type wrapper.
    """
    from pbi_cli.core.static_table_backend import (
        decode_static_table,
        encode_static_table,
        parse_columns_spec,
        parse_rows_text,
    )

    try:
        rows, derived_columns = _load_encode_rows(
            rows_input, b64_file, parse_rows_text, decode_static_table
        )
        resolved_columns = parse_columns_spec(columns) if columns else derived_columns
        result = encode_static_table(rows, columns=resolved_columns, form=form, template=template)
    except click.UsageError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface backend failures as CLI errors
        print_error(str(exc))
        raise SystemExit(1)

    if ctx.json_output:
        output = json.dumps(result, indent=2, ensure_ascii=False, default=str)
    elif base64_only:
        output = result["base64"]
    else:
        output = result["m_expression"]

    _maybe_write(out, output)
    click.echo(output)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_payload_source(source: str | None, b64: str | None, b64_file: str | None) -> str:
    provided = [value for value in (source, b64, b64_file) if value]
    if len(provided) > 1:
        raise click.UsageError("Provide only one of <source>, --b64, or --b64-file.")
    if b64_file:
        return Path(b64_file).read_text(encoding="utf-8-sig", errors="replace")
    if b64:
        return b64
    if source is None:
        raise click.UsageError("Missing <source> (or --b64 / --b64-file).")
    return _read_text_input(source)


def _read_text_input(value: str) -> str:
    if value == "-":
        return sys.stdin.read()
    if value.startswith("@"):
        path = value[1:]
        if path == "-":
            return sys.stdin.read()
        return Path(path).read_text(encoding="utf-8-sig", errors="replace")
    return value


def _load_encode_rows(
    rows_input: str | None,
    b64_file: str | None,
    parse_rows_text: object,
    decode_static_table: object,
) -> tuple[list[list[object]], list[dict[str, str]]]:
    if rows_input and b64_file:
        raise click.UsageError("Provide only one of --rows or --b64-file.")
    if b64_file:
        text = Path(b64_file).read_text(encoding="utf-8-sig", errors="replace")
        result = decode_static_table(text)  # type: ignore[operator]
        return cast(
            "tuple[list[list[object]], list[dict[str, str]]]",
            (result["rows"], result["columns"]),
        )
    if not rows_input:
        raise click.UsageError("Provide --rows (@file.json | @- | path) or --b64-file.")
    text = _read_text_input(rows_input)
    return cast(
        "tuple[list[list[object]], list[dict[str, str]]]",
        parse_rows_text(text),  # type: ignore[operator]
    )


def _maybe_write(out: str | None, output: str) -> None:
    if not out:
        return
    Path(out).write_text(output if output.endswith("\n") else output + "\n", encoding="utf-8")
    print_success(f"Wrote {out}")
