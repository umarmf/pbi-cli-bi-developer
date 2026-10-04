"""Decode/encode Power BI "static" tables (Base64 + DEFLATE M payloads).

Static tables created with "Enter Data" or pasted from Excel/Sheets compile to
M that embeds the data as a Base64 string::

    Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText(
        "<base64>", BinaryEncoding.Base64), Compression.Deflate)), ...)

or, for larger pastes without a JSON layer::

    Csv.Document(Binary.Decompress(Binary.FromText(
        "<base64>", BinaryEncoding.Base64), Compression.Deflate),
        [Delimiter=",", Columns=N, Encoding=1252, QuoteStyle=QuoteStyle.None])

The payload pipeline is: Base64 -> **raw DEFLATE** (no zlib/gzip wrapper) ->
a JSON array-of-arrays (``Table.FromRows``) or CSV (``Csv.Document``).

This module is file-static: it never touches a live model or Power BI Desktop.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import re
import zlib
from typing import Any

__all__ = [
    "decode_static_table",
    "encode_static_table",
    "extract_base64",
    "parse_columns_spec",
    "parse_rows_text",
    "rows_to_csv",
]

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

# ``Binary.FromText("<base64>", BinaryEncoding.Base64)`` -- the captured string
# may contain newlines / arbitrary whitespace (DOTALL + [^"]*).
_FROM_TEXT_RE = re.compile(
    r'Binary\.FromText\s*\(\s*"([^"]*)"\s*,\s*BinaryEncoding\.Base64\s*\)',
    re.IGNORECASE | re.DOTALL,
)

# ``type table [A = _t, B = Int64.Type]`` -- non-greedy to the first ']'.
_TYPE_TABLE_RE = re.compile(r"type\s+table\s*\[(.*?)\]", re.IGNORECASE | re.DOTALL)

# ``let _t = ((type nullable text) meta [Serialized.Text = true])`` alias defs.
_ALIAS_DEF_RE = re.compile(
    r"(?P<name>[A-Za-z_]\w*)\s*=\s*\(*\(?\s*type\s+nullable\s+(?P<base>[A-Za-z0-9_.]+)",
    re.IGNORECASE,
)

_B64_CHARS_RE = re.compile(r"^[A-Za-z0-9+/=_-]+$")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# M reserved words that must be quoted when used as identifiers.
_RESERVED = frozenset(
    {
        "and",
        "as",
        "each",
        "else",
        "error",
        "false",
        "if",
        "in",
        "is",
        "let",
        "meta",
        "not",
        "null",
        "or",
        "otherwise",
        "section",
        "shared",
        "then",
        "true",
        "try",
        "type",
        "xor",
    }
)

# ---------------------------------------------------------------------------
# Type mapping
# ---------------------------------------------------------------------------

# M/DAX type literal (lowercased) -> canonical type name.
_TYPE_FROM_M: dict[str, str] = {
    "text": "text",
    "int64.type": "int",
    "int64": "int",
    "int": "int",
    "integer": "int",
    "number": "number",
    "double.type": "number",
    "single.type": "number",
    "decimal.type": "number",
    "currency.type": "number",
    "date": "date",
    "datetime": "datetime",
    "datetimezone": "datetime",
    "logical": "bool",
    "bool": "bool",
    "boolean": "bool",
    "any": "any",
}

# Canonical type name -> M type literal used when emitting a ``type table[...]``.
_TYPE_TO_M: dict[str, str] = {
    "text": "text",
    "int": "Int64.Type",
    "number": "number",
    "date": "date",
    "datetime": "datetime",
    "bool": "logical",
    "any": "any",
}

_DEFAULT_TYPE = "text"


# ---------------------------------------------------------------------------
# Public: payload extraction
# ---------------------------------------------------------------------------


def extract_base64(source: str) -> str:
    """Pull the Base64 payload out of an M expression, TMDL block, or bare string.

    Handles ``Binary.FromText("...", BinaryEncoding.Base64)`` (whitespace and
    line breaks inside the string are tolerated) and a bare Base64 string.
    """
    if source is None:
        raise ValueError("No source supplied.")

    match = _FROM_TEXT_RE.search(source)
    if match:
        b64 = _clean_b64(match.group(1))
        if not b64:
            raise ValueError("Binary.FromText(...) payload is empty.")
        return b64

    cleaned = _clean_b64(source)
    if cleaned and _is_base64(cleaned):
        return cleaned

    raise ValueError(
        "No Base64 payload found. Expected a Binary.FromText(...) M expression, "
        "a TMDL partition/expression source block, or a bare Base64 string."
    )


# ---------------------------------------------------------------------------
# Public: decode
# ---------------------------------------------------------------------------


def parse_rows_text(text: str) -> tuple[list[list[Any]], list[dict[str, str]]]:
    """Parse JSON array-of-arrays/objects or CSV text into rows + columns.

    Used by ``pbi static encode`` to read ``--rows`` input. JSON is detected by a
    leading ``[``/``{``; anything else is parsed as CSV (types inferred).
    """
    stripped = (text or "").lstrip()
    if stripped[:1] in ("[", "{"):
        return _rows_from_json(json.loads(text))
    rows = _read_csv_rows(text)
    columns = _infer_columns(rows)
    return [_coerce_row(row, columns) for row in rows], columns


def decode_static_table(source: str) -> dict[str, Any]:
    """Decode a static-table payload into rows + declared columns.

    Args:
        source: An M expression (``Table.FromRows`` / ``Csv.Document``), a TMDL
            ``source =`` block, or a bare Base64 string.

    Returns:
        Dict with ``format`` (``json`` | ``csv``), ``columns``
        (``[{"name", "type"}]``), ``rows`` (list of lists), ``row_count``,
        ``column_count`` and ``compression`` (how the payload was inflated).
    """
    b64 = extract_base64(source)
    raw = _b64decode(b64)
    data, compression = _decompress(raw)
    text = _to_text(data).strip()

    declared = _extract_type_table(source)

    if text[:1] in ("[", "{"):
        form = "json"
        rows, object_columns = _rows_from_json(json.loads(text))
        if declared:
            columns = declared
        elif object_columns:
            columns = object_columns
        else:
            columns = _default_columns(_row_width(rows))
    else:
        if not _looks_like_csv(text):
            raise ValueError(
                "Decoded payload is neither JSON nor CSV -- the input does not "
                "look like a static-table payload."
            )
        form = "csv"
        rows = _read_csv_rows(text)
        if declared:
            columns = declared
        else:
            columns = _infer_columns(rows)
        rows = [_coerce_row(row, columns) for row in rows]

    width = len(columns) or _row_width(rows)
    rows = [list(row) + [None] * (width - len(row)) for row in rows]

    return {
        "status": "success",
        "format": form,
        "compression": compression,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "column_count": len(columns),
    }


# ---------------------------------------------------------------------------
# Public: encode
# ---------------------------------------------------------------------------


def encode_static_table(
    rows: list[list[Any]],
    columns: list[dict[str, Any]] | list[str] | None = None,
    form: str = "auto",
    template: bool = False,
) -> dict[str, Any]:
    """Encode rows into a Base64 payload + paste-ready M expression.

    Args:
        rows: Row-major values (JSON-compatible; ``None`` becomes JSON null /
            an empty CSV cell).
        columns: ``[{"name", "type"}]``, a list of names, or ``None`` to
            generate ``Column1..N`` as text.
        form: ``json`` (``Table.FromRows``), ``csv`` (``Csv.Document``), or
            ``auto`` (currently resolves to ``json`` -- the lossless default).
        template: Reproduce the exact ``let _t = ((type nullable text) meta
            [Serialized.Text = true]) in type table [...]`` wrapper.

    Returns:
        Dict with ``base64``, ``m_expression``, ``form``, ``columns``,
        ``row_count`` and ``column_count``.
    """
    normalized = _normalize_columns(columns, rows)
    resolved = "csv" if form == "csv" else "json"

    if resolved == "json":
        payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), default=str)
        payload_bytes = payload.encode("utf-8")
        m_expression = _json_m_expression(_compress_b64(payload_bytes), normalized, template)
    else:
        payload_text = rows_to_csv(rows)
        payload_bytes, encoding_number = _encode_csv_bytes(payload_text)
        m_expression = _csv_m_expression(_compress_b64(payload_bytes), normalized, encoding_number)

    # Re-extract the payload we just built (single source of truth for base64).
    b64 = extract_base64(m_expression)

    return {
        "status": "success",
        "form": resolved,
        "base64": b64,
        "m_expression": m_expression,
        "columns": normalized,
        "rows": rows,
        "row_count": len(rows),
        "column_count": len(normalized),
    }


def parse_columns_spec(spec: str) -> list[dict[str, str]]:
    """Parse ``"Name:type,Name2:int"`` into ``[{"name", "type"}]``.

    A segment without ``:`` defaults to ``text``. Unknown types fall back to
    ``text`` as well.
    """
    columns: list[dict[str, str]] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, sep, raw_type = chunk.rpartition(":")
        if not sep or not name.strip():
            name, raw_type = chunk, _DEFAULT_TYPE
        columns.append({"name": name.strip(), "type": _normalize_type(raw_type)})
    return columns


# ---------------------------------------------------------------------------
# Public: CSV rendering (used by the decode --csv flag)
# ---------------------------------------------------------------------------


def rows_to_csv(rows: list[list[Any]]) -> str:
    """Render rows as CSV text (standard quoting, CRLF line endings)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    for row in rows:
        writer.writerow([_csv_cell(value) for value in row])
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Base64 / compression primitives
# ---------------------------------------------------------------------------


def _clean_b64(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _is_base64(text: str) -> bool:
    if not text or len(text) < 4 or not _B64_CHARS_RE.match(text):
        return False
    try:
        _b64decode(text)
        return True
    except Exception:  # noqa: BLE001 - any decode failure means "not base64"
        return False


def _b64decode(text: str) -> bytes:
    cleaned = re.sub(r"\s+", "", text).replace("-", "+").replace("_", "/")
    cleaned += "=" * ((-len(cleaned)) % 4)
    return base64.b64decode(cleaned, validate=True)


def _compress_b64(data: bytes) -> str:
    """Compress with raw DEFLATE (matches M ``Compression.Deflate``) and Base64 it."""
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(data) + compressor.flush()
    return base64.b64encode(compressed).decode("ascii")


def _decompress(data: bytes) -> tuple[bytes, str]:
    """Inflate a payload, trying raw DEFLATE first, then zlib, then gzip.

    Returns ``(bytes, compression_name)``. When none match, the original bytes
    are returned with ``compression == "none"`` (handles ``Compression.None``
    and uncompressed payloads).
    """
    for wbits, name in ((-15, "deflate"), (15, "zlib"), (31, "gzip")):
        try:
            return zlib.decompress(data, wbits), name
        except zlib.error:
            continue
    return data, "none"


def _to_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# M expression builders
# ---------------------------------------------------------------------------


def _json_m_expression(b64: str, columns: list[dict[str, str]], template: bool) -> str:
    type_clause = _type_clause(columns, template)
    return (
        "Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("
        f'"{b64}", BinaryEncoding.Base64), Compression.Deflate)), {type_clause})'
    )


def _csv_m_expression(b64: str, columns: list[dict[str, str]], encoding_number: int) -> str:
    return (
        "Csv.Document(Binary.Decompress(Binary.FromText("
        f'"{b64}", BinaryEncoding.Base64), Compression.Deflate), '
        f'[Delimiter=",", Columns={len(columns) or 1}, '
        f"Encoding={encoding_number}, QuoteStyle=QuoteStyle.Csv])"
    )


def _type_clause(columns: list[dict[str, str]], template: bool) -> str:
    parts: list[str] = []
    for column in columns:
        name = _format_identifier(column["name"])
        ctype = _normalize_type(column.get("type", _DEFAULT_TYPE))
        if template and ctype == _DEFAULT_TYPE:
            literal = "_t"
        else:
            literal = _TYPE_TO_M.get(ctype, _DEFAULT_TYPE)
        parts.append(f"{name} = {literal}")
    body = ", ".join(parts)
    if template:
        return (
            f"let _t = ((type nullable text) meta [Serialized.Text = true]) in type table [{body}]"
        )
    return f"type table [{body}]"


def _format_identifier(name: Any) -> str:
    text = str(name)
    if text and _IDENT_RE.match(text) and text.lower() not in _RESERVED:
        return text
    return '#"' + text.replace('"', '""') + '"'


def _encode_csv_bytes(text: str) -> tuple[bytes, int]:
    """Encode CSV payload bytes; prefer cp1252 (M ``Encoding=1252``), else UTF-8."""
    try:
        return text.encode("cp1252"), 1252
    except UnicodeEncodeError:
        return text.encode("utf-8"), 65001


# ---------------------------------------------------------------------------
# Type-table parsing
# ---------------------------------------------------------------------------


def _extract_type_table(source: str) -> list[dict[str, str]]:
    match = _TYPE_TABLE_RE.search(source or "")
    if not match:
        return []
    aliases = _extract_alias_types(source)
    columns: list[dict[str, str]] = []
    for entry in _split_top_level(match.group(1)):
        name, raw_type = _parse_type_entry(entry)
        if name:
            columns.append({"name": name, "type": _normalize_type(raw_type, aliases)})
    return columns


def _extract_alias_types(source: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for match in _ALIAS_DEF_RE.finditer(source or ""):
        aliases[match.group("name").lower()] = _TYPE_FROM_M.get(
            match.group("base").lower(), _DEFAULT_TYPE
        )
    return aliases


def _parse_type_entry(entry: str) -> tuple[str, str]:
    name, sep, rhs = _split_once_top_level(entry, "=")
    if not sep:
        return _unquote_identifier(entry.strip()), _DEFAULT_TYPE
    return _unquote_identifier(name.strip()), rhs.strip()


def _unquote_identifier(name: str) -> str:
    if name.startswith('#"') and name.endswith('"') and len(name) >= 3:
        return name[2:-1].replace('""', '"')
    return name


def _normalize_type(raw: str, aliases: dict[str, str] | None = None) -> str:
    text = (raw or "").strip()
    lowered = text.lower()
    # Drop a leading ``type`` and ``nullable`` qualifier.
    lowered = re.sub(r"^type\s+", "", lowered)
    lowered = re.sub(r"^nullable\s+", "", lowered)
    # Drop trailing metadata blocks such as ``meta [Serialized.Text = true]``.
    lowered = re.sub(r"\s*meta\s*\[.*$", "", lowered, flags=re.DOTALL).strip()
    if aliases and lowered in aliases:
        return aliases[lowered]
    return _TYPE_FROM_M.get(lowered, _DEFAULT_TYPE)


# ---------------------------------------------------------------------------
# Generic bracket/quote-aware tokenizer
# ---------------------------------------------------------------------------


def _split_top_level(text: str, separator: str = ",") -> list[str]:
    parts: list[str] = []
    buffer: list[str] = []
    depth = 0
    in_quote = False
    for char in text:
        if char == '"':
            in_quote = not in_quote
            buffer.append(char)
        elif in_quote:
            buffer.append(char)
        elif char in "([{":
            depth += 1
            buffer.append(char)
        elif char in ")]}":
            depth -= 1
            buffer.append(char)
        elif char == separator and depth == 0:
            parts.append("".join(buffer).strip())
            buffer = []
        else:
            buffer.append(char)
    tail = "".join(buffer).strip()
    if tail:
        parts.append(tail)
    return [part for part in parts if part]


def _split_once_top_level(text: str, separator: str) -> tuple[str, str, str]:
    depth = 0
    in_quote = False
    for index, char in enumerate(text):
        if char == '"':
            in_quote = not in_quote
        elif in_quote:
            continue
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == separator and depth == 0:
            return text[:index], char, text[index + 1 :]
    return text, "", ""


# ---------------------------------------------------------------------------
# JSON / CSV row parsing
# ---------------------------------------------------------------------------


def _rows_from_json(value: Any) -> tuple[list[list[Any]], list[dict[str, str]]]:
    if isinstance(value, list):
        if not value:
            return [], []
        if all(isinstance(item, dict) for item in value):
            keys = list(value[0].keys())
            columns = [
                {
                    "name": str(key),
                    "type": _infer_type([item.get(key) for item in value]),
                }
                for key in keys
            ]
            return [[item.get(key) for key in keys] for item in value], columns
        rows: list[list[Any]] = []
        for item in value:
            if isinstance(item, list):
                rows.append(list(item))
            elif isinstance(item, dict):
                rows.append([item.get(key) for key in item])
            else:
                rows.append([item])
        return rows, []
    if isinstance(value, dict):
        return [[value]], []
    return [[value]], []


def _read_csv_rows(text: str) -> list[list[str]]:
    if not text.strip():
        return []
    reader = csv.reader(io.StringIO(text))
    return [list(row) for row in reader]


def _looks_like_csv(text: str) -> bool:
    """Reject decompressed garbage that is not a plausible CSV payload."""
    if not text.strip():
        return True
    if not any(delimiter in text for delimiter in (",", "\t", "\n", "\r")):
        return False
    printable = sum(1 for char in text if char.isprintable() or char in "\r\n\t")
    return printable / len(text) > 0.95


def _infer_columns(rows: list[list[Any]]) -> list[dict[str, str]]:
    width = _row_width(rows)
    columns: list[dict[str, str]] = []
    for index in range(width):
        values = [row[index] if index < len(row) else None for row in rows]
        columns.append({"name": f"Column{index + 1}", "type": _infer_type(values)})
    return columns


def _infer_type(values: list[Any]) -> str:
    present = [value for value in values if value is not None and value != ""]
    if not present:
        return _DEFAULT_TYPE
    if all(isinstance(value, bool) for value in present):
        return "bool"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in present):
        return "int"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in present):
        return "number"
    return _infer_type_from_strings([str(value) for value in present])


def _infer_type_from_strings(values: list[str]) -> str:
    if all(value.lower() in ("true", "false") for value in values):
        return "bool"
    if all(re.fullmatch(r"[+-]?\d+", value) for value in values):
        return "int"
    if all(re.fullmatch(r"[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?", value) for value in values):
        return "number"
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) for value in values):
        return "date"
    return _DEFAULT_TYPE


def _coerce_row(row: list[Any], columns: list[dict[str, str]]) -> list[Any]:
    return [
        _coerce_value(
            row[index] if index < len(row) else None,
            columns[index]["type"] if index < len(columns) else _DEFAULT_TYPE,
        )
        for index in range(max(len(row), len(columns)))
    ]


def _coerce_value(value: Any, column_type: str) -> Any:
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    if text == "":
        return None
    if column_type == "int":
        try:
            return int(text)
        except ValueError:
            return text
    if column_type == "number":
        try:
            return float(text)
        except ValueError:
            return text
    if column_type == "bool":
        lowered = text.lower()
        if lowered in ("true", "1"):
            return True
        if lowered in ("false", "0"):
            return False
        return text
    return text


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _row_width(rows: list[list[Any]]) -> int:
    return max((len(row) for row in rows), default=0)


def _default_columns(count: int) -> list[dict[str, str]]:
    return [{"name": f"Column{index + 1}", "type": _DEFAULT_TYPE} for index in range(count)]


def _normalize_columns(
    columns: list[dict[str, Any]] | list[str] | None,
    rows: list[list[Any]],
) -> list[dict[str, str]]:
    if not columns:
        return _default_columns(_row_width(rows))
    normalized: list[dict[str, str]] = []
    for column in columns:
        if isinstance(column, str):
            normalized.append({"name": column, "type": _DEFAULT_TYPE})
        else:
            normalized.append(
                {
                    "name": str(column.get("name", "")),
                    "type": _normalize_type(str(column.get("type", _DEFAULT_TYPE))),
                }
            )
    return normalized


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
