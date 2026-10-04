"""CLI-level tests for `pbi static decode` / `pbi static encode`."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from pbi_cli.main import cli
from tests.test_static_table_backend import (
    FIXTURE_B64,
    FIXTURE_COLUMNS,
    FIXTURE_FIRST_ROW,
    FIXTURE_M,
)

_COLUMNS_SPEC = (
    "QuestionIndex:text,QuestionID:text,Question:text,Question Type:text,Theme Category:text"
)


def _invoke(cli_runner: CliRunner, args: list[str], **kwargs: object):
    return cli_runner.invoke(cli, args, **kwargs)


def test_static_help_lists_subcommands(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["static", "--help"])
    assert result.exit_code == 0
    assert "decode" in result.output
    assert "encode" in result.output


def test_decode_b64_json_bare(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["static", "decode", "--b64", FIXTURE_B64, "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["row_count"] == 27
    assert payload["format"] == "json"
    assert payload["rows"][0] == FIXTURE_FIRST_ROW


def test_decode_default_outputs_rows(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["static", "decode", "--b64", FIXTURE_B64])
    assert result.exit_code == 0
    rows = json.loads(result.output)
    assert isinstance(rows, list)
    assert len(rows) == 27


def test_decode_m_file_recovers_columns(cli_runner: CliRunner, tmp_path: Path) -> None:
    m_file = tmp_path / "questions.m"
    m_file.write_text(FIXTURE_M, encoding="utf-8")
    result = _invoke(cli_runner, ["static", "decode", f"@{m_file}", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["columns"] == FIXTURE_COLUMNS
    assert payload["rows"][0] == FIXTURE_FIRST_ROW


def test_decode_csv_flag(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["static", "decode", "--b64", FIXTURE_B64, "--csv"])
    assert result.exit_code == 0
    assert result.output.splitlines()[0].startswith("1,Q001,")


def test_decode_global_json(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["--json", "static", "decode", "--b64", FIXTURE_B64])
    assert result.exit_code == 0
    assert json.loads(result.output)["row_count"] == 27


def test_decode_stdin(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["static", "decode", "-", "--json"], input=FIXTURE_B64)
    assert result.exit_code == 0
    assert json.loads(result.output)["row_count"] == 27


def test_decode_out_writes_file(cli_runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "decoded.json"
    result = _invoke(
        cli_runner,
        ["static", "decode", "--b64", FIXTURE_B64, "--json", "--out", str(out)],
    )
    assert result.exit_code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["row_count"] == 27


def test_decode_missing_source_is_usage_error(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["static", "decode"])
    assert result.exit_code == 2


def test_decode_bad_payload_exits_nonzero(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["static", "decode", "not-a-static-table"])
    assert result.exit_code == 1


def test_encode_rows_roundtrips(cli_runner: CliRunner, tmp_path: Path) -> None:
    rows_file = tmp_path / "rows.json"
    rows = json.loads(_invoke(cli_runner, ["static", "decode", "--b64", FIXTURE_B64]).output)
    rows_file.write_text(json.dumps(rows), encoding="utf-8")

    result = _invoke(
        cli_runner,
        [
            "static",
            "encode",
            "--rows",
            f"@{rows_file}",
            "--columns",
            _COLUMNS_SPEC,
            "--template",
        ],
    )
    assert result.exit_code == 0
    expr = result.output.strip()
    assert expr.startswith("Table.FromRows(")
    assert "let _t = ((type nullable text) meta [Serialized.Text = true])" in expr

    # Pipe the emitted M back through decode.
    encoded_file = tmp_path / "encoded.m"
    encoded_file.write_text(expr, encoding="utf-8")
    decoded = _invoke(cli_runner, ["static", "decode", f"@{encoded_file}", "--json"])
    assert decoded.exit_code == 0
    payload = json.loads(decoded.output)
    assert payload["rows"] == rows
    assert payload["columns"] == FIXTURE_COLUMNS


def test_encode_base64_only(cli_runner: CliRunner, tmp_path: Path) -> None:
    rows_file = tmp_path / "rows.json"
    rows_file.write_text(json.dumps([["a", "b"]]), encoding="utf-8")
    result = _invoke(
        cli_runner,
        [
            "static",
            "encode",
            "--rows",
            f"@{rows_file}",
            "--columns",
            "A:text,B:text",
            "--base64-only",
        ],
    )
    assert result.exit_code == 0
    assert "Table.FromRows" not in result.output
    decoded = _invoke(cli_runner, ["static", "decode", "--b64", result.output.strip(), "--json"])
    assert json.loads(decoded.output)["rows"] == [["a", "b"]]


def test_encode_json_structured(cli_runner: CliRunner, tmp_path: Path) -> None:
    rows_file = tmp_path / "rows.json"
    rows_file.write_text(json.dumps([["a"]]), encoding="utf-8")
    result = _invoke(cli_runner, ["--json", "static", "encode", "--rows", f"@{rows_file}"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["base64"]
    assert payload["m_expression"].startswith("Table.FromRows(")


def test_encode_csv_form(cli_runner: CliRunner, tmp_path: Path) -> None:
    rows_file = tmp_path / "rows.json"
    rows_file.write_text(json.dumps([["a,b", 1], ["c", 2]]), encoding="utf-8")
    result = _invoke(
        cli_runner,
        [
            "static",
            "encode",
            "--rows",
            f"@{rows_file}",
            "--columns",
            "A:text,B:int",
            "--form",
            "csv",
        ],
    )
    assert result.exit_code == 0
    assert result.output.strip().startswith("Csv.Document(")
    encoded_file = tmp_path / "encoded_csv.m"
    encoded_file.write_text(result.output.strip(), encoding="utf-8")
    decoded = _invoke(cli_runner, ["static", "decode", f"@{encoded_file}", "--json"])
    assert json.loads(decoded.output)["rows"] == [["a,b", 1], ["c", 2]]


def test_encode_from_b64_file(cli_runner: CliRunner, tmp_path: Path) -> None:
    b64_file = tmp_path / "payload.b64"
    b64_file.write_text(FIXTURE_B64, encoding="utf-8")
    result = _invoke(
        cli_runner,
        ["static", "encode", "--b64-file", str(b64_file), "--columns", _COLUMNS_SPEC],
    )
    assert result.exit_code == 0
    assert result.output.strip().startswith("Table.FromRows(")


def test_encode_missing_input_is_usage_error(cli_runner: CliRunner) -> None:
    result = _invoke(cli_runner, ["static", "encode"])
    assert result.exit_code == 2
