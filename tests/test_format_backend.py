"""Tests for pbi_cli.core.format_backend.

Covers format_get, format_clear, format_background_gradient, and
format_background_measure against a minimal in-memory PBIR directory tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pbi_cli.core.errors import PbiCliError
from pbi_cli.core.format_backend import (
    format_background_conditional,
    format_background_gradient,
    format_background_measure,
    format_clear,
    format_data_labels,
    format_display_units,
    format_get,
    format_set_object,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

PAGE_NAME = "overview"
VISUAL_NAME = "test_visual"
FIELD_PROFIT = "Sum(financials.Profit)"
FIELD_SALES = "Sum(financials.Sales)"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _minimal_visual_json() -> dict[str, Any]:
    """Return a minimal visual.json with two bound fields and no objects."""
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/"
        "fabric/item/report/definition/visual/1.0.0/schema.json",
        "visual": {
            "visualType": "tableEx",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [
                            {
                                "field": {
                                    "Column": {
                                        "Expression": {"SourceRef": {"Entity": "financials"}},
                                        "Property": "Profit",
                                    }
                                },
                                "queryRef": FIELD_PROFIT,
                                "active": True,
                            },
                            {
                                "field": {
                                    "Column": {
                                        "Expression": {"SourceRef": {"Entity": "financials"}},
                                        "Property": "Sales",
                                    }
                                },
                                "queryRef": FIELD_SALES,
                                "active": True,
                            },
                        ]
                    }
                }
            },
        },
    }


@pytest.fixture
def report_with_visual(tmp_path: Path) -> Path:
    """Build a minimal PBIR definition folder with one page containing one visual.

    Returns the ``definition/`` path accepted by all format_* functions.

    Layout::

        <tmp_path>/
          definition/
            version.json
            report.json
            pages/
              pages.json
              overview/
                page.json
                visuals/
                  test_visual/
                    visual.json
    """
    definition = tmp_path / "definition"
    definition.mkdir()

    _write_json(
        definition / "version.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/"
            "fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "1.0.0",
        },
    )
    _write_json(
        definition / "report.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/"
            "fabric/item/report/definition/report/1.0.0/schema.json",
            "themeCollection": {"baseTheme": {"name": "CY24SU06"}},
            "layoutOptimization": "Disabled",
        },
    )

    pages_dir = definition / "pages"
    pages_dir.mkdir()
    _write_json(
        pages_dir / "pages.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/"
            "fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [PAGE_NAME],
        },
    )

    page_dir = pages_dir / PAGE_NAME
    page_dir.mkdir()
    _write_json(
        page_dir / "page.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/"
            "fabric/item/report/definition/page/1.0.0/schema.json",
            "name": PAGE_NAME,
            "displayName": "Overview",
            "displayOption": "FitToPage",
            "width": 1280,
            "height": 720,
            "ordinal": 0,
        },
    )

    visuals_dir = page_dir / "visuals"
    visuals_dir.mkdir()

    visual_dir = visuals_dir / VISUAL_NAME
    visual_dir.mkdir()
    _write_json(visual_dir / "visual.json", _minimal_visual_json())

    return definition


# ---------------------------------------------------------------------------
# Helper to read saved visual.json directly
# ---------------------------------------------------------------------------


def _read_visual(definition: Path) -> dict[str, Any]:
    path = definition / "pages" / PAGE_NAME / "visuals" / VISUAL_NAME / "visual.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. format_get on a fresh visual returns empty objects
# ---------------------------------------------------------------------------


def test_format_get_fresh_visual_returns_empty_objects(report_with_visual: Path) -> None:
    """format_get returns empty objects dict on a visual with no formatting."""
    result = format_get(report_with_visual, PAGE_NAME, VISUAL_NAME)

    assert result["visual"] == VISUAL_NAME
    assert result["objects"] == {}


# ---------------------------------------------------------------------------
# 2. format_background_gradient adds an entry to objects.values
# ---------------------------------------------------------------------------


def test_format_background_gradient_adds_entry(report_with_visual: Path) -> None:
    """format_background_gradient creates objects.values with one entry."""
    format_background_gradient(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Profit",
        field_query_ref=FIELD_PROFIT,
    )

    data = _read_visual(report_with_visual)
    values = data["visual"]["objects"]["values"]
    assert len(values) == 1


# ---------------------------------------------------------------------------
# 3. Gradient entry has correct FillRule.linearGradient2 structure
# ---------------------------------------------------------------------------


def test_format_background_gradient_correct_structure(report_with_visual: Path) -> None:
    """Gradient entry contains the expected FillRule.linearGradient2 keys."""
    format_background_gradient(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Profit",
        field_query_ref=FIELD_PROFIT,
    )

    data = _read_visual(report_with_visual)
    entry = data["visual"]["objects"]["values"][0]
    fill_rule_expr = entry["properties"]["backColor"]["solid"]["color"]["expr"]["FillRule"]
    assert "linearGradient2" in fill_rule_expr["FillRule"]
    linear = fill_rule_expr["FillRule"]["linearGradient2"]
    assert "min" in linear
    assert "max" in linear
    assert "nullColoringStrategy" in linear["min"]


# ---------------------------------------------------------------------------
# 4. Gradient entry selector.metadata matches field_query_ref
# ---------------------------------------------------------------------------


def test_format_background_gradient_selector_metadata(report_with_visual: Path) -> None:
    """Gradient entry selector.metadata equals the supplied field_query_ref."""
    format_background_gradient(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Profit",
        field_query_ref=FIELD_PROFIT,
    )

    data = _read_visual(report_with_visual)
    entry = data["visual"]["objects"]["values"][0]
    assert entry["selector"]["metadata"] == FIELD_PROFIT


# ---------------------------------------------------------------------------
# 5. format_background_measure adds an entry to objects.values
# ---------------------------------------------------------------------------


def test_format_background_measure_adds_entry(report_with_visual: Path) -> None:
    """format_background_measure creates objects.values with one entry."""
    format_background_measure(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        measure_table="financials",
        measure_property="Conditional Formatting Sales",
        field_query_ref=FIELD_SALES,
    )

    data = _read_visual(report_with_visual)
    values = data["visual"]["objects"]["values"]
    assert len(values) == 1


# ---------------------------------------------------------------------------
# 6. Measure entry has correct Measure expression structure
# ---------------------------------------------------------------------------


def test_format_background_measure_correct_structure(report_with_visual: Path) -> None:
    """Measure entry contains the expected Measure expression keys."""
    format_background_measure(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        measure_table="financials",
        measure_property="Conditional Formatting Sales",
        field_query_ref=FIELD_SALES,
    )

    data = _read_visual(report_with_visual)
    entry = data["visual"]["objects"]["values"][0]
    measure_expr = entry["properties"]["backColor"]["solid"]["color"]["expr"]
    assert "Measure" in measure_expr
    assert measure_expr["Measure"]["Property"] == "Conditional Formatting Sales"
    assert measure_expr["Measure"]["Expression"]["SourceRef"]["Entity"] == "financials"


# ---------------------------------------------------------------------------
# 7. Applying gradient twice (same field_query_ref) replaces, not duplicates
# ---------------------------------------------------------------------------


def test_format_background_gradient_idempotent(report_with_visual: Path) -> None:
    """Applying gradient twice on same field replaces the existing entry."""
    format_background_gradient(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Profit",
        field_query_ref=FIELD_PROFIT,
    )
    format_background_gradient(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Profit",
        field_query_ref=FIELD_PROFIT,
    )

    data = _read_visual(report_with_visual)
    values = data["visual"]["objects"]["values"]
    assert len(values) == 1


# ---------------------------------------------------------------------------
# 8. Applying gradient for different field_query_ref creates second entry
# ---------------------------------------------------------------------------


def test_format_background_gradient_different_fields(report_with_visual: Path) -> None:
    """Two different field_query_refs produce two entries in objects.values."""
    format_background_gradient(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Profit",
        field_query_ref=FIELD_PROFIT,
    )
    format_background_gradient(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Sales",
        field_query_ref=FIELD_SALES,
    )

    data = _read_visual(report_with_visual)
    values = data["visual"]["objects"]["values"]
    assert len(values) == 2
    refs = {e["selector"]["metadata"] for e in values}
    assert refs == {FIELD_PROFIT, FIELD_SALES}


# ---------------------------------------------------------------------------
# 9. format_clear sets objects to {}
# ---------------------------------------------------------------------------


def test_format_clear_sets_empty_objects(report_with_visual: Path) -> None:
    """format_clear sets visual.objects to an empty dict."""
    format_background_gradient(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Profit",
        field_query_ref=FIELD_PROFIT,
    )
    format_clear(report_with_visual, PAGE_NAME, VISUAL_NAME)

    data = _read_visual(report_with_visual)
    assert data["visual"]["objects"] == {}


# ---------------------------------------------------------------------------
# 10. format_clear after gradient clears the entries
# ---------------------------------------------------------------------------


def test_format_clear_removes_values(report_with_visual: Path) -> None:
    """format_clear removes objects.values that were set by gradient."""
    format_background_gradient(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Profit",
        field_query_ref=FIELD_PROFIT,
    )
    result = format_clear(report_with_visual, PAGE_NAME, VISUAL_NAME)

    assert result["status"] == "cleared"
    data = _read_visual(report_with_visual)
    assert "values" not in data["visual"]["objects"]


# ---------------------------------------------------------------------------
# 11. format_get after gradient returns non-empty objects
# ---------------------------------------------------------------------------


def test_format_get_after_gradient_returns_objects(report_with_visual: Path) -> None:
    """format_get returns non-empty objects after a gradient rule is applied."""
    format_background_gradient(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Profit",
        field_query_ref=FIELD_PROFIT,
    )

    result = format_get(report_with_visual, PAGE_NAME, VISUAL_NAME)

    assert result["visual"] == VISUAL_NAME
    assert result["objects"] != {}
    assert len(result["objects"]["values"]) == 1


# ---------------------------------------------------------------------------
# 12. format_get on missing visual raises PbiCliError
# ---------------------------------------------------------------------------


def test_format_get_missing_visual_raises(report_with_visual: Path) -> None:
    """format_get raises PbiCliError when the visual folder does not exist."""
    with pytest.raises(PbiCliError, match="not found"):
        format_get(report_with_visual, PAGE_NAME, "nonexistent_visual")


# ---------------------------------------------------------------------------
# 13. gradient + measure on different fields: objects.values has 2 entries
# ---------------------------------------------------------------------------


def test_gradient_and_measure_different_fields(report_with_visual: Path) -> None:
    """A gradient on one field and a measure rule on another yield two entries."""
    format_background_gradient(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Profit",
        field_query_ref=FIELD_PROFIT,
    )
    format_background_measure(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        measure_table="financials",
        measure_property="Conditional Formatting Sales",
        field_query_ref=FIELD_SALES,
    )

    data = _read_visual(report_with_visual)
    values = data["visual"]["objects"]["values"]
    assert len(values) == 2


# ---------------------------------------------------------------------------
# 14. format_background_measure with same field replaces existing entry
# ---------------------------------------------------------------------------


def test_format_background_measure_replaces_existing(report_with_visual: Path) -> None:
    """Applying measure rule twice on same field replaces the existing entry."""
    format_background_measure(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        measure_table="financials",
        measure_property="CF Sales v1",
        field_query_ref=FIELD_SALES,
    )
    format_background_measure(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        measure_table="financials",
        measure_property="CF Sales v2",
        field_query_ref=FIELD_SALES,
    )

    data = _read_visual(report_with_visual)
    values = data["visual"]["objects"]["values"]
    assert len(values) == 1
    prop = values[0]["properties"]["backColor"]["solid"]["color"]["expr"]["Measure"]["Property"]
    assert prop == "CF Sales v2"


# ---------------------------------------------------------------------------
# 15. format_clear returns correct status dict
# ---------------------------------------------------------------------------


def test_format_clear_return_value(report_with_visual: Path) -> None:
    """format_clear returns the expected status dictionary."""
    result = format_clear(report_with_visual, PAGE_NAME, VISUAL_NAME)

    assert result == {"status": "cleared", "visual": VISUAL_NAME}


# ---------------------------------------------------------------------------
# format_background_conditional
# ---------------------------------------------------------------------------

FIELD_UNITS = "Sum(financials.Units Sold)"


def test_format_background_conditional_adds_entry(report_with_visual: Path) -> None:
    """format_background_conditional creates an entry in objects.values."""
    format_background_conditional(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Units Sold",
        threshold=100000,
        color_hex="#12239E",
        field_query_ref=FIELD_UNITS,
    )

    data = _read_visual(report_with_visual)
    values = data["visual"]["objects"]["values"]
    assert len(values) == 1


def test_format_background_conditional_correct_structure(report_with_visual: Path) -> None:
    """Conditional entry has Conditional.Cases with ComparisonKind and color."""
    format_background_conditional(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Units Sold",
        threshold=100000,
        color_hex="#12239E",
        field_query_ref=FIELD_UNITS,
    )

    data = _read_visual(report_with_visual)
    entry = data["visual"]["objects"]["values"][0]
    cond_expr = entry["properties"]["backColor"]["solid"]["color"]["expr"]["Conditional"]
    assert "Cases" in cond_expr
    case = cond_expr["Cases"][0]
    comparison = case["Condition"]["Comparison"]
    assert comparison["ComparisonKind"] == 2  # gt
    assert comparison["Right"]["Literal"]["Value"] == "100000D"
    assert case["Value"]["Literal"]["Value"] == "'#12239E'"


def test_format_background_conditional_selector_metadata(report_with_visual: Path) -> None:
    """Conditional entry selector.metadata equals the supplied field_query_ref."""
    format_background_conditional(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Units Sold",
        threshold=100000,
        color_hex="#12239E",
        field_query_ref=FIELD_UNITS,
    )

    data = _read_visual(report_with_visual)
    entry = data["visual"]["objects"]["values"][0]
    assert entry["selector"]["metadata"] == FIELD_UNITS


def test_format_background_conditional_default_field_query_ref(
    report_with_visual: Path,
) -> None:
    """When field_query_ref is omitted, it defaults to 'Sum(table.column)'."""
    result = format_background_conditional(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Units Sold",
        threshold=100000,
        color_hex="#12239E",
    )

    assert result["field"] == "Sum(financials.Units Sold)"


def test_format_background_conditional_replaces_existing(report_with_visual: Path) -> None:
    """Applying conditional twice on same field_query_ref replaces the entry."""
    format_background_conditional(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Units Sold",
        threshold=100000,
        color_hex="#FF0000",
        field_query_ref=FIELD_UNITS,
    )
    format_background_conditional(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Units Sold",
        threshold=50000,
        color_hex="#00FF00",
        field_query_ref=FIELD_UNITS,
    )

    data = _read_visual(report_with_visual)
    values = data["visual"]["objects"]["values"]
    assert len(values) == 1
    case = values[0]["properties"]["backColor"]["solid"]["color"]["expr"]["Conditional"]["Cases"][0]
    assert case["Value"]["Literal"]["Value"] == "'#00FF00'"


def test_format_background_conditional_comparison_lte(report_with_visual: Path) -> None:
    """comparison='lte' maps to ComparisonKind=5."""
    format_background_conditional(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Units Sold",
        threshold=10000,
        color_hex="#AABBCC",
        comparison="lte",
        field_query_ref=FIELD_UNITS,
    )

    data = _read_visual(report_with_visual)
    entry = data["visual"]["objects"]["values"][0]
    kind = entry["properties"]["backColor"]["solid"]["color"]["expr"]["Conditional"]["Cases"][0][
        "Condition"
    ]["Comparison"]["ComparisonKind"]
    assert kind == 5  # lte


def test_format_background_conditional_invalid_comparison(
    report_with_visual: Path,
) -> None:
    """An unknown comparison string raises PbiCliError."""
    with pytest.raises(PbiCliError):
        format_background_conditional(
            report_with_visual,
            PAGE_NAME,
            VISUAL_NAME,
            input_table="financials",
            input_column="Units Sold",
            threshold=100,
            color_hex="#000000",
            comparison="between",
        )


# ---------------------------------------------------------------------------
# format_display_units
# ---------------------------------------------------------------------------


def test_display_units_none_creates_label_display_units(report_with_visual: Path) -> None:
    """--units none writes labelDisplayUnits='1D' on a fresh field entry."""
    format_display_units(report_with_visual, PAGE_NAME, VISUAL_NAME, FIELD_SALES, "none")

    data = _read_visual(report_with_visual)
    entry = data["visual"]["objects"]["values"][0]
    assert entry["selector"]["metadata"] == FIELD_SALES
    assert entry["properties"]["labelDisplayUnits"] == {"expr": {"Literal": {"Value": "1D"}}}


def test_display_units_millions_value(report_with_visual: Path) -> None:
    """--units millions writes labelDisplayUnits='1000000D'."""
    format_display_units(report_with_visual, PAGE_NAME, VISUAL_NAME, FIELD_SALES, "millions")

    data = _read_visual(report_with_visual)
    value = data["visual"]["objects"]["values"][0]["properties"]["labelDisplayUnits"]
    assert value == {"expr": {"Literal": {"Value": "1000000D"}}}


@pytest.mark.parametrize(
    "token,expected",
    [
        ("none", "1D"),
        ("thousands", "1000D"),
        ("millions", "1000000D"),
        ("billions", "1000000000D"),
        ("k", "1000D"),
        ("m", "1000000D"),
        ("2500", "2500D"),
    ],
)
def test_display_units_tokens(report_with_visual: Path, token: str, expected: str) -> None:
    """Named units and raw multipliers resolve to the correct D-literal."""
    format_display_units(report_with_visual, PAGE_NAME, VISUAL_NAME, FIELD_SALES, token)
    data = _read_visual(report_with_visual)
    value = data["visual"]["objects"]["values"][0]["properties"]["labelDisplayUnits"]
    assert value == {"expr": {"Literal": {"Value": expected}}}


def test_display_units_invalid_raises(report_with_visual: Path) -> None:
    """An unknown units token raises PbiCliError."""
    with pytest.raises(PbiCliError, match="Unknown display units"):
        format_display_units(report_with_visual, PAGE_NAME, VISUAL_NAME, FIELD_SALES, "bazillion")


def test_display_units_merges_into_existing_field(report_with_visual: Path) -> None:
    """Setting display units on a field that already has CF preserves the CF."""
    format_background_gradient(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        input_table="financials",
        input_column="Sales",
        field_query_ref=FIELD_SALES,
    )
    format_display_units(report_with_visual, PAGE_NAME, VISUAL_NAME, FIELD_SALES, "none")

    data = _read_visual(report_with_visual)
    values = data["visual"]["objects"]["values"]
    assert len(values) == 1  # merged, not duplicated
    props = values[0]["properties"]
    assert "backColor" in props  # original CF preserved
    assert props["labelDisplayUnits"] == {"expr": {"Literal": {"Value": "1D"}}}


def test_display_units_auto_removes_override(report_with_visual: Path) -> None:
    """--units auto strips an existing labelDisplayUnits override."""
    format_display_units(report_with_visual, PAGE_NAME, VISUAL_NAME, FIELD_SALES, "millions")
    result = format_display_units(report_with_visual, PAGE_NAME, VISUAL_NAME, FIELD_SALES, "auto")

    assert result["units"] == "auto"
    data = _read_visual(report_with_visual)
    # auto leaves an empty properties entry (selector retained) — no labelDisplayUnits
    values = data["visual"]["objects"]["values"]
    assert len(values) == 1
    assert "labelDisplayUnits" not in values[0]["properties"]


def test_display_units_replaces_existing(report_with_visual: Path) -> None:
    """Changing units twice on the same field yields one entry with the new value."""
    format_display_units(report_with_visual, PAGE_NAME, VISUAL_NAME, FIELD_SALES, "millions")
    format_display_units(report_with_visual, PAGE_NAME, VISUAL_NAME, FIELD_SALES, "none")

    data = _read_visual(report_with_visual)
    values = data["visual"]["objects"]["values"]
    assert len(values) == 1
    value = values[0]["properties"]["labelDisplayUnits"]
    assert value == {"expr": {"Literal": {"Value": "1D"}}}


def test_display_units_auto_locates_value_container(report_with_visual: Path) -> None:
    """A field living under objects.value (modern cardVisual) is updated in place."""
    # Pre-seed a cardVisual-style structure with the field under objects.value
    vpath = report_with_visual / "pages" / PAGE_NAME / "visuals" / VISUAL_NAME / "visual.json"
    seeded = _read_visual(report_with_visual)
    seeded["visual"]["visualType"] = "cardVisual"
    seeded["visual"]["objects"] = {
        "value": [
            {
                "properties": {"fontSize": {"expr": {"Literal": {"Value": "20D"}}}},
                "selector": {"metadata": FIELD_SALES},
            }
        ]
    }
    _write_json(vpath, seeded)

    format_display_units(report_with_visual, PAGE_NAME, VISUAL_NAME, FIELD_SALES, "none")

    data = _read_visual(report_with_visual)
    # updated in place under `value`, NOT duplicated into a new `values` list
    assert "values" not in data["visual"]["objects"]
    entry = data["visual"]["objects"]["value"][0]
    assert entry["selector"]["metadata"] == FIELD_SALES
    assert entry["properties"]["labelDisplayUnits"] == {"expr": {"Literal": {"Value": "1D"}}}
    assert "fontSize" in entry["properties"]  # sibling preserved


# ---------------------------------------------------------------------------
# format_data_labels
# ---------------------------------------------------------------------------


def test_data_labels_hide_visual_level(report_with_visual: Path) -> None:
    """Hiding data labels sets labels[0].properties.show=false at visual level."""
    format_data_labels(report_with_visual, PAGE_NAME, VISUAL_NAME, show=False)

    data = _read_visual(report_with_visual)
    labels = data["visual"]["objects"]["labels"]
    assert labels[0]["properties"]["show"] == {"expr": {"Literal": {"Value": "false"}}}


def test_data_labels_show_visual_level(report_with_visual: Path) -> None:
    """Showing data labels sets labels[0].properties.show=true."""
    format_data_labels(report_with_visual, PAGE_NAME, VISUAL_NAME, show=True)

    data = _read_visual(report_with_visual)
    value = data["visual"]["objects"]["labels"][0]["properties"]["show"]
    assert value == {"expr": {"Literal": {"Value": "true"}}}


def test_data_labels_per_field(report_with_visual: Path) -> None:
    """With a field_query_ref, labels.show goes into the per-field values entry."""
    format_data_labels(
        report_with_visual, PAGE_NAME, VISUAL_NAME, show=True, field_query_ref=FIELD_SALES
    )

    data = _read_visual(report_with_visual)
    entry = data["visual"]["objects"]["values"][0]
    assert entry["selector"]["metadata"] == FIELD_SALES
    assert entry["properties"]["show"] == {"expr": {"Literal": {"Value": "true"}}}


def test_data_labels_idempotent(report_with_visual: Path) -> None:
    """Toggling labels twice does not create a second labels property-group."""
    format_data_labels(report_with_visual, PAGE_NAME, VISUAL_NAME, show=False)
    format_data_labels(report_with_visual, PAGE_NAME, VISUAL_NAME, show=True)

    data = _read_visual(report_with_visual)
    labels = data["visual"]["objects"]["labels"]
    assert len(labels) == 1
    assert labels[0]["properties"]["show"] == {"expr": {"Literal": {"Value": "true"}}}


# ---------------------------------------------------------------------------
# format_set_object (generic)
# ---------------------------------------------------------------------------


def test_set_object_visual_level(report_with_visual: Path) -> None:
    """Generic setter writes a visual-level property under the named object."""
    format_set_object(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        property_name="showAxisTitle",
        object_name="valueAxis",
        value="false",
    )

    data = _read_visual(report_with_visual)
    value = data["visual"]["objects"]["valueAxis"][0]["properties"]["showAxisTitle"]
    assert value == {"expr": {"Literal": {"Value": "false"}}}


def test_set_object_per_field(report_with_visual: Path) -> None:
    """Generic setter with --field writes into the per-field values entry."""
    format_set_object(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        property_name="fontSize",
        value="12D",
        field_query_ref=FIELD_SALES,
    )

    data = _read_visual(report_with_visual)
    entry = data["visual"]["objects"]["values"][0]
    assert entry["selector"]["metadata"] == FIELD_SALES
    assert entry["properties"]["fontSize"] == {"expr": {"Literal": {"Value": "12D"}}}


def test_set_object_remove_visual_level(report_with_visual: Path) -> None:
    """--remove deletes a visual-level property."""
    format_set_object(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        property_name="show",
        object_name="labels",
        value="true",
    )
    format_set_object(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        property_name="show",
        object_name="labels",
        remove=True,
    )

    data = _read_visual(report_with_visual)
    assert "show" not in data["visual"]["objects"]["labels"][0]["properties"]


def test_set_object_requires_object_or_field(report_with_visual: Path) -> None:
    """Without --object or --field the setter raises PbiCliError."""
    with pytest.raises(PbiCliError, match="Either --object"):
        format_set_object(
            report_with_visual,
            PAGE_NAME,
            VISUAL_NAME,
            property_name="show",
            value="true",
        )


def test_set_object_color_value(report_with_visual: Path) -> None:
    """A hex color value is encoded as a solid color expression."""
    format_set_object(
        report_with_visual,
        PAGE_NAME,
        VISUAL_NAME,
        property_name="color",
        object_name="labels",
        value="#FF0000",
    )

    data = _read_visual(report_with_visual)
    value = data["visual"]["objects"]["labels"][0]["properties"]["color"]
    assert value == {"solid": {"color": {"expr": {"Literal": {"Value": "'#FF0000'"}}}}}
