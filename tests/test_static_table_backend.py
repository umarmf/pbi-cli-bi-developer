"""Tests for pbi_cli.core.static_table_backend (decode/encode of static tables).

Covers the real fixture payload, JSON+CSV round-trips, wrapper extraction
(bare Base64 / full M / TMDL source block), compression leniency, and edge
cases. No connection or Power BI Desktop is involved.
"""

from __future__ import annotations

import base64
import gzip
import json
import zlib

import pytest

from pbi_cli.core.static_table_backend import (
    decode_static_table,
    encode_static_table,
    extract_base64,
    parse_columns_spec,
    rows_to_csv,
)

# Real "Enter Data" table: 27 rows x 5 text columns.
FIXTURE_B64 = (
    "tVfbbtw2EP0VwkCBFlgEu86lTV8Mt3YRA0WzyRrwg5sHrjRasZZIlaR2o3x9z3CkXe3FsRu0Lx5bJOf"
    "MzJk5pO/vz2Znk7MP0ymbS0+qc63SG43fXKFc65WngrzXlWq8W3ldT9SmNFmJZXwPSqvz77AHJ/ILuLi"
    "ikHnTRLMm/PVxODuXs+qSPVsK4ezT5P7sXKDZ/KID5cpZxvdq6dyDsStFnxvyhmxGE1W6jarMA1Wd0n2"
    "c0QE5c3VNNldX2rZL4ihxJhoKvKxVwefh2avMVRXpVUsXajZVS2KA2oW49Yptw/fSrEp8aq2svUCEf8w"
    "X+Pm763QVO/Vni7jfqI8DvI7G2ZTUS0nq5bOS2ri2ylMuWelcoCGL+S4LvdLGqgIJJC+WPschyU41rc9"
    "KoChsuWqX2jAHC7LRIKjIIfSgfdwpwlcS4aujCEuUwK3Jf0vd5/9J3dP3b6n6a8np9fNyMkXKY0NICNE"
    "uW47CxRLbtqUdKrpHkrPB5NiFExxu4V39GGWHTLwbAhlT8UbCfnMU9toEE/+n/mcQrUKmqzTkU944m07"
    "UF/LudP8njmYHwyFLF/+CpB8lWzbH0dY6J1V32zHBUgahUKRD6oRTXX29rU/y/5P4Z3NlcgU+d/TrpnH"
    "GRnagon4AdKUzUjoouJCag901WcM7QlZS3lb0KIkL2YAgEvJbQX7bIzM5O+5QbMhenYoodKB6G6pQH6z"
    "FpLJQU5Mdwd31mw7ynE0TXDLv0BZ5D1kYj/EpSSPdpWsxSeFYkxeAyxLx+2I8k4sgmeTUiU+iqvfW689"
    "mOyPHzufD9NzUjYfngfmZSH0yY+fGCk2SvtL1Uiq2KanvceTfVBQp3xPRY+T34uHaro13NtUvAYscJ8P"
    "AAd0YCgN3wxBtTCz7iy40mG8oAsofVN56brGEypRg+9Caf+GbpU6OHo0/x/br4vI23X+9y1u4lHhEfJP"
    "5SjxcE43yhai5HCj4GrqTq2WXloAUMMSb0oHtqpHi7EWc9GMUySLqAoxvXUowoprJPBEMEHEF1SkaVxx"
    "JK2Ut8zAC3E7K9bAokKJ4yTwF2QsA4Gr9sM3MWBMNnhQ5NY41stGdDLX7KhXzfttcvEowIkjJPBHM362"
    "uDPp6yP1wDAaUof8/yH6BEV1KhmF294nXkfazWnmiyLm2Dau092atq+fKgqhQMo/hMCW6qvbUKZ64O07"
    "r0TBk+7jnIkfJ3EDqQt+6qCPXz9ifTzwMDwfjXOQnmZvANQcF2nZ8Hm+mKvSEpJz46mHCQ5keql6FdrU"
    "iaB8/k0zN40Ic8gn1k43Qpf4JKsKUzHupjVy1j/RCJ0qRcSs9QAJOPC9OD8F+xUSVkpnjUkZyiaKDTuM"
    "LNHUBdgzXqkZeJlH0febQHrnzYaIqt1x2E5SJ1jqmL6sOL/WgW6thNqau053qXPXD4WX6m85MJS7HXXs"
    "uSpXMOEYRxF37jEVw1EALvC7CaPj3MYfV/aqIHCXTIwrBaAO8DPELLqN8qbOHEeXMJAhZ4f+PrUScIIV"
    "PjGf2xdOdIUqVzF2JIeFImCCmvdAZlxl/Y8HYomoZpL+jcsoM33zD0/KoOCfuzeEdf4WBh7hLBCJPydx"
    "tZ1mzRMjbju8EpyJHjT5h+Rhd1E9SdKFuip1HPHN5I6QBoqPtirb+A/4zicf1uh3B3uEcqi9viU//AA=="
)

FIXTURE_COLUMNS = [
    {"name": "QuestionIndex", "type": "text"},
    {"name": "QuestionID", "type": "text"},
    {"name": "Question", "type": "text"},
    {"name": "Question Type", "type": "text"},
    {"name": "Theme Category", "type": "text"},
]

FIXTURE_FIRST_ROW = [
    "1",
    "Q001",
    "Are you aware of our referral program, which offers a 2% reward?",
    "Descriptive",
    "Referral Program Awareness",
]

# The exact M wrapper emitted by Power BI for an all-text static table.
FIXTURE_M = (
    "Source = Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("
    f'"{FIXTURE_B64}", BinaryEncoding.Base64), Compression.Deflate)), '
    "let _t = ((type nullable text) meta [Serialized.Text = true]) in "
    "type table [QuestionIndex = _t, QuestionID = _t, Question = _t, "
    '#"Question Type" = _t, #"Theme Category" = _t])'
)

FIXTURE_TMDL = (
    f"table Questions\n\tpartition Questions = m\n\t\tmode: import\n\t\tsource = {FIXTURE_M}\n"
)


def _m_with_type_table(type_table_body: str) -> str:
    """Wrap the fixture payload in a Table.FromRows with a custom type table."""
    return (
        "Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("
        f'"{FIXTURE_B64}", BinaryEncoding.Base64), Compression.Deflate)), '
        f"type table [{type_table_body}])"
    )


# ---------------------------------------------------------------------------
# Real fixture
# ---------------------------------------------------------------------------


def test_decode_fixture_from_m_expression() -> None:
    result = decode_static_table(FIXTURE_M)
    assert result["format"] == "json"
    assert result["compression"] == "deflate"
    assert result["columns"] == FIXTURE_COLUMNS
    assert result["row_count"] == 27
    assert result["column_count"] == 5
    assert result["rows"][0] == FIXTURE_FIRST_ROW
    assert result["rows"][-1][1] == "Q027"


def test_decode_fixture_bare_base64_has_rows() -> None:
    result = decode_static_table(FIXTURE_B64)
    assert result["row_count"] == 27
    assert result["rows"][0] == FIXTURE_FIRST_ROW
    # Bare Base64 carries no type table, so names are generated.
    assert result["columns"] == [{"name": f"Column{i}", "type": "text"} for i in range(1, 6)]


def test_decode_fixture_no_compression_variant() -> None:
    """A Compression.None payload is plain Base64 JSON (no inflate)."""
    payload = json.dumps([FIXTURE_FIRST_ROW], ensure_ascii=False).encode("utf-8")
    b64 = base64.b64encode(payload).decode("ascii")
    source = (
        'Table.FromRows(Json.Document(Binary.FromText("'
        f'{b64}", BinaryEncoding.Base64))), '
        "type table [QuestionIndex = text, QuestionID = text, Question = text, "
        '#"Question Type" = text, #"Theme Category" = text])'
    )
    result = decode_static_table(source)
    assert result["compression"] == "none"
    assert result["rows"] == [FIXTURE_FIRST_ROW]


def test_roundtrip_fixture_json() -> None:
    decoded = decode_static_table(FIXTURE_M)
    encoded = encode_static_table(
        decoded["rows"], columns=decoded["columns"], form="json", template=True
    )
    again = decode_static_table(encoded["m_expression"])
    assert again["rows"] == decoded["rows"]
    assert again["columns"] == decoded["columns"]


# ---------------------------------------------------------------------------
# Fresh encode -> decode (mixed types)
# ---------------------------------------------------------------------------

_FRESH_ROWS = [
    ['a,b"c\nd', 1, 3.14, "2024-01-15", True, None],
    ["plain", 42, -0.5, "1999-12-31", False, None],
]
_FRESH_COLUMNS = [
    {"name": "Text Col", "type": "text"},
    {"name": "Int Col", "type": "int"},
    {"name": "Num Col", "type": "number"},
    {"name": "Date Col", "type": "date"},
    {"name": "Bool Col", "type": "bool"},
    {"name": "Any Col", "type": "any"},
]


def test_encode_fresh_json_roundtrip_preserves_columns_and_types() -> None:
    encoded = encode_static_table(_FRESH_ROWS, columns=_FRESH_COLUMNS, form="json", template=True)
    assert encoded["base64"]
    assert encoded["row_count"] == 2
    decoded = decode_static_table(encoded["m_expression"])
    assert decoded["format"] == "json"
    assert decoded["columns"] == _FRESH_COLUMNS
    assert decoded["rows"] == _FRESH_ROWS


def test_encode_fresh_csv_roundtrip_preserves_values() -> None:
    encoded = encode_static_table(_FRESH_ROWS, columns=_FRESH_COLUMNS, form="csv")
    decoded = decode_static_table(encoded["m_expression"])
    assert decoded["format"] == "csv"
    assert decoded["row_count"] == 2
    assert decoded["rows"] == _FRESH_ROWS


def test_csv_encoding_quotes_special_characters() -> None:
    encoded = encode_static_table(_FRESH_ROWS, columns=_FRESH_COLUMNS, form="csv")
    payload_b64 = encoded["base64"]
    raw = zlib.decompress(base64.b64decode(payload_b64), -15).decode("cp1252")
    # The comma/quote/newline cell must be quoted with doubled inner quotes.
    assert '"a,b""c' in raw
    decoded = decode_static_table(encoded["m_expression"])
    assert decoded["rows"][0][0] == 'a,b"c\nd'


def test_encode_template_wrapper_is_exact() -> None:
    encoded = encode_static_table(_FRESH_ROWS, columns=_FRESH_COLUMNS, form="json", template=True)
    expr = encoded["m_expression"]
    assert expr.startswith("Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText(")
    assert "let _t = ((type nullable text) meta [Serialized.Text = true]) in type table [" in expr
    # text -> _t, others -> their literal; names with spaces are quoted.
    assert '#"Text Col" = _t' in expr
    assert '#"Int Col" = Int64.Type' in expr
    assert '#"Num Col" = number' in expr
    assert '#"Bool Col" = logical' in expr
    assert '#"Any Col" = any' in expr


def test_encode_always_uses_raw_deflate() -> None:
    encoded = encode_static_table(_FRESH_ROWS, columns=_FRESH_COLUMNS, form="json")
    raw = base64.b64decode(encoded["base64"])
    payload = zlib.decompress(raw, -15).decode("utf-8")
    assert json.loads(payload) == json.loads(json.dumps(_FRESH_ROWS))


def test_json_encoding_emits_typed_literals() -> None:
    encoded = encode_static_table([[1, 2.5, True, None]], columns=["A", "B", "C", "D"], form="json")
    payload = zlib.decompress(base64.b64decode(encoded["base64"]), -15).decode("utf-8")
    assert payload == "[[1,2.5,true,null]]"


# ---------------------------------------------------------------------------
# Wrapper extraction
# ---------------------------------------------------------------------------


def test_extract_all_wrapper_variants() -> None:
    assert extract_base64(FIXTURE_B64) == FIXTURE_B64
    assert FIXTURE_B64 in extract_base64(FIXTURE_M)
    assert FIXTURE_B64 in extract_base64(FIXTURE_TMDL)


def test_decode_full_m_and_tmdl_match_bare_rows() -> None:
    bare = decode_static_table(FIXTURE_B64)
    from_m = decode_static_table(FIXTURE_M)
    from_tmdl = decode_static_table(FIXTURE_TMDL)
    assert from_m["rows"] == bare["rows"]
    assert from_tmdl["rows"] == bare["rows"]
    assert from_tmdl["columns"] == FIXTURE_COLUMNS


def test_base64_with_injected_whitespace() -> None:
    broken = "\n".join(FIXTURE_B64[i : i + 40] for i in range(0, len(FIXTURE_B64), 40))
    assert extract_base64(broken) == FIXTURE_B64
    assert decode_static_table(broken)["row_count"] == 27
    # whitespace inside the M string literal too
    spaced_m = FIXTURE_M.replace(FIXTURE_B64, FIXTURE_B64[:100] + "\n\t  " + FIXTURE_B64[100:])
    assert decode_static_table(spaced_m)["row_count"] == 27


def test_extract_raises_on_garbage() -> None:
    with pytest.raises(ValueError):
        extract_base64("this is not a static table")


# ---------------------------------------------------------------------------
# Compression leniency
# ---------------------------------------------------------------------------


def _wrapped(payload_bytes: bytes, compressor) -> str:
    b64 = base64.b64encode(compressor(payload_bytes)).decode("ascii")
    return (
        "Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("
        f'"{b64}", BinaryEncoding.Base64), Compression.Deflate)), '
        "type table [QuestionIndex = text, QuestionID = text, Question = text, "
        '#"Question Type" = text, #"Theme Category" = text])'
    )


@pytest.mark.parametrize(
    ("compressor", "expected"),
    [
        (lambda b: zlib.compress(b), "zlib"),
        (gzip.compress, "gzip"),
    ],
)
def test_decompress_falls_back_to_zlib_and_gzip(compressor, expected: str) -> None:
    source = _wrapped(json.dumps([FIXTURE_FIRST_ROW]).encode("utf-8"), compressor)
    result = decode_static_table(source)
    assert result["compression"] == expected
    assert result["rows"] == [FIXTURE_FIRST_ROW]


# ---------------------------------------------------------------------------
# CSV variant (Csv.Document)
# ---------------------------------------------------------------------------


def test_decode_csv_document_variant() -> None:
    decoded = decode_static_table(FIXTURE_M)
    encoded = encode_static_table(decoded["rows"], columns=decoded["columns"], form="csv")
    expr = (
        "Csv.Document(Binary.Decompress(Binary.FromText("
        f'"{encoded["base64"]}", BinaryEncoding.Base64), Compression.Deflate), '
        '[Delimiter=",", Columns=5, Encoding=1252, QuoteStyle=QuoteStyle.None])'
    )
    result = decode_static_table(expr)
    assert result["format"] == "csv"
    assert result["row_count"] == 27
    assert [str(value) for value in result["rows"][0]] == FIXTURE_FIRST_ROW


# ---------------------------------------------------------------------------
# Type mapping / edge cases
# ---------------------------------------------------------------------------


def test_type_mapping_from_type_table() -> None:
    source = _m_with_type_table(
        "A = Int64.Type, B = number, C = Double.Type, D = date, "
        "E = datetime, F = logical, G = any, H = text"
    )
    columns = decode_static_table(source)["columns"]
    assert [c["type"] for c in columns] == [
        "int",
        "number",
        "number",
        "date",
        "datetime",
        "bool",
        "any",
        "text",
    ]


def test_unknown_column_type_falls_back_to_text() -> None:
    source = _m_with_type_table("A = SomeUnknown.Type, B = text")
    columns = decode_static_table(source)["columns"]
    assert [c["type"] for c in columns] == ["text", "text"]


def test_empty_table_json_roundtrip() -> None:
    encoded = encode_static_table([], columns=[{"name": "A", "type": "text"}], form="json")
    decoded = decode_static_table(encoded["m_expression"])
    assert decoded["row_count"] == 0
    assert decoded["columns"] == [{"name": "A", "type": "text"}]


def test_empty_table_csv_decodes_without_rows() -> None:
    encoded = encode_static_table([], columns=[{"name": "A", "type": "text"}], form="csv")
    decoded = decode_static_table(encoded["m_expression"])
    assert decoded["row_count"] == 0
    assert decoded["format"] == "csv"


def test_quoted_column_names_roundtrip() -> None:
    columns = [{"name": "Question Type", "type": "text"}, {"name": "type", "type": "text"}]
    encoded = encode_static_table([["x", "y"]], columns=columns, form="json", template=True)
    assert '#"Question Type" = _t' in encoded["m_expression"]
    assert '#"type" = _t' in encoded["m_expression"]
    decoded = decode_static_table(encoded["m_expression"])
    assert decoded["columns"] == columns


def test_parse_columns_spec() -> None:
    parsed = parse_columns_spec("A:text, B:int, C, D:number")
    assert parsed == [
        {"name": "A", "type": "text"},
        {"name": "B", "type": "int"},
        {"name": "C", "type": "text"},
        {"name": "D", "type": "number"},
    ]


def test_rows_to_csv_roundtrips_through_parser() -> None:
    csv_text = rows_to_csv([["a,b", 1, True, None], ["x", 2, False, None]])
    assert csv_text.startswith('"a,b",1,true,')
    from pbi_cli.core.static_table_backend import parse_rows_text

    rows, columns = parse_rows_text(csv_text)
    assert rows == [["a,b", 1, True, None], ["x", 2, False, None]]
    assert [c["type"] for c in columns] == ["text", "int", "bool", "text"]
