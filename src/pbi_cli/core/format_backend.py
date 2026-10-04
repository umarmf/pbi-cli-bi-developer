"""Pure-function backend for PBIR conditional formatting operations.

Mirrors ``report_backend.py`` but focuses on visual conditional formatting.
Every function takes a ``Path`` to the definition folder and returns a plain
Python dict suitable for ``format_result()``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pbi_cli.core.errors import PbiCliError
from pbi_cli.core.pbir_path import get_visual_dir

# ---------------------------------------------------------------------------
# JSON helpers (same as report_backend / visual_backend)
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_visual(definition_path: Path, page_name: str, visual_name: str) -> dict[str, Any]:
    """Load and return visual JSON data, raising PbiCliError if missing."""
    visual_path = get_visual_dir(definition_path, page_name, visual_name) / "visual.json"
    if not visual_path.exists():
        raise PbiCliError(
            f"Visual '{visual_name}' not found on page '{page_name}'. Expected: {visual_path}"
        )
    return _read_json(visual_path)


def _save_visual(
    definition_path: Path,
    page_name: str,
    visual_name: str,
    data: dict[str, Any],
) -> None:
    """Write visual JSON data back to disk.

    A ``.json.bak`` copy of the previous file is created before writing so
    that a corrupted write can be recovered manually.
    """
    visual_path = get_visual_dir(definition_path, page_name, visual_name) / "visual.json"
    if visual_path.exists():
        backup_path = visual_path.with_suffix(".json.bak")
        backup_path.write_bytes(visual_path.read_bytes())
    _write_json(visual_path, data)


def _get_values_list(objects: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the objects.values list, defaulting to empty."""
    return list(objects.get("values", []))


def _replace_or_append(
    values: list[dict[str, Any]],
    new_entry: dict[str, Any],
    field_query_ref: str,
) -> list[dict[str, Any]]:
    """Return a new list with *new_entry* replacing any existing entry
    whose ``selector.metadata`` matches *field_query_ref*, or appended
    if no match exists. Immutable -- does not modify the input list.
    """
    replaced = False
    result: list[dict[str, Any]] = []
    for entry in values:
        meta = entry.get("selector", {}).get("metadata", "")
        if meta == field_query_ref:
            result.append(new_entry)
            replaced = True
        else:
            result.append(entry)
    if not replaced:
        result.append(new_entry)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def format_get(
    definition_path: Path,
    page_name: str,
    visual_name: str,
) -> dict[str, Any]:
    """Return current formatting objects for a visual.

    Returns ``{"visual": visual_name, "objects": {...}}`` where *objects*
    is the content of ``visual.objects`` (empty dict if absent).
    """
    data = _load_visual(definition_path, page_name, visual_name)
    objects = data.get("visual", {}).get("objects", {})
    return {"visual": visual_name, "objects": objects}


def format_clear(
    definition_path: Path,
    page_name: str,
    visual_name: str,
) -> dict[str, Any]:
    """Clear all formatting objects from a visual.

    Sets ``visual.objects`` to ``{}`` and persists the change.
    Returns ``{"status": "cleared", "visual": visual_name}``.
    """
    data = _load_visual(definition_path, page_name, visual_name)
    visual_section = dict(data.get("visual", {}))
    visual_section["objects"] = {}
    new_data = {**data, "visual": visual_section}
    _save_visual(definition_path, page_name, visual_name, new_data)
    return {"status": "cleared", "visual": visual_name}


def format_background_gradient(
    definition_path: Path,
    page_name: str,
    visual_name: str,
    input_table: str,
    input_column: str,
    field_query_ref: str,
    min_color: str = "#FFFFFF",
    max_color: str = "#118DFF",
) -> dict[str, Any]:
    """Add a linear gradient background color rule to a visual column.

    *input_table* / *input_column*: the measure/column driving the gradient
    (used for the FillRule.Input Aggregation).

    *field_query_ref*: the queryRef of the target field (e.g.
    ``"Sum(financials.Profit)"``). Used as ``selector.metadata``.

    Adds/replaces the entry in ``visual.objects.values[]`` whose
    ``selector.metadata`` matches *field_query_ref*.

    Returns ``{"status": "applied", "visual": visual_name,
    "rule": "gradient", "field": field_query_ref}``.
    """
    data = _load_visual(definition_path, page_name, visual_name)
    visual_section = dict(data.get("visual", {}))
    objects = dict(visual_section.get("objects", {}))
    values = _get_values_list(objects)

    new_entry: dict[str, Any] = {
        "properties": {
            "backColor": {
                "solid": {
                    "color": {
                        "expr": {
                            "FillRule": {
                                "Input": {
                                    "Aggregation": {
                                        "Expression": {
                                            "Column": {
                                                "Expression": {
                                                    "SourceRef": {"Entity": input_table}
                                                },
                                                "Property": input_column,
                                            }
                                        },
                                        "Function": 0,
                                    }
                                },
                                "FillRule": {
                                    "linearGradient2": {
                                        "min": {
                                            "color": {"Literal": {"Value": f"'{min_color}'"}},
                                            "nullColoringStrategy": {
                                                "strategy": {"Literal": {"Value": "'asZero'"}}
                                            },
                                        },
                                        "max": {"color": {"Literal": {"Value": f"'{max_color}'"}}},
                                    }
                                },
                            }
                        }
                    }
                }
            }
        },
        "selector": {
            "data": [{"dataViewWildcard": {"matchingOption": 1}}],
            "metadata": field_query_ref,
        },
    }

    new_values = _replace_or_append(values, new_entry, field_query_ref)
    new_objects = {**objects, "values": new_values}
    new_visual = {**visual_section, "objects": new_objects}
    new_data = {**data, "visual": new_visual}
    _save_visual(definition_path, page_name, visual_name, new_data)

    return {
        "status": "applied",
        "visual": visual_name,
        "rule": "gradient",
        "field": field_query_ref,
    }


# ComparisonKind integer codes (Power BI query expression).
_COMPARISON_KINDS: dict[str, int] = {
    "eq": 0,
    "neq": 1,
    "gt": 2,
    "gte": 3,
    "lt": 4,
    "lte": 5,
}


def format_background_conditional(
    definition_path: Path,
    page_name: str,
    visual_name: str,
    input_table: str,
    input_column: str,
    threshold: float | int,
    color_hex: str,
    comparison: str = "gt",
    field_query_ref: str | None = None,
) -> dict[str, Any]:
    """Add a rule-based conditional background color to a visual column.

    When the aggregated value of *input_column* satisfies the comparison
    against *threshold*, the cell background is set to *color_hex*.

    *comparison* is one of ``"eq"``, ``"neq"``, ``"gt"``, ``"gte"``,
    ``"lt"``, ``"lte"`` (default ``"gt"``).

    *field_query_ref* is the ``selector.metadata`` queryRef of the target
    field (e.g. ``"Sum(financials.Units Sold)"``).  Defaults to
    ``"Sum({table}.{column})"`` if omitted.

    Returns ``{"status": "applied", "visual": visual_name,
    "rule": "conditional", "field": field_query_ref}``.
    """
    comparison_lower = comparison.strip().lower()
    if comparison_lower not in _COMPARISON_KINDS:
        valid = ", ".join(_COMPARISON_KINDS)
        raise PbiCliError(f"comparison must be one of {valid}, got '{comparison}'.")
    comparison_kind = _COMPARISON_KINDS[comparison_lower]

    if field_query_ref is None:
        field_query_ref = f"Sum({input_table}.{input_column})"

    # Format threshold as a Power BI decimal literal (D suffix).
    threshold_literal = f"{threshold}D"

    data = _load_visual(definition_path, page_name, visual_name)
    visual_section = dict(data.get("visual", {}))
    objects = dict(visual_section.get("objects", {}))
    values = _get_values_list(objects)

    new_entry: dict[str, Any] = {
        "properties": {
            "backColor": {
                "solid": {
                    "color": {
                        "expr": {
                            "Conditional": {
                                "Cases": [
                                    {
                                        "Condition": {
                                            "Comparison": {
                                                "ComparisonKind": comparison_kind,
                                                "Left": {
                                                    "Aggregation": {
                                                        "Expression": {
                                                            "Column": {
                                                                "Expression": {
                                                                    "SourceRef": {
                                                                        "Entity": input_table
                                                                    }
                                                                },
                                                                "Property": input_column,
                                                            }
                                                        },
                                                        "Function": 0,
                                                    }
                                                },
                                                "Right": {"Literal": {"Value": threshold_literal}},
                                            }
                                        },
                                        "Value": {"Literal": {"Value": f"'{color_hex}'"}},
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        },
        "selector": {
            "data": [{"dataViewWildcard": {"matchingOption": 1}}],
            "metadata": field_query_ref,
        },
    }

    new_values = _replace_or_append(values, new_entry, field_query_ref)
    new_objects = {**objects, "values": new_values}
    new_visual = {**visual_section, "objects": new_objects}
    new_data = {**data, "visual": new_visual}
    _save_visual(definition_path, page_name, visual_name, new_data)

    return {
        "status": "applied",
        "visual": visual_name,
        "rule": "conditional",
        "field": field_query_ref,
    }


def format_background_measure(
    definition_path: Path,
    page_name: str,
    visual_name: str,
    measure_table: str,
    measure_property: str,
    field_query_ref: str,
) -> dict[str, Any]:
    """Add a measure-driven background color rule to a visual column.

    *measure_table* / *measure_property*: the DAX measure that returns a
    hex color string.

    *field_query_ref*: the queryRef of the target field.

    Adds/replaces the entry in ``visual.objects.values[]`` whose
    ``selector.metadata`` matches *field_query_ref*.

    Returns ``{"status": "applied", "visual": visual_name,
    "rule": "measure", "field": field_query_ref}``.
    """
    data = _load_visual(definition_path, page_name, visual_name)
    visual_section = dict(data.get("visual", {}))
    objects = dict(visual_section.get("objects", {}))
    values = _get_values_list(objects)

    new_entry: dict[str, Any] = {
        "properties": {
            "backColor": {
                "solid": {
                    "color": {
                        "expr": {
                            "Measure": {
                                "Expression": {"SourceRef": {"Entity": measure_table}},
                                "Property": measure_property,
                            }
                        }
                    }
                }
            }
        },
        "selector": {
            "data": [{"dataViewWildcard": {"matchingOption": 1}}],
            "metadata": field_query_ref,
        },
    }

    new_values = _replace_or_append(values, new_entry, field_query_ref)
    new_objects = {**objects, "values": new_values}
    new_visual = {**visual_section, "objects": new_objects}
    new_data = {**data, "visual": new_visual}
    _save_visual(definition_path, page_name, visual_name, new_data)

    return {
        "status": "applied",
        "visual": visual_name,
        "rule": "measure",
        "field": field_query_ref,
    }


# ---------------------------------------------------------------------------
# Visual-level object property setters (display units, data labels, etc.)
#
# PBIR stores two distinct shapes inside ``visual.objects``:
#   * per-field entries in the ``values`` list, each carrying a
#     ``selector.metadata`` queryRef (e.g. labelDisplayUnits, backColor);
#   * visual-level objects keyed by name (``labels``, ``valueAxis``, ...),
#     each a list of property-groups, typically a single entry with no
#     selector (e.g. labels.show, valueAxis.fontSize).
# ---------------------------------------------------------------------------

_NUM_LITERAL_RE = re.compile(r"^[+-]?\d+(\.\d+)?[DL]?$", re.IGNORECASE)
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")


def _encode_literal(value: Any, kind: str | None = None) -> dict[str, Any]:
    """Encode a Python value into a PBIR property-expression node.

    *kind* overrides auto-detection. Without it:

    * bool  -> ``{"Literal": {"Value": "true"|"false"}}``
    * ``"true"``/``"false"`` strings -> bool literal
    * hex color (``#RRGGBB``) -> ``{"solid": {"color": {"expr": {"Literal": ...}}}}``
    * numeric literal (``"10D"``, ``"0L"``, ``"1000000"``) -> passed through
    * plain int/float -> decimal literal ``"<n>D"``
    * anything else -> single-quoted string literal ``"'x'"``
    """
    if isinstance(value, bool):
        return {"expr": {"Literal": {"Value": "true" if value else "false"}}}

    k = (kind or "").lower()
    s = str(value)
    if not k:
        if s.lower() in ("true", "false"):
            k = "bool"
        elif _HEX_COLOR_RE.match(s):
            k = "color"
        elif _NUM_LITERAL_RE.match(s):
            k = "num"
        else:
            k = "str"

    if k == "bool":
        return {"expr": {"Literal": {"Value": "true" if s.lower() == "true" else "false"}}}
    if k == "num":
        return {"expr": {"Literal": {"Value": s}}}
    if k == "color":
        c = s if s.startswith("#") else f"#{s}"
        return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{c}'"}}}}}
    return {"expr": {"Literal": {"Value": f"'{s}'"}}}


_DISPLAY_UNIT_MULTIPLIERS: dict[str, int] = {
    "none": 1,
    "ones": 1,
    "unit": 1,
    "thousands": 1000,
    "thousand": 1000,
    "k": 1000,
    "millions": 1000000,
    "million": 1000000,
    "m": 1000000,
    "billions": 1000000000,
    "billion": 1000000000,
    "b": 1000000000,
}


def _resolve_display_units(units: Any) -> int | None:
    """Resolve a units token to an integer multiplier, or ``None`` for Auto.

    Accepts named units (none/thousands/millions/billions/auto) or a raw
    integer multiplier. ``None`` (Auto) signals that any existing
    ``labelDisplayUnits`` override should be removed.
    """
    key = str(units).strip().lower()
    if key == "auto":
        return None
    if key in _DISPLAY_UNIT_MULTIPLIERS:
        return _DISPLAY_UNIT_MULTIPLIERS[key]
    try:
        return int(units)
    except (ValueError, TypeError) as exc:
        raise PbiCliError(
            f"Unknown display units '{units}'. Use none/thousands/millions/billions/auto "
            "or an integer multiplier."
        ) from exc


def _set_field_property(
    values: list[dict[str, Any]],
    field_query_ref: str,
    property_name: str,
    value_node: dict[str, Any] | None,
    *,
    remove: bool = False,
) -> list[dict[str, Any]]:
    """Merge (or remove) *property_name* on the per-field entry matching
    *field_query_ref*, appending a new entry if none exists.

    Unlike :func:`_replace_or_append`, this preserves sibling properties on an
    existing field entry (e.g. a field may carry both ``labelDisplayUnits``
    and ``fontSize``). Immutable.
    """
    result: list[dict[str, Any]] = []
    found = False
    for entry in values:
        meta = entry.get("selector", {}).get("metadata", "")
        if meta == field_query_ref:
            found = True
            props = dict(entry.get("properties", {}))
            if remove:
                props.pop(property_name, None)
            elif value_node is not None:
                props[property_name] = value_node
            result.append({**entry, "properties": props})
        else:
            result.append(entry)
    if not found and not remove and value_node is not None:
        result.append(
            {
                "properties": {property_name: value_node},
                "selector": {"metadata": field_query_ref},
            }
        )
    return result


def _find_field_object_key(objects: dict[str, Any], field_query_ref: str) -> str | None:
    """Return the object key whose entry list contains *field_query_ref*.

    Per-field formatting lives under different object keys depending on the
    visual type: ``values`` for tables/matrices, ``value`` for modern
    ``cardVisual``, etc. This scans every object key to find where a given
    field already lives. Returns ``None`` if not present anywhere.
    """
    for key, val in objects.items():
        if not isinstance(val, list):
            continue
        for entry in val:
            if (
                isinstance(entry, dict)
                and entry.get("selector", {}).get("metadata") == field_query_ref
            ):
                return key
    return None


def _set_field_property_anywhere(
    objects: dict[str, Any],
    field_query_ref: str,
    property_name: str,
    value_node: dict[str, Any] | None,
    *,
    object_name: str | None = None,
    remove: bool = False,
    default_container: str = "values",
) -> tuple[dict[str, Any], str | None]:
    """Set/remove a per-field property, auto-locating the field's container.

    *object_name* forces a specific container. Without it the field is
    located across all object-key lists; if absent and creating, it is added
    under *default_container*. Returns the new ``objects`` dict and the key
    that was written to (``None`` when removing a field that does not exist).
    """
    target_key = object_name or _find_field_object_key(objects, field_query_ref)
    if target_key is None:
        if remove:
            return objects, None
        target_key = default_container
    existing = list(objects.get(target_key, []))
    new_list = _set_field_property(
        existing, field_query_ref, property_name, value_node, remove=remove
    )
    return {**objects, target_key: new_list}, target_key


def _set_visual_level_property(
    objects: dict[str, Any],
    object_name: str,
    property_name: str,
    value_node: dict[str, Any] | None,
    *,
    remove: bool = False,
) -> dict[str, Any]:
    """Set (or remove) *property_name* on a visual-level object.

    Targets ``objects.<object_name>[0].properties`` (the single property-group
    used for visual-level settings such as ``labels.show``). Creates the
    object list + group when absent.
    """
    obj_list = list(objects.get(object_name, []))
    if obj_list:
        group = dict(obj_list[0])
        props = dict(group.get("properties", {}))
        if remove:
            props.pop(property_name, None)
        elif value_node is not None:
            props[property_name] = value_node
        obj_list[0] = {**group, "properties": props}
    elif not remove and value_node is not None:
        obj_list = [{"properties": {property_name: value_node}}]
    objects[object_name] = obj_list
    return objects


def format_set_object(
    definition_path: Path,
    page_name: str,
    visual_name: str,
    property_name: str,
    object_name: str | None = None,
    value: Any = None,
    field_query_ref: str | None = None,
    remove: bool = False,
    kind: str | None = None,
) -> dict[str, Any]:
    """Generic setter for any visual ``objects`` property.

    Two scopes:

    * **per-field** (``field_query_ref`` given): merges *property_name* into the
      matching entry. The container key is auto-located (``values`` for
      tables/matrices, ``value`` for modern ``cardVisual``); pass
      ``object_name`` to force a specific container.
    * **visual-level** (``object_name`` given, no field): sets
      ``objects.<object_name>[0].properties[<property_name>]``
      (e.g. ``labels.show``).

    Pass ``remove=True`` to delete the property instead.

    Returns ``{"status": "set"|"removed", "visual", "scope", "object",
    "property", "field"}``.
    """
    if not field_query_ref and not object_name:
        raise PbiCliError("Either --object (visual-level) or --field (per-field) is required.")

    data = _load_visual(definition_path, page_name, visual_name)
    visual_section = dict(data.get("visual", {}))
    objects = dict(visual_section.get("objects", {}))
    value_node = None if remove else _encode_literal(value, kind)

    used_key: str | None
    if field_query_ref:
        objects, used_key = _set_field_property_anywhere(
            objects,
            field_query_ref,
            property_name,
            value_node,
            object_name=object_name,
            remove=remove,
        )
    else:
        assert object_name is not None  # narrowed by the guard above
        objects = _set_visual_level_property(
            objects, object_name, property_name, value_node, remove=remove
        )
        used_key = object_name

    new_visual = {**visual_section, "objects": objects}
    new_data = {**data, "visual": new_visual}
    _save_visual(definition_path, page_name, visual_name, new_data)

    return {
        "status": "removed" if remove else "set",
        "visual": visual_name,
        "scope": "field" if field_query_ref else "visual",
        "object": used_key,
        "property": property_name,
        "field": field_query_ref,
    }


def format_display_units(
    definition_path: Path,
    page_name: str,
    visual_name: str,
    field_query_ref: str,
    units: Any,
    object_name: str | None = None,
) -> dict[str, Any]:
    """Set the display units (abbreviation) of a single visual field.

    *units* accepts ``none`` (whole numbers), ``thousands``, ``millions``,
    ``billions``, ``auto`` (remove override) or an integer multiplier.

    Display units are stored per-field as ``labelDisplayUnits``. The container
    is auto-located (``values`` for tables/matrices, ``value`` for modern
    ``cardVisual``); pass *object_name* to force a specific container.

    Returns ``{"status": "applied", "visual", "field", "units"}``.
    """
    mult = _resolve_display_units(units)
    data = _load_visual(definition_path, page_name, visual_name)
    visual_section = dict(data.get("visual", {}))
    objects = dict(visual_section.get("objects", {}))
    resolved: Any

    if mult is None:  # Auto -> strip the override
        objects, _ = _set_field_property_anywhere(
            objects,
            field_query_ref,
            "labelDisplayUnits",
            None,
            object_name=object_name,
            remove=True,
        )
        resolved = "auto"
    else:
        value_node = _encode_literal(f"{mult}D")
        objects, _ = _set_field_property_anywhere(
            objects,
            field_query_ref,
            "labelDisplayUnits",
            value_node,
            object_name=object_name,
        )
        resolved = mult

    new_visual = {**visual_section, "objects": objects}
    new_data = {**data, "visual": new_visual}
    _save_visual(definition_path, page_name, visual_name, new_data)

    return {
        "status": "applied",
        "visual": visual_name,
        "field": field_query_ref,
        "units": resolved,
    }


def format_data_labels(
    definition_path: Path,
    page_name: str,
    visual_name: str,
    show: bool,
    field_query_ref: str | None = None,
) -> dict[str, Any]:
    """Show or hide data labels on a visual (or a single field).

    With no *field_query_ref* this toggles ``labels.show`` at the visual
    level. With a field it sets the per-field ``show`` (auto-located).

    Returns ``{"status": "applied", "visual", "show", "field"}``.
    """
    value_node = _encode_literal(show)
    data = _load_visual(definition_path, page_name, visual_name)
    visual_section = dict(data.get("visual", {}))
    objects = dict(visual_section.get("objects", {}))

    if field_query_ref:
        objects, _ = _set_field_property_anywhere(objects, field_query_ref, "show", value_node)
    else:
        objects = _set_visual_level_property(objects, "labels", "show", value_node)

    new_visual = {**visual_section, "objects": objects}
    new_data = {**data, "visual": new_visual}
    _save_visual(definition_path, page_name, visual_name, new_data)

    return {
        "status": "applied",
        "visual": visual_name,
        "show": show,
        "field": field_query_ref,
    }
