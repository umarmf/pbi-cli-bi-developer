"""Tests for pbi_cli.core.filter_backend.

Covers filter_list, filter_add_categorical, filter_remove, and filter_clear
for both page-level and visual-level scopes.

A ``sample_report`` fixture builds a minimal valid PBIR folder in tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pbi_cli.core.errors import PbiCliError
from pbi_cli.core.filter_backend import (
    filter_add_advanced,
    filter_add_categorical,
    filter_add_relative_date,
    filter_add_topn,
    filter_clear,
    filter_list,
    filter_remove,
    filter_where,
)

# ---------------------------------------------------------------------------
# Schema constants used only for fixture JSON
# ---------------------------------------------------------------------------

_SCHEMA_PAGE = (
    "https://developer.microsoft.com/json-schemas/"
    "fabric/item/report/definition/page/1.0.0/schema.json"
)
_SCHEMA_VISUAL_CONTAINER = (
    "https://developer.microsoft.com/json-schemas/"
    "fabric/item/report/definition/visualContainer/2.7.0/schema.json"
)
_SCHEMA_VISUAL_CONFIG = (
    "https://developer.microsoft.com/json-schemas/"
    "fabric/item/report/definition/visualConfiguration/2.3.0/schema.json"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[return-value]


def _make_page(definition_path: Path, page_name: str, display_name: str = "Overview") -> Path:
    """Create a minimal page folder and return the page dir."""
    page_dir = definition_path / "pages" / page_name
    page_dir.mkdir(parents=True, exist_ok=True)
    _write(
        page_dir / "page.json",
        {
            "$schema": _SCHEMA_PAGE,
            "name": page_name,
            "displayName": display_name,
            "displayOption": "FitToPage",
            "width": 1280,
            "height": 720,
            "ordinal": 0,
        },
    )
    return page_dir


def _make_visual(page_dir: Path, visual_name: str) -> Path:
    """Create a minimal visual folder and return the visual dir."""
    visual_dir = page_dir / "visuals" / visual_name
    visual_dir.mkdir(parents=True, exist_ok=True)
    _write(
        visual_dir / "visual.json",
        {
            "$schema": _SCHEMA_VISUAL_CONTAINER,
            "name": visual_name,
            "position": {"x": 0, "y": 0, "width": 400, "height": 300, "z": 0, "tabOrder": 0},
            "visual": {
                "$schema": _SCHEMA_VISUAL_CONFIG,
                "visualType": "barChart",
                "query": {"queryState": {}},
                "objects": {},
            },
        },
    )
    return visual_dir


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def definition_path(tmp_path: Path) -> Path:
    """Return a minimal PBIR definition folder with one page and one visual."""
    defn = tmp_path / "MyReport.Report" / "definition"
    defn.mkdir(parents=True)
    _write(defn / "report.json", {"name": "MyReport"})
    page_dir = _make_page(defn, "page_overview", "Overview")
    _make_visual(page_dir, "visual_abc123")
    return defn


# ---------------------------------------------------------------------------
# filter_list
# ---------------------------------------------------------------------------


def test_filter_list_empty_page(definition_path: Path) -> None:
    """filter_list returns empty list when no filterConfig exists on a page."""
    result = filter_list(definition_path, "page_overview")
    assert result == []


def test_filter_list_empty_visual(definition_path: Path) -> None:
    """filter_list returns empty list when no filterConfig exists on a visual."""
    result = filter_list(definition_path, "page_overview", visual_name="visual_abc123")
    assert result == []


def test_filter_list_with_filters(definition_path: Path) -> None:
    """filter_list returns the filters after one is added."""
    filter_add_categorical(definition_path, "page_overview", "Sales", "Region", ["North", "South"])
    result = filter_list(definition_path, "page_overview")
    assert len(result) == 1
    assert result[0]["type"] == "Categorical"


def test_filter_list_missing_file(definition_path: Path) -> None:
    """filter_list raises PbiCliError when the page does not exist."""
    with pytest.raises(PbiCliError):
        filter_list(definition_path, "nonexistent_page")


# ---------------------------------------------------------------------------
# filter_add_categorical (page scope)
# ---------------------------------------------------------------------------


def test_filter_add_categorical_page_returns_status(definition_path: Path) -> None:
    """filter_add_categorical returns the expected status dict."""
    result = filter_add_categorical(
        definition_path, "page_overview", "financials", "Country", ["Canada", "France"]
    )
    assert result["status"] == "added"
    assert result["type"] == "Categorical"
    assert result["scope"] == "page"
    assert "name" in result


def test_filter_add_categorical_page_persisted(definition_path: Path) -> None:
    """Added filter appears in the page.json file with correct structure."""
    filter_add_categorical(
        definition_path, "page_overview", "financials", "Country", ["Canada", "France"]
    )
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    data = _read(page_json)
    filters = data["filterConfig"]["filters"]
    assert len(filters) == 1
    f = filters[0]
    assert f["type"] == "Categorical"
    assert f["howCreated"] == "User"


def test_filter_add_categorical_json_structure(definition_path: Path) -> None:
    """The filter body has correct Version, From, and Where structure."""
    filter_add_categorical(
        definition_path, "page_overview", "financials", "Country", ["Canada", "France"]
    )
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    f = _read(page_json)["filterConfig"]["filters"][0]

    assert f["filter"]["Version"] == 2

    from_entries = f["filter"]["From"]
    assert len(from_entries) == 1
    assert from_entries[0]["Name"] == "f"
    assert from_entries[0]["Entity"] == "financials"
    assert from_entries[0]["Type"] == 0

    where = f["filter"]["Where"]
    assert len(where) == 1
    in_clause = where[0]["Condition"]["In"]
    assert len(in_clause["Values"]) == 2
    assert in_clause["Values"][0][0]["Literal"]["Value"] == "'Canada'"
    assert in_clause["Values"][1][0]["Literal"]["Value"] == "'France'"


def test_filter_add_categorical_alias_from_table_name(definition_path: Path) -> None:
    """Source alias uses the first character of the table name, lowercased."""
    filter_add_categorical(definition_path, "page_overview", "Sales", "Product", ["Widget"])
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    f = _read(page_json)["filterConfig"]["filters"][0]
    alias = f["filter"]["From"][0]["Name"]
    assert alias == "s"
    source_ref = f["filter"]["Where"][0]["Condition"]["In"]["Expressions"][0]
    assert source_ref["Column"]["Expression"]["SourceRef"]["Source"] == "s"


def test_filter_add_categorical_custom_name(definition_path: Path) -> None:
    """filter_add_categorical uses the provided name when given."""
    result = filter_add_categorical(
        definition_path, "page_overview", "Sales", "Region", ["East"], name="myfilter123"
    )
    assert result["name"] == "myfilter123"
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    f = _read(page_json)["filterConfig"]["filters"][0]
    assert f["name"] == "myfilter123"


# ---------------------------------------------------------------------------
# filter_add_categorical (visual scope)
# ---------------------------------------------------------------------------


def test_filter_add_categorical_visual_scope(definition_path: Path) -> None:
    """filter_add_categorical adds a visual filter with scope='visual' and no howCreated."""
    result = filter_add_categorical(
        definition_path,
        "page_overview",
        "financials",
        "Segment",
        ["SMB"],
        visual_name="visual_abc123",
    )
    assert result["scope"] == "visual"

    visual_json = (
        definition_path / "pages" / "page_overview" / "visuals" / "visual_abc123" / "visual.json"
    )
    f = _read(visual_json)["filterConfig"]["filters"][0]
    assert "howCreated" not in f
    assert f["type"] == "Categorical"


def test_filter_list_visual_after_add(definition_path: Path) -> None:
    """filter_list on a visual returns the added filter."""
    filter_add_categorical(
        definition_path,
        "page_overview",
        "Sales",
        "Year",
        ["2024"],
        visual_name="visual_abc123",
    )
    result = filter_list(definition_path, "page_overview", visual_name="visual_abc123")
    assert len(result) == 1
    assert result[0]["type"] == "Categorical"


# ---------------------------------------------------------------------------
# filter_remove
# ---------------------------------------------------------------------------


def test_filter_remove_removes_by_name(definition_path: Path) -> None:
    """filter_remove deletes the correct filter and leaves others intact."""
    filter_add_categorical(
        definition_path, "page_overview", "Sales", "Region", ["East"], name="filter_a"
    )
    filter_add_categorical(
        definition_path, "page_overview", "Sales", "Product", ["Widget"], name="filter_b"
    )
    result = filter_remove(definition_path, "page_overview", "filter_a")
    assert result == {"status": "removed", "name": "filter_a"}

    remaining = filter_list(definition_path, "page_overview")
    assert len(remaining) == 1
    assert remaining[0]["name"] == "filter_b"


def test_filter_remove_raises_for_unknown_name(definition_path: Path) -> None:
    """filter_remove raises PbiCliError when the filter name does not exist."""
    with pytest.raises(PbiCliError, match="not found"):
        filter_remove(definition_path, "page_overview", "does_not_exist")


def test_filter_remove_visual(definition_path: Path) -> None:
    """filter_remove works on visual-level filters."""
    filter_add_categorical(
        definition_path,
        "page_overview",
        "Sales",
        "Year",
        ["2024"],
        visual_name="visual_abc123",
        name="vis_filter_x",
    )
    result = filter_remove(
        definition_path, "page_overview", "vis_filter_x", visual_name="visual_abc123"
    )
    assert result["status"] == "removed"
    assert filter_list(definition_path, "page_overview", visual_name="visual_abc123") == []


# ---------------------------------------------------------------------------
# filter_clear
# ---------------------------------------------------------------------------


def test_filter_clear_removes_all(definition_path: Path) -> None:
    """filter_clear removes every filter and returns the correct count."""
    filter_add_categorical(definition_path, "page_overview", "Sales", "Region", ["East"], name="f1")
    filter_add_categorical(
        definition_path, "page_overview", "Sales", "Product", ["Widget"], name="f2"
    )
    result = filter_clear(definition_path, "page_overview")
    assert result == {"status": "cleared", "removed": 2, "scope": "page"}
    assert filter_list(definition_path, "page_overview") == []


def test_filter_clear_empty_page(definition_path: Path) -> None:
    """filter_clear on a page with no filters returns removed=0."""
    result = filter_clear(definition_path, "page_overview")
    assert result["removed"] == 0
    assert result["scope"] == "page"


def test_filter_clear_visual_scope(definition_path: Path) -> None:
    """filter_clear on a visual uses scope='visual'."""
    filter_add_categorical(
        definition_path,
        "page_overview",
        "Sales",
        "Year",
        ["2024"],
        visual_name="visual_abc123",
    )
    result = filter_clear(definition_path, "page_overview", visual_name="visual_abc123")
    assert result["scope"] == "visual"
    assert result["removed"] == 1
    assert filter_list(definition_path, "page_overview", visual_name="visual_abc123") == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_filter_list_no_filter_config_key(definition_path: Path) -> None:
    """filter_list gracefully returns [] when filterConfig key is absent."""
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    data = _read(page_json)
    data.pop("filterConfig", None)
    _write(page_json, data)
    assert filter_list(definition_path, "page_overview") == []


def test_multiple_adds_accumulate(definition_path: Path) -> None:
    """Each call to filter_add_categorical appends rather than replaces."""
    for i in range(3):
        filter_add_categorical(
            definition_path,
            "page_overview",
            "Sales",
            "Region",
            [f"Region{i}"],
            name=f"filter_{i}",
        )
    result = filter_list(definition_path, "page_overview")
    assert len(result) == 3


# ---------------------------------------------------------------------------
# filter_add_topn
# ---------------------------------------------------------------------------


def test_filter_add_topn_returns_status(definition_path: Path) -> None:
    """filter_add_topn returns the expected status dict."""
    result = filter_add_topn(
        definition_path,
        "page_overview",
        table="financials",
        column="Country",
        n=3,
        order_by_table="financials",
        order_by_column="Sales",
    )
    assert result["status"] == "added"
    assert result["type"] == "TopN"
    assert result["scope"] == "page"
    assert result["n"] == 3
    assert result["direction"] == "Top"
    assert "name" in result


def test_filter_add_topn_persisted(definition_path: Path) -> None:
    """filter_add_topn writes a TopN filter entry to page.json."""
    filter_add_topn(
        definition_path,
        "page_overview",
        table="financials",
        column="Country",
        n=3,
        order_by_table="financials",
        order_by_column="Sales",
        name="topn_test",
    )
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    data = _read(page_json)
    filters = data["filterConfig"]["filters"]
    assert len(filters) == 1
    f = filters[0]
    assert f["type"] == "TopN"
    assert f["name"] == "topn_test"
    assert f["howCreated"] == "User"


def test_filter_add_topn_subquery_structure(definition_path: Path) -> None:
    """The TopN filter has the correct Subquery/From/Where structure."""
    filter_add_topn(
        definition_path,
        "page_overview",
        table="financials",
        column="Country",
        n=5,
        order_by_table="financials",
        order_by_column="Sales",
        name="topn_struct",
    )
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    f = _read(page_json)["filterConfig"]["filters"][0]["filter"]

    assert f["Version"] == 2
    assert len(f["From"]) == 2

    subquery_entry = f["From"][0]
    assert subquery_entry["Name"] == "subquery"
    assert subquery_entry["Type"] == 2
    query = subquery_entry["Expression"]["Subquery"]["Query"]
    assert query["Top"] == 5

    where = f["Where"][0]["Condition"]["In"]
    assert "Table" in where
    assert where["Table"]["SourceRef"]["Source"] == "subquery"


def test_filter_add_topn_direction_bottom(definition_path: Path) -> None:
    """direction='Bottom' produces PBI Direction=1 in the OrderBy."""
    filter_add_topn(
        definition_path,
        "page_overview",
        table="financials",
        column="Country",
        n=3,
        order_by_table="financials",
        order_by_column="Profit",
        direction="Bottom",
        name="topn_bottom",
    )
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    f = _read(page_json)["filterConfig"]["filters"][0]["filter"]
    query = f["From"][0]["Expression"]["Subquery"]["Query"]
    assert query["OrderBy"][0]["Direction"] == 1


def test_filter_add_topn_invalid_direction(definition_path: Path) -> None:
    """filter_add_topn raises PbiCliError for an unknown direction."""
    with pytest.raises(PbiCliError):
        filter_add_topn(
            definition_path,
            "page_overview",
            table="financials",
            column="Country",
            n=3,
            order_by_table="financials",
            order_by_column="Sales",
            direction="Middle",
        )


def test_filter_add_topn_visual_scope(definition_path: Path) -> None:
    """filter_add_topn adds a visual filter with scope='visual' and no howCreated."""
    result = filter_add_topn(
        definition_path,
        "page_overview",
        table="financials",
        column="Country",
        n=3,
        order_by_table="financials",
        order_by_column="Sales",
        visual_name="visual_abc123",
    )
    assert result["scope"] == "visual"
    visual_json = (
        definition_path / "pages" / "page_overview" / "visuals" / "visual_abc123" / "visual.json"
    )
    f = _read(visual_json)["filterConfig"]["filters"][0]
    assert "howCreated" not in f


# ---------------------------------------------------------------------------
# filter_add_relative_date
# ---------------------------------------------------------------------------


def test_filter_add_relative_date_returns_status(definition_path: Path) -> None:
    """filter_add_relative_date returns the expected status dict."""
    result = filter_add_relative_date(
        definition_path,
        "page_overview",
        table="financials",
        column="Date",
        amount=3,
        time_unit="months",
    )
    assert result["status"] == "added"
    assert result["type"] == "RelativeDate"
    assert result["scope"] == "page"
    assert result["amount"] == 3
    assert result["time_unit"] == "months"


def test_filter_add_relative_date_persisted(definition_path: Path) -> None:
    """filter_add_relative_date writes a RelativeDate entry to page.json."""
    filter_add_relative_date(
        definition_path,
        "page_overview",
        table="financials",
        column="Date",
        amount=3,
        time_unit="months",
        name="reldate_test",
    )
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    data = _read(page_json)
    filters = data["filterConfig"]["filters"]
    assert len(filters) == 1
    f = filters[0]
    assert f["type"] == "RelativeDate"
    assert f["name"] == "reldate_test"
    assert f["howCreated"] == "User"


def test_filter_add_relative_date_between_structure(definition_path: Path) -> None:
    """The RelativeDate filter uses a Between/DateAdd/DateSpan/Now structure."""
    filter_add_relative_date(
        definition_path,
        "page_overview",
        table="financials",
        column="Date",
        amount=3,
        time_unit="months",
    )
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    f = _read(page_json)["filterConfig"]["filters"][0]["filter"]

    assert f["Version"] == 2
    between = f["Where"][0]["Condition"]["Between"]
    assert "LowerBound" in between
    assert "UpperBound" in between

    # UpperBound is DateSpan(Now(), days)
    upper = between["UpperBound"]["DateSpan"]
    assert "Now" in upper["Expression"]
    assert upper["TimeUnit"] == 0  # days

    # LowerBound: DateSpan(DateAdd(DateAdd(Now(), +1, days), -amount, time_unit), days)
    lower_date_add = between["LowerBound"]["DateSpan"]["Expression"]["DateAdd"]
    assert lower_date_add["Amount"] == -3
    assert lower_date_add["TimeUnit"] == 2  # months
    inner = lower_date_add["Expression"]["DateAdd"]
    assert inner["Amount"] == 1
    assert inner["TimeUnit"] == 0  # days


def test_filter_add_relative_date_time_unit_years(definition_path: Path) -> None:
    """time_unit='years' maps to TimeUnit=3 in the DateAdd."""
    filter_add_relative_date(
        definition_path,
        "page_overview",
        table="financials",
        column="Date",
        amount=1,
        time_unit="years",
    )
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    f = _read(page_json)["filterConfig"]["filters"][0]["filter"]
    lower_span = f["Where"][0]["Condition"]["Between"]["LowerBound"]["DateSpan"]
    lower_date_add = lower_span["Expression"]["DateAdd"]
    assert lower_date_add["TimeUnit"] == 3  # years


def test_filter_add_relative_date_invalid_unit(definition_path: Path) -> None:
    """filter_add_relative_date raises PbiCliError for an unknown time_unit."""
    with pytest.raises(PbiCliError):
        filter_add_relative_date(
            definition_path,
            "page_overview",
            table="financials",
            column="Date",
            amount=3,
            time_unit="quarters",
        )


def test_filter_add_relative_date_visual_scope(definition_path: Path) -> None:
    """filter_add_relative_date adds a visual filter with no howCreated key."""
    result = filter_add_relative_date(
        definition_path,
        "page_overview",
        table="financials",
        column="Date",
        amount=7,
        time_unit="days",
        visual_name="visual_abc123",
    )
    assert result["scope"] == "visual"
    visual_json = (
        definition_path / "pages" / "page_overview" / "visuals" / "visual_abc123" / "visual.json"
    )
    f = _read(visual_json)["filterConfig"]["filters"][0]
    assert "howCreated" not in f


# ---------------------------------------------------------------------------
# filter_add_advanced
# ---------------------------------------------------------------------------


def test_filter_add_advanced_measure_structure(definition_path: Path) -> None:
    """filter_add_advanced writes a Comparison filter over a measure."""
    result = filter_add_advanced(
        definition_path,
        "page_overview",
        table="Manager Level Selector",
        property_name="Valid Manager (L2-L5 Only)",
        is_measure=True,
        op="eq",
        value="1",
    )
    assert result["status"] == "added"
    assert result["type"] == "Advanced"
    assert result["scope"] == "page"
    assert result["op"] == "eq"
    assert result["value"] == "1"

    page_json = definition_path / "pages" / "page_overview" / "page.json"
    f = _read(page_json)["filterConfig"]["filters"][0]
    assert f["type"] == "Advanced"
    assert f["field"]["Measure"]["Property"] == "Valid Manager (L2-L5 Only)"
    assert f["field"]["Measure"]["Expression"]["SourceRef"]["Entity"] == "Manager Level Selector"
    assert f["howCreated"] == "User"

    body = f["filter"]
    assert body["Version"] == 2
    assert body["From"][0]["Name"] == "m"
    assert body["From"][0]["Entity"] == "Manager Level Selector"

    comparison = body["Where"][0]["Condition"]["Comparison"]
    assert comparison["ComparisonKind"] == 0  # eq
    assert comparison["Left"]["Measure"]["Property"] == "Valid Manager (L2-L5 Only)"
    assert comparison["Left"]["Measure"]["Expression"]["SourceRef"]["Source"] == "m"
    assert comparison["Right"]["Literal"]["Value"] == "1L"


def test_filter_add_advanced_op_mapping(definition_path: Path) -> None:
    """op names map to the correct ComparisonKind integer."""
    filter_add_advanced(
        definition_path,
        "page_overview",
        table="Sales",
        property_name="Revenue",
        op="gte",
        value="100",
    )
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    comparison = _read(page_json)["filterConfig"]["filters"][0]["filter"]["Where"][0]["Condition"][
        "Comparison"
    ]
    assert comparison["ComparisonKind"] == 3  # gte
    assert comparison["Right"]["Literal"]["Value"] == "100L"


def test_filter_add_advanced_column_reference(definition_path: Path) -> None:
    """is_measure=False produces a Column reference instead of a Measure."""
    filter_add_advanced(
        definition_path,
        "page_overview",
        table="Sales",
        property_name="Year",
        is_measure=False,
        op="gte",
        value="2024",
    )
    page_json = definition_path / "pages" / "page_overview" / "page.json"
    f = _read(page_json)["filterConfig"]["filters"][0]
    assert "Column" in f["field"]
    assert "Measure" not in f["field"]
    left = f["filter"]["Where"][0]["Condition"]["Comparison"]["Left"]
    assert "Column" in left


def test_filter_add_advanced_visual_scope(definition_path: Path) -> None:
    """filter_add_advanced adds a visual filter with no howCreated key."""
    result = filter_add_advanced(
        definition_path,
        "page_overview",
        table="Manager Level Selector",
        property_name="Valid Manager (L2-L5 Only)",
        visual_name="visual_abc123",
    )
    assert result["scope"] == "visual"
    visual_json = (
        definition_path / "pages" / "page_overview" / "visuals" / "visual_abc123" / "visual.json"
    )
    f = _read(visual_json)["filterConfig"]["filters"][0]
    assert "howCreated" not in f
    assert f["type"] == "Advanced"


def test_filter_add_advanced_invalid_op(definition_path: Path) -> None:
    """filter_add_advanced raises PbiCliError for an unknown operator."""
    with pytest.raises(PbiCliError, match="op must be one of"):
        filter_add_advanced(
            definition_path,
            "page_overview",
            table="Sales",
            property_name="Revenue",
            op="contains",
        )


# ---------------------------------------------------------------------------
# filter_list summarize
# ---------------------------------------------------------------------------


def test_filter_list_summarize(definition_path: Path) -> None:
    """filter_list with summarize=True returns name/type/field/condition dicts."""
    filter_add_categorical(
        definition_path, "page_overview", "Sales", "Region", ["North", "South"], name="f_cat"
    )
    filter_add_advanced(
        definition_path,
        "page_overview",
        table="Manager Level Selector",
        property_name="Valid Manager (L2-L5 Only)",
        name="f_adv",
    )
    result = filter_list(definition_path, "page_overview", summarize=True)
    assert len(result) == 2

    cat = next(r for r in result if r["name"] == "f_cat")
    assert cat["type"] == "Categorical"
    assert cat["field"] == "Sales[Region]"
    assert "North" in cat["condition"]

    adv = next(r for r in result if r["name"] == "f_adv")
    assert adv["type"] == "Advanced"
    assert adv["field"] == "Manager Level Selector[Valid Manager (L2-L5 Only)]"
    assert adv["condition"] == "eq 1L"


# ---------------------------------------------------------------------------
# filter_where
# ---------------------------------------------------------------------------


def test_filter_where_matches_field(definition_path: Path) -> None:
    """filter_where returns only filters whose field matches the spec."""
    filter_add_categorical(
        definition_path, "page_overview", "Sales", "Region", ["East"], name="f_region"
    )
    filter_add_advanced(
        definition_path,
        "page_overview",
        table="Manager Level Selector",
        property_name="Valid Manager (L2-L5 Only)",
        name="f_valid",
    )

    result = filter_where(
        definition_path,
        "page_overview",
        field_specs=["Manager Level Selector[Valid Manager (L2-L5 Only)]"],
    )
    assert len(result) == 1
    assert result[0]["name"] == "f_valid"


def test_filter_where_bare_field_name(definition_path: Path) -> None:
    """A bare field spec matches on property name alone."""
    filter_add_advanced(
        definition_path,
        "page_overview",
        table="Manager Level Selector",
        property_name="Valid Manager (L2-L5 Only)",
        name="f_valid",
    )
    result = filter_where(
        definition_path, "page_overview", field_specs=["Valid Manager (L2-L5 Only)"]
    )
    assert [f["name"] for f in result] == ["f_valid"]


def test_filter_where_type_filter(definition_path: Path) -> None:
    """filter_where with type_filter restricts to a filter type."""
    filter_add_categorical(
        definition_path, "page_overview", "Sales", "Region", ["East"], name="f_region"
    )
    filter_add_advanced(
        definition_path,
        "page_overview",
        table="Sales",
        property_name="Revenue",
        name="f_rev",
    )
    result = filter_where(
        definition_path, "page_overview", field_specs=["Revenue"], type_filter="Advanced"
    )
    assert [f["name"] for f in result] == ["f_rev"]
