"""Pure-function backend for PBIR filter operations.

Every function takes a ``Path`` to the definition folder and returns a plain
Python dict suitable for ``format_result()``.

Filters are stored in ``filterConfig.filters[]`` inside either:
- ``pages/<page_name>/page.json`` for page-level filters
- ``pages/<page_name>/visuals/<visual_name>/visual.json`` for visual-level filters
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from pbi_cli.core.errors import PbiCliError
from pbi_cli.core.pbir_path import get_page_dir, get_visual_dir
from pbi_cli.core.visual_backend import parse_field_spec

# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    """Read and parse a JSON file."""
    result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return result


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON with consistent formatting."""
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _generate_name() -> str:
    """Generate a 20-character hex identifier matching PBIR convention."""
    return secrets.token_hex(10)


# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------


def _resolve_target_path(
    definition_path: Path,
    page_name: str,
    visual_name: str | None,
) -> Path:
    """Return the JSON file path for the target (page or visual)."""
    if visual_name is None:
        return get_page_dir(definition_path, page_name) / "page.json"
    return get_visual_dir(definition_path, page_name, visual_name) / "visual.json"


def _get_filters(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the filters list from a page or visual JSON dict."""
    filter_config = data.get("filterConfig")
    if not isinstance(filter_config, dict):
        return []
    filters = filter_config.get("filters")
    if not isinstance(filters, list):
        return []
    return filters


def _set_filters(data: dict[str, Any], filters: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a new dict with filterConfig.filters replaced (immutable update)."""
    filter_config = dict(data.get("filterConfig") or {})
    filter_config["filters"] = filters
    return {**data, "filterConfig": filter_config}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def filter_list(
    definition_path: Path,
    page_name: str,
    visual_name: str | None = None,
    summarize: bool = False,
) -> list[dict[str, Any]]:
    """List filters on a page or specific visual.

    If visual_name is None, returns page-level filters from page.json.
    If visual_name is given, returns visual-level filters from visual.json.
    Returns the raw filter dicts from filterConfig.filters[], or a summarized
    view (``{"name", "type", "field", "condition"}``) when *summarize* is set.
    """
    target = _resolve_target_path(definition_path, page_name, visual_name)
    if not target.exists():
        raise PbiCliError(f"File not found: {target}")
    data = _read_json(target)
    filters = _get_filters(data)
    if summarize:
        return [_summarize_filter(f) for f in filters]
    return filters


# ---------------------------------------------------------------------------
# Filter inspection helpers
# ---------------------------------------------------------------------------

# ComparisonKind integer codes used by Power BI Advanced/Comparison filters.
_COMPARISON_KINDS: dict[str, int] = {
    "eq": 0,
    "neq": 1,
    "gt": 2,
    "gte": 3,
    "lt": 4,
    "lte": 5,
}

_COMPARISON_KINDS_REV: dict[int, str] = {v: k for k, v in _COMPARISON_KINDS.items()}


def _filter_field_ref(f: dict[str, Any]) -> tuple[str, str, str]:
    """Return ``(kind, entity, property)`` for a filter's ``field`` block."""
    field = f.get("field", {})
    for kind in ("Measure", "Column", "Aggregation"):
        if kind in field:
            item = field[kind]
            source_ref = item.get("Expression", {}).get("SourceRef", {})
            entity = source_ref.get("Entity", source_ref.get("Source", ""))
            prop = item.get("Property", "")
            return kind, entity or "", prop or ""
    return "", "", ""


def _summarize_filter(f: dict[str, Any]) -> dict[str, Any]:
    """Produce a human-readable summary of a raw filter dict."""
    kind, entity, prop = _filter_field_ref(f)
    field_str = f"{entity}[{prop}]" if entity else prop
    ftype = f.get("type", "")
    name = f.get("name", "")
    body = f.get("filter", {})
    condition = ""

    where = body.get("Where", [])
    if where:
        cond = where[0].get("Condition", {})
        if "Comparison" in cond:
            cmp_ = cond["Comparison"]
            op = _COMPARISON_KINDS_REV.get(cmp_.get("ComparisonKind"), "?")
            val = cmp_.get("Right", {}).get("Literal", {}).get("Value", "")
            condition = f"{op} {val}"
        elif "In" in cond:
            in_ = cond["In"]
            values = in_.get("Values", [])
            if values:
                vals = [
                    v[0].get("Literal", {}).get("Value", "")
                    if isinstance(v, list) and v
                    else str(v)
                    for v in values
                ]
                condition = "in [" + ", ".join(vals) + "]"
            elif "Table" in in_:
                condition = "in (subquery)"
        elif "Between" in cond:
            condition = "between (relative date)"

    if not condition and ftype == "TopN":
        subq = body.get("From", [{}])[0].get("Expression", {}).get("Subquery", {}).get("Query", {})
        condition = f"top {subq.get('Top', '')}"
    if not condition and ftype == "RelativeDate":
        condition = "relative date"

    return {"name": name, "type": ftype, "field": field_str, "condition": condition}


def filter_where(
    definition_path: Path,
    page_name: str,
    field_specs: list[str],
    visual_name: str | None = None,
    type_filter: str | None = None,
    summarize: bool = False,
) -> list[dict[str, Any]]:
    """Return filters on a page/visual whose field matches any *field_specs*.

    *field_specs* are ``Table[Field]`` or bare ``Field`` strings. A bare spec
    matches on property alone. *type_filter* optionally restricts to a filter
    type (``Categorical``, ``TopN``, ``RelativeDate``, ``Advanced``).
    """
    target = _resolve_target_path(definition_path, page_name, visual_name)
    if not target.exists():
        raise PbiCliError(f"File not found: {target}")
    data = _read_json(target)
    filters = _get_filters(data)

    result: list[dict[str, Any]] = []
    for f in filters:
        if type_filter is not None and f.get("type") != type_filter:
            continue
        _, entity, prop = _filter_field_ref(f)
        for spec in field_specs:
            spec_table, spec_prop = parse_field_spec(spec)
            if (not spec_table or entity == spec_table) and prop == spec_prop:
                result.append(_summarize_filter(f) if summarize else f)
                break
    return result


def _to_pbi_literal(value: str) -> str:
    """Convert a CLI string value to a Power BI literal.

    Power BI uses typed literals: strings are single-quoted (``'text'``),
    integers use an ``L`` suffix (``123L``), and doubles use ``D`` (``1.5D``).
    """
    # Try integer first (e.g. "2014" -> "2014L")
    try:
        int(value)
        return f"{value}L"
    except ValueError:
        pass
    # Try float (e.g. "3.14" -> "3.14D")
    try:
        float(value)
        return f"{value}D"
    except ValueError:
        pass
    # Fall back to string literal
    return f"'{value}'"


def filter_add_categorical(
    definition_path: Path,
    page_name: str,
    table: str,
    column: str,
    values: list[str],
    visual_name: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Add a categorical filter to a page or visual.

    Builds the full filterConfig entry from table/column/values.
    The source alias is always the first letter of the table name (lowercase).
    Returns a status dict with name, type, and scope.
    """
    target = _resolve_target_path(definition_path, page_name, visual_name)
    if not target.exists():
        raise PbiCliError(f"File not found: {target}")

    filter_name = name if name is not None else _generate_name()
    alias = table[0].lower()
    scope = "visual" if visual_name is not None else "page"

    where_values: list[list[dict[str, Any]]] = [
        [{"Literal": {"Value": _to_pbi_literal(v)}}] for v in values
    ]

    entry: dict[str, Any] = {
        "name": filter_name,
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": table}},
                "Property": column,
            }
        },
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": table, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "In": {
                            "Expressions": [
                                {
                                    "Column": {
                                        "Expression": {"SourceRef": {"Source": alias}},
                                        "Property": column,
                                    }
                                }
                            ],
                            "Values": where_values,
                        }
                    }
                }
            ],
        },
    }

    if scope == "page":
        entry["howCreated"] = "User"

    data = _read_json(target)
    filters = list(_get_filters(data))
    filters.append(entry)
    updated = _set_filters(data, filters)
    _write_json(target, updated)

    return {"status": "added", "name": filter_name, "type": "Categorical", "scope": scope}


def filter_add_advanced(
    definition_path: Path,
    page_name: str,
    table: str,
    property_name: str,
    is_measure: bool = True,
    op: str = "eq",
    value: str = "1",
    visual_name: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Add an Advanced (measure/column comparison) filter to a page or visual.

    Builds a Comparison filter of the form ``<field> <op> <value>`` (e.g.
    ``'Manager Level Selector'[Valid Manager (L2-L5 Only)] = 1``). This is the
    generic "Advanced filtering" shape Power BI Desktop emits for measure
    filters -- there is no dedicated ``add-categorical``/``add-topn`` command
    for it.

    *table* / *property_name* name the field; *is_measure* chooses a Measure
    vs Column reference. *op* is one of ``eq``, ``neq``, ``gt``, ``gte``,
    ``lt``, ``lte``. *value* is encoded as a PBI literal (integers get an
    ``L`` suffix, floats a ``D`` suffix, anything else single-quoted).

    Returns a status dict with name, type, scope, op, and value.
    """
    op_lower = op.strip().lower()
    if op_lower not in _COMPARISON_KINDS:
        valid = ", ".join(_COMPARISON_KINDS)
        raise PbiCliError(f"op must be one of {valid}, got '{op}'.")

    target = _resolve_target_path(definition_path, page_name, visual_name)
    if not target.exists():
        raise PbiCliError(f"File not found: {target}")

    filter_name = name if name is not None else _generate_name()
    alias = table[0].lower()
    scope = "visual" if visual_name is not None else "page"
    kind_key = "Measure" if is_measure else "Column"

    entry: dict[str, Any] = {
        "name": filter_name,
        "field": {
            kind_key: {
                "Expression": {"SourceRef": {"Entity": table}},
                "Property": property_name,
            }
        },
        "type": "Advanced",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": table, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "Comparison": {
                            "ComparisonKind": _COMPARISON_KINDS[op_lower],
                            "Left": {
                                kind_key: {
                                    "Expression": {"SourceRef": {"Source": alias}},
                                    "Property": property_name,
                                }
                            },
                            "Right": {"Literal": {"Value": _to_pbi_literal(value)}},
                        }
                    }
                }
            ],
        },
    }

    if scope == "page":
        entry["howCreated"] = "User"

    data = _read_json(target)
    filters = list(_get_filters(data))
    filters.append(entry)
    updated = _set_filters(data, filters)
    _write_json(target, updated)

    return {
        "status": "added",
        "name": filter_name,
        "type": "Advanced",
        "scope": scope,
        "op": op_lower,
        "value": value,
    }


def filter_remove(
    definition_path: Path,
    page_name: str,
    filter_name: str,
    visual_name: str | None = None,
) -> dict[str, Any]:
    """Remove a filter by name from a page or visual.

    Raises PbiCliError if filter_name is not found.
    Returns a status dict with the removed filter name.
    """
    target = _resolve_target_path(definition_path, page_name, visual_name)
    if not target.exists():
        raise PbiCliError(f"File not found: {target}")

    data = _read_json(target)
    filters = _get_filters(data)
    remaining = [f for f in filters if f.get("name") != filter_name]

    if len(remaining) == len(filters):
        raise PbiCliError(
            f"Filter '{filter_name}' not found on "
            f"{'visual ' + visual_name if visual_name else 'page'} '{page_name}'."
        )

    updated = _set_filters(data, remaining)
    _write_json(target, updated)
    return {"status": "removed", "name": filter_name}


def filter_add_topn(
    definition_path: Path,
    page_name: str,
    table: str,
    column: str,
    n: int,
    order_by_table: str,
    order_by_column: str,
    direction: str = "Top",
    visual_name: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Add a TopN filter to a page or visual.

    *direction* is ``"Top"`` (highest N by *order_by_column*) or
    ``"Bottom"`` (lowest N).  Direction maps to Power BI query Direction
    values: Top = 2 (Descending), Bottom = 1 (Ascending).

    Returns a status dict with name, type, scope, n, and direction.
    """
    direction_upper = direction.strip().capitalize()
    if direction_upper not in ("Top", "Bottom"):
        raise PbiCliError(f"direction must be 'Top' or 'Bottom', got '{direction}'.")

    pbi_direction = 2 if direction_upper == "Top" else 1

    target = _resolve_target_path(definition_path, page_name, visual_name)
    if not target.exists():
        raise PbiCliError(f"File not found: {target}")

    filter_name = name if name is not None else _generate_name()
    cat_alias = table[0].lower()
    ord_alias = order_by_table[0].lower()
    # Avoid alias collision when both tables start with the same letter
    if ord_alias == cat_alias and order_by_table != table:
        ord_alias = ord_alias + "2"
    scope = "visual" if visual_name is not None else "page"

    # Inner subquery From: include both tables when they differ
    inner_from: list[dict[str, Any]] = [
        {"Name": cat_alias, "Entity": table, "Type": 0},
    ]
    if order_by_table != table:
        inner_from.append({"Name": ord_alias, "Entity": order_by_table, "Type": 0})

    entry: dict[str, Any] = {
        "name": filter_name,
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": table}},
                "Property": column,
            }
        },
        "type": "TopN",
        "filter": {
            "Version": 2,
            "From": [
                {
                    "Name": "subquery",
                    "Expression": {
                        "Subquery": {
                            "Query": {
                                "Version": 2,
                                "From": inner_from,
                                "Select": [
                                    {
                                        "Column": {
                                            "Expression": {"SourceRef": {"Source": cat_alias}},
                                            "Property": column,
                                        },
                                        "Name": "field",
                                    }
                                ],
                                "OrderBy": [
                                    {
                                        "Direction": pbi_direction,
                                        "Expression": {
                                            "Aggregation": {
                                                "Expression": {
                                                    "Column": {
                                                        "Expression": {
                                                            "SourceRef": {
                                                                "Source": ord_alias
                                                                if order_by_table != table
                                                                else cat_alias
                                                            }
                                                        },
                                                        "Property": order_by_column,
                                                    }
                                                },
                                                "Function": 0,
                                            }
                                        },
                                    }
                                ],
                                "Top": n,
                            }
                        }
                    },
                    "Type": 2,
                },
                {"Name": cat_alias, "Entity": table, "Type": 0},
            ],
            "Where": [
                {
                    "Condition": {
                        "In": {
                            "Expressions": [
                                {
                                    "Column": {
                                        "Expression": {"SourceRef": {"Source": cat_alias}},
                                        "Property": column,
                                    }
                                }
                            ],
                            "Table": {"SourceRef": {"Source": "subquery"}},
                        }
                    }
                }
            ],
        },
    }

    if scope == "page":
        entry["howCreated"] = "User"

    data = _read_json(target)
    filters = list(_get_filters(data))
    filters.append(entry)
    updated = _set_filters(data, filters)
    _write_json(target, updated)

    return {
        "status": "added",
        "name": filter_name,
        "type": "TopN",
        "scope": scope,
        "n": n,
        "direction": direction_upper,
    }


# TimeUnit integer codes used by Power BI for RelativeDate filters.
_RELATIVE_DATE_TIME_UNITS: dict[str, int] = {
    "days": 0,
    "weeks": 1,
    "months": 2,
    "years": 3,
}


def filter_add_relative_date(
    definition_path: Path,
    page_name: str,
    table: str,
    column: str,
    amount: int,
    time_unit: str,
    visual_name: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Add a RelativeDate filter (e.g. "last 3 months") to a page or visual.

    *amount* is a positive integer representing the period count.
    *time_unit* is one of ``"days"``, ``"weeks"``, ``"months"``, ``"years"``.

    The filter matches rows where *column* falls in the last *amount* *time_unit*
    relative to today (inclusive of the current period boundary).

    Returns a status dict with name, type, scope, amount, and time_unit.
    """
    time_unit_lower = time_unit.strip().lower()
    if time_unit_lower not in _RELATIVE_DATE_TIME_UNITS:
        valid = ", ".join(_RELATIVE_DATE_TIME_UNITS)
        raise PbiCliError(f"time_unit must be one of {valid}, got '{time_unit}'.")
    time_unit_code = _RELATIVE_DATE_TIME_UNITS[time_unit_lower]
    days_code = _RELATIVE_DATE_TIME_UNITS["days"]

    target = _resolve_target_path(definition_path, page_name, visual_name)
    if not target.exists():
        raise PbiCliError(f"File not found: {target}")

    filter_name = name if name is not None else _generate_name()
    alias = table[0].lower()
    scope = "visual" if visual_name is not None else "page"

    # LowerBound: DateSpan(DateAdd(DateAdd(Now(), +1, days), -amount, time_unit), days)
    lower_bound: dict[str, Any] = {
        "DateSpan": {
            "Expression": {
                "DateAdd": {
                    "Expression": {
                        "DateAdd": {
                            "Expression": {"Now": {}},
                            "Amount": 1,
                            "TimeUnit": days_code,
                        }
                    },
                    "Amount": -amount,
                    "TimeUnit": time_unit_code,
                }
            },
            "TimeUnit": days_code,
        }
    }

    # UpperBound: DateSpan(Now(), days)
    upper_bound: dict[str, Any] = {
        "DateSpan": {
            "Expression": {"Now": {}},
            "TimeUnit": days_code,
        }
    }

    entry: dict[str, Any] = {
        "name": filter_name,
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": table}},
                "Property": column,
            }
        },
        "type": "RelativeDate",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": table, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "Between": {
                            "Expression": {
                                "Column": {
                                    "Expression": {"SourceRef": {"Source": alias}},
                                    "Property": column,
                                }
                            },
                            "LowerBound": lower_bound,
                            "UpperBound": upper_bound,
                        }
                    }
                }
            ],
        },
    }

    if scope == "page":
        entry["howCreated"] = "User"

    data = _read_json(target)
    filters = list(_get_filters(data))
    filters.append(entry)
    updated = _set_filters(data, filters)
    _write_json(target, updated)

    return {
        "status": "added",
        "name": filter_name,
        "type": "RelativeDate",
        "scope": scope,
        "amount": amount,
        "time_unit": time_unit_lower,
    }


def filter_clear(
    definition_path: Path,
    page_name: str,
    visual_name: str | None = None,
) -> dict[str, Any]:
    """Remove all filters from a page or visual.

    Returns a status dict with the count of removed filters and scope.
    """
    target = _resolve_target_path(definition_path, page_name, visual_name)
    if not target.exists():
        raise PbiCliError(f"File not found: {target}")

    scope = "visual" if visual_name is not None else "page"
    data = _read_json(target)
    filters = _get_filters(data)
    removed = len(filters)

    updated = _set_filters(data, [])
    _write_json(target, updated)
    return {"status": "cleared", "removed": removed, "scope": scope}
