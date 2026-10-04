"""Tests for pbi_cli.core.bulk_backend.

All tests use a minimal in-memory PBIR directory tree with a single page
containing 5 visuals of mixed types.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pbi_cli.core.bulk_backend import (
    visual_bulk_bind,
    visual_bulk_delete,
    visual_bulk_update,
    visual_where,
)
from pbi_cli.core.visual_backend import visual_add, visual_bind, visual_get, visual_set_container

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@pytest.fixture
def multi_visual_page(tmp_path: Path) -> Path:
    """PBIR definition folder with one page containing 5 visuals.

    Layout:
      - BarChart_1  barChart   x=0    y=0
      - BarChart_2  barChart   x=440  y=0
      - BarChart_3  barChart   x=880  y=0
      - Card_1      card       x=0    y=320
      - KPI_1       kpi        x=440  y=320

    Returns the ``definition/`` path.
    """
    definition = tmp_path / "definition"
    definition.mkdir()

    _write_json(
        definition / "version.json",
        {"version": "2.0.0"},
    )
    _write_json(
        definition / "report.json",
        {
            "$schema": "...",
            "themeCollection": {"baseTheme": {"name": "CY24SU06"}},
            "layoutOptimization": "None",
        },
    )

    pages_dir = definition / "pages"
    pages_dir.mkdir()
    _write_json(
        pages_dir / "pages.json",
        {"pageOrder": ["test_page"], "activePageName": "test_page"},
    )

    page_dir = pages_dir / "test_page"
    page_dir.mkdir()
    _write_json(
        page_dir / "page.json",
        {
            "name": "test_page",
            "displayName": "Test Page",
            "displayOption": "FitToPage",
            "width": 1280,
            "height": 720,
            "ordinal": 0,
        },
    )

    visuals_dir = page_dir / "visuals"
    visuals_dir.mkdir()

    # Add 5 visuals via visual_add to get realistic JSON files
    visual_add(definition, "test_page", "bar", name="BarChart_1", x=0, y=0, width=400, height=300)
    visual_add(definition, "test_page", "bar", name="BarChart_2", x=440, y=0, width=400, height=300)
    visual_add(definition, "test_page", "bar", name="BarChart_3", x=880, y=0, width=400, height=300)
    visual_add(definition, "test_page", "card", name="Card_1", x=0, y=320, width=200, height=120)
    visual_add(definition, "test_page", "kpi", name="KPI_1", x=440, y=320, width=250, height=150)

    return definition


# ---------------------------------------------------------------------------
# visual_where -- filter by type
# ---------------------------------------------------------------------------


def test_where_by_type_returns_correct_subset(multi_visual_page: Path) -> None:
    """visual_where with visual_type='barChart' returns only the 3 bar charts."""
    result = visual_where(multi_visual_page, "test_page", visual_type="barChart")

    assert len(result) == 3
    assert all(v["visual_type"] == "barChart" for v in result)


def test_where_by_alias_resolves_type(multi_visual_page: Path) -> None:
    """visual_where accepts user-friendly alias 'bar' and resolves it."""
    result = visual_where(multi_visual_page, "test_page", visual_type="bar")

    assert len(result) == 3


def test_where_by_type_card(multi_visual_page: Path) -> None:
    result = visual_where(multi_visual_page, "test_page", visual_type="card")

    assert len(result) == 1
    assert result[0]["name"] == "Card_1"


def test_where_no_filter_returns_all(multi_visual_page: Path) -> None:
    """visual_where with no filters returns all 5 visuals."""
    result = visual_where(multi_visual_page, "test_page")

    assert len(result) == 5


def test_where_by_name_pattern(multi_visual_page: Path) -> None:
    """visual_where with name_pattern='BarChart_*' returns 3 matching visuals."""
    result = visual_where(multi_visual_page, "test_page", name_pattern="BarChart_*")

    assert len(result) == 3
    assert all(v["name"].startswith("BarChart_") for v in result)


def test_where_by_x_max(multi_visual_page: Path) -> None:
    """visual_where with x_max=400 returns visuals at x=0 only (left column)."""
    result = visual_where(multi_visual_page, "test_page", x_max=400)

    names = {v["name"] for v in result}
    assert "BarChart_1" in names
    assert "Card_1" in names
    assert "BarChart_3" not in names


def test_where_by_y_min(multi_visual_page: Path) -> None:
    """visual_where with y_min=300 returns only visuals below y=300."""
    result = visual_where(multi_visual_page, "test_page", y_min=300)

    names = {v["name"] for v in result}
    assert "Card_1" in names
    assert "KPI_1" in names
    assert "BarChart_1" not in names


def test_where_type_and_position_combined(multi_visual_page: Path) -> None:
    """Combining type and x_max narrows results correctly."""
    result = visual_where(multi_visual_page, "test_page", visual_type="barChart", x_max=400)

    assert len(result) == 1
    assert result[0]["name"] == "BarChart_1"


def test_where_nonexistent_type_returns_empty(multi_visual_page: Path) -> None:
    result = visual_where(multi_visual_page, "test_page", visual_type="lineChart")

    assert result == []


# ---------------------------------------------------------------------------
# visual_bulk_bind
# ---------------------------------------------------------------------------


def test_bulk_bind_applies_to_all_matching(multi_visual_page: Path) -> None:
    """visual_bulk_bind applies bindings to all 3 bar charts."""
    result = visual_bulk_bind(
        multi_visual_page,
        "test_page",
        visual_type="barChart",
        bindings=[{"role": "category", "field": "Date[Month]"}],
    )

    assert result["bound"] == 3
    assert set(result["visuals"]) == {"BarChart_1", "BarChart_2", "BarChart_3"}

    # Verify the projection was written to each visual
    for name in result["visuals"]:
        vfile = multi_visual_page / "pages" / "test_page" / "visuals" / name / "visual.json"
        data = json.loads(vfile.read_text(encoding="utf-8"))
        projections = data["visual"]["query"]["queryState"]["Category"]["projections"]
        assert len(projections) == 1
        assert projections[0]["nativeQueryRef"] == "Month"


def test_bulk_bind_with_name_pattern(multi_visual_page: Path) -> None:
    """visual_bulk_bind with name_pattern restricts to matching visuals only."""
    result = visual_bulk_bind(
        multi_visual_page,
        "test_page",
        visual_type="barChart",
        bindings=[{"role": "value", "field": "Sales[Revenue]"}],
        name_pattern="BarChart_1",
    )

    assert result["bound"] == 1
    assert result["visuals"] == ["BarChart_1"]


def test_bulk_bind_returns_zero_when_no_match(multi_visual_page: Path) -> None:
    result = visual_bulk_bind(
        multi_visual_page,
        "test_page",
        visual_type="lineChart",
        bindings=[{"role": "value", "field": "Sales[Revenue]"}],
    )

    assert result["bound"] == 0
    assert result["visuals"] == []


# ---------------------------------------------------------------------------
# visual_bulk_update
# ---------------------------------------------------------------------------


def test_bulk_update_sets_height_for_all_matching(multi_visual_page: Path) -> None:
    """visual_bulk_update resizes all bar charts."""
    result = visual_bulk_update(
        multi_visual_page,
        "test_page",
        where_type="barChart",
        set_height=250,
    )

    assert result["updated"] == 3

    for name in result["visuals"]:
        info = visual_get(multi_visual_page, "test_page", name)
        assert info["height"] == 250


def test_bulk_update_hides_by_name_pattern(multi_visual_page: Path) -> None:
    result = visual_bulk_update(
        multi_visual_page,
        "test_page",
        where_name_pattern="BarChart_*",
        set_hidden=True,
    )

    assert result["updated"] == 3
    for name in result["visuals"]:
        info = visual_get(multi_visual_page, "test_page", name)
        assert info["is_hidden"] is True


def test_bulk_update_requires_at_least_one_setter(multi_visual_page: Path) -> None:
    """visual_bulk_update raises ValueError when no set_* arg provided."""
    with pytest.raises(ValueError, match="At least one set_"):
        visual_bulk_update(
            multi_visual_page,
            "test_page",
            where_type="barChart",
        )


# ---------------------------------------------------------------------------
# visual_bulk_delete
# ---------------------------------------------------------------------------


def test_bulk_delete_removes_matching_visuals(multi_visual_page: Path) -> None:
    result = visual_bulk_delete(
        multi_visual_page,
        "test_page",
        where_type="barChart",
    )

    assert result["deleted"] == 3
    assert set(result["visuals"]) == {"BarChart_1", "BarChart_2", "BarChart_3"}

    # Confirm folders are gone
    visuals_dir = multi_visual_page / "pages" / "test_page" / "visuals"
    remaining = {d.name for d in visuals_dir.iterdir() if d.is_dir()}
    assert "BarChart_1" not in remaining
    assert "Card_1" in remaining
    assert "KPI_1" in remaining


def test_bulk_delete_by_name_pattern(multi_visual_page: Path) -> None:
    result = visual_bulk_delete(
        multi_visual_page,
        "test_page",
        where_name_pattern="BarChart_*",
    )

    assert result["deleted"] == 3


def test_bulk_delete_requires_filter(multi_visual_page: Path) -> None:
    """visual_bulk_delete raises ValueError when no filter given."""
    with pytest.raises(ValueError, match="Provide at least"):
        visual_bulk_delete(multi_visual_page, "test_page")


def test_bulk_delete_returns_zero_when_no_match(multi_visual_page: Path) -> None:
    result = visual_bulk_delete(
        multi_visual_page,
        "test_page",
        where_type="lineChart",
    )

    assert result["deleted"] == 0
    assert result["visuals"] == []


# ---------------------------------------------------------------------------
# visual_where -- title pattern, field usage, all-pages
# ---------------------------------------------------------------------------


def test_where_by_title_pattern(multi_visual_page: Path) -> None:
    """visual_where with title_pattern matches a visual by its literal title."""
    visual_set_container(multi_visual_page, "test_page", "BarChart_1", title="Revenue by Region")
    result = visual_where(multi_visual_page, "test_page", title_pattern="Revenue *")
    assert [v["name"] for v in result] == ["BarChart_1"]
    assert result[0]["title"] == "Revenue by Region"


def test_where_by_title_pattern_no_measure_title(multi_visual_page: Path) -> None:
    """Visuals with no title (or measure-driven titles) are skipped."""
    result = visual_where(multi_visual_page, "test_page", title_pattern="*")
    assert result == []


def test_where_uses_measure(multi_visual_page: Path) -> None:
    """visual_where with uses_measure matches visuals referencing that measure."""
    visual_bind(
        multi_visual_page, "test_page", "BarChart_1", [{"role": "value", "field": "Sales[Revenue]"}]
    )
    visual_bind(
        multi_visual_page, "test_page", "BarChart_2", [{"role": "value", "field": "Sales[Margin]"}]
    )
    result = visual_where(multi_visual_page, "test_page", uses_measure=["Sales[Revenue]"])
    assert [v["name"] for v in result] == ["BarChart_1"]


def test_where_uses_measure_bare_name(multi_visual_page: Path) -> None:
    """A bare measure name matches across tables."""
    visual_bind(
        multi_visual_page, "test_page", "BarChart_1", [{"role": "value", "field": "Sales[Revenue]"}]
    )
    result = visual_where(multi_visual_page, "test_page", uses_measure=["Revenue"])
    assert [v["name"] for v in result] == ["BarChart_1"]


def test_where_uses_measure_excludes_columns(multi_visual_page: Path) -> None:
    """uses_measure must not match a column-only reference."""
    visual_bind(
        multi_visual_page, "test_page", "BarChart_3", [{"role": "category", "field": "Date[Month]"}]
    )
    result = visual_where(multi_visual_page, "test_page", uses_measure=["Date[Month]"])
    assert result == []


def test_where_uses_field_matches_any_kind(multi_visual_page: Path) -> None:
    """uses_field matches both measures and columns."""
    visual_bind(
        multi_visual_page, "test_page", "BarChart_1", [{"role": "value", "field": "Sales[Revenue]"}]
    )
    visual_bind(
        multi_visual_page, "test_page", "BarChart_3", [{"role": "category", "field": "Date[Month]"}]
    )
    result = visual_where(multi_visual_page, "test_page", uses_field=["Date[Month]"])
    assert [v["name"] for v in result] == ["BarChart_3"]


def test_where_all_pages_annotates_page(multi_visual_page: Path) -> None:
    """visual_where with page_name=None searches every page and adds a page key."""
    page_two = multi_visual_page / "pages" / "page_two"
    page_two.mkdir(exist_ok=True)
    (page_two / "visuals").mkdir(exist_ok=True)
    _write_json(
        page_two / "page.json",
        {
            "name": "page_two",
            "displayName": "Page Two",
            "displayOption": "FitToPage",
            "width": 1280,
            "height": 720,
            "ordinal": 1,
        },
    )
    visual_add(multi_visual_page, "page_two", "card", name="Card_P2")

    result = visual_where(multi_visual_page, page_name=None)
    assert len(result) == 6
    assert all("page" in v for v in result)
    pairs = {(v["name"], v["page"]) for v in result}
    assert ("Card_P2", "page_two") in pairs
    assert ("BarChart_1", "test_page") in pairs


def test_where_all_pages_uses_measure(multi_visual_page: Path) -> None:
    """all-pages + uses_measure narrows across pages correctly."""
    page_two = multi_visual_page / "pages" / "page_two"
    page_two.mkdir(exist_ok=True)
    (page_two / "visuals").mkdir(exist_ok=True)
    _write_json(
        page_two / "page.json",
        {
            "name": "page_two",
            "displayName": "Page Two",
            "displayOption": "FitToPage",
            "width": 1280,
            "height": 720,
            "ordinal": 1,
        },
    )
    visual_add(multi_visual_page, "page_two", "card", name="Card_P2")
    visual_bind(
        multi_visual_page, "page_two", "Card_P2", [{"role": "field", "field": "Sales[Revenue]"}]
    )
    visual_bind(
        multi_visual_page, "test_page", "BarChart_1", [{"role": "value", "field": "Sales[Revenue]"}]
    )

    result = visual_where(multi_visual_page, page_name=None, uses_measure=["Sales[Revenue]"])
    assert {(v["name"], v["page"]) for v in result} == {
        ("Card_P2", "page_two"),
        ("BarChart_1", "test_page"),
    }
