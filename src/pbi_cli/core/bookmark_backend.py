"""Pure-function backend for PBIR bookmark operations.

Mirrors ``report_backend.py`` but operates on the bookmarks subfolder.
Every function takes a ``Path`` to the definition folder and returns a plain
Python dict suitable for ``format_result()``.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from pbi_cli.core.errors import PbiCliError

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

SCHEMA_BOOKMARKS_METADATA = (
    "https://developer.microsoft.com/json-schemas/"
    "fabric/item/report/definition/bookmarksMetadata/1.0.0/schema.json"
)
SCHEMA_BOOKMARK = (
    "https://developer.microsoft.com/json-schemas/"
    "fabric/item/report/definition/bookmark/2.1.0/schema.json"
)

# Visual types that render data (charts / tables / cards). These are the only
# candidates for a "selected visuals" bookmark scope. Slicers/filters
# ("slicer", "advancedSlicerVisual", "filterVisual") and chrome ("actionButton",
# "shape", "textbox", "image", "pageNavigator", "bookmarkNavigator") are
# deliberately excluded so that toggling a bookmark never resets page filters.
DATA_VISUAL_TYPES = frozenset(
    {
        "pivotTable",
        "tableEx",
        "matrix",
        "lineChart",
        "areaChart",
        "stackedAreaChart",
        "clusteredColumnChart",
        "stackedColumnChart",
        "clusteredBarChart",
        "stackedBarChart",
        "ribbonChart",
        "waterfallChart",
        "scatterChart",
        "pieChart",
        "donutChart",
        "funnel",
        "gauge",
        "kpi",
        "card",
        "cardVisual",
        "cardMultiRow",
        "lineClusteredColumnComboChart",
        "lineStackedColumnComboChart",
        "map",
        "shapeMap",
        "decompositionTreeVisual",
        "keyDriversVisual",
        "influencerVisual",
        "qnaVisual",
    }
)

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
# Path helpers
# ---------------------------------------------------------------------------


def _bookmarks_dir(definition_path: Path) -> Path:
    return definition_path / "bookmarks"


def _index_path(definition_path: Path) -> Path:
    return _bookmarks_dir(definition_path) / "bookmarks.json"


def _bookmark_path(definition_path: Path, name: str) -> Path:
    return _bookmarks_dir(definition_path) / f"{name}.bookmark.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def bookmark_list(definition_path: Path) -> list[dict[str, Any]]:
    """List all bookmarks.

    Returns a list of ``{name, display_name, active_section}`` dicts.
    Returns ``[]`` if the bookmarks folder or index does not exist.
    """
    index_file = _index_path(definition_path)
    if not index_file.exists():
        return []

    index = _read_json(index_file)
    items: list[dict[str, Any]] = index.get("items", [])

    results: list[dict[str, Any]] = []
    for item in items:
        name = item.get("name", "")
        bm_file = _bookmark_path(definition_path, name)
        if not bm_file.exists():
            continue
        bm = _read_json(bm_file)
        exploration = bm.get("explorationState", {})
        results.append(
            {
                "name": name,
                "display_name": bm.get("displayName", ""),
                "active_section": exploration.get("activeSection"),
            }
        )

    return results


def bookmark_get(definition_path: Path, name: str) -> dict[str, Any]:
    """Get the full data for a single bookmark by name.

    Raises ``PbiCliError`` if the bookmark does not exist.
    """
    bm_file = _bookmark_path(definition_path, name)
    if not bm_file.exists():
        raise PbiCliError(f"Bookmark '{name}' not found.")
    return _read_json(bm_file)


def bookmark_add(
    definition_path: Path,
    display_name: str,
    target_page: str,
    name: str | None = None,
) -> dict[str, Any]:
    """Create a new bookmark pointing to *target_page*.

    Creates the ``bookmarks/`` directory and ``bookmarks.json`` index if they
    do not already exist. Returns a status dict with the created bookmark info.
    """
    bm_name = name if name is not None else _generate_name()

    bm_dir = _bookmarks_dir(definition_path)
    bm_dir.mkdir(parents=True, exist_ok=True)

    index_file = _index_path(definition_path)
    if index_file.exists():
        index = _read_json(index_file)
    else:
        index = {"$schema": SCHEMA_BOOKMARKS_METADATA, "items": []}

    index["items"] = list(index.get("items", []))
    index["items"].append({"name": bm_name})
    _write_json(index_file, index)

    bookmark_data: dict[str, Any] = {
        "$schema": SCHEMA_BOOKMARK,
        "displayName": display_name,
        "name": bm_name,
        "options": {"targetVisualNames": []},
        "explorationState": {
            "version": "1.3",
            "activeSection": target_page,
        },
    }
    _write_json(_bookmark_path(definition_path, bm_name), bookmark_data)

    return {
        "status": "created",
        "name": bm_name,
        "display_name": display_name,
        "target_page": target_page,
    }


def bookmark_delete(
    definition_path: Path,
    name: str,
) -> dict[str, Any]:
    """Delete a bookmark by name.

    Removes the ``.bookmark.json`` file and its entry in ``bookmarks.json``.
    Raises ``PbiCliError`` if the bookmark is not found.
    """
    index_file = _index_path(definition_path)
    if not index_file.exists():
        raise PbiCliError(f"Bookmark '{name}' not found.")

    index = _read_json(index_file)
    items: list[dict[str, Any]] = index.get("items", [])
    existing_names = [i.get("name") for i in items]

    if name not in existing_names:
        raise PbiCliError(f"Bookmark '{name}' not found.")

    bm_file = _bookmark_path(definition_path, name)
    if bm_file.exists():
        bm_file.unlink()

    updated_items = [i for i in items if i.get("name") != name]
    updated_index = {**index, "items": updated_items}
    _write_json(index_file, updated_index)

    return {"status": "deleted", "name": name}


def _data_visual_names(bm: dict[str, Any]) -> list[str]:
    """Collect data-visual IDs captured in a bookmark's exploration state.

    Walks ``explorationState.sections.*.visualContainers`` and returns the IDs
    whose ``singleVisual.visualType`` is a data-rendering type (chart/table/
    card). Slicers, buttons, shapes, text boxes and images are excluded.
    Results are sorted for deterministic output.
    """
    exploration = bm.get("explorationState") or {}
    sections = exploration.get("sections") or {}
    data_ids: set[str] = set()
    for _page_id, section in sections.items():
        containers = section.get("visualContainers") or {}
        for visual_id, container in containers.items():
            if not isinstance(container, dict):
                continue
            single = container.get("singleVisual") or {}
            if single.get("visualType") in DATA_VISUAL_TYPES:
                data_ids.add(visual_id)
    return sorted(data_ids)


def bookmark_set_scope(
    definition_path: Path,
    name: str,
    *,
    data_visuals: bool = False,
    all_visuals: bool = False,
    visuals: list[str] | None = None,
    suppress_data: bool = True,
) -> dict[str, Any]:
    """Change a bookmark's scope (All Visuals vs Selected Visuals).

    At most one of *data_visuals*, *all_visuals*, or *visuals* may be supplied.
    When none is given, the scope defaults to *all_visuals*:

    - ``all_visuals=True`` -- target every visual (the Power BI default) by
      clearing ``targetVisualNames`` and removing ``applyOnlyToTargetVisuals``.
    - ``visuals=[...]`` -- target exactly the given visual IDs.
    - ``data_visuals=True`` -- target only the data visuals captured in the
      bookmark (charts/tables/cards), excluding slicers, buttons and chrome.
      NOTE: this is a niche option -- it changes the scope to selected-visuals,
      which also stops the bookmark from hiding/showing non-data visuals such
      as navigation buttons. For view-switch bookmarks prefer ``all_visuals``
      combined with ``suppress_data=True`` (see below).

    ``suppress_data`` controls the bookmark's "Data" setting
    (``options.suppressData``) and defaults to ``True`` -- i.e. unchecking
    "Data" in Power BI. This is the recommended configuration for view-switch
    bookmarks: the bookmark still hides/shows every visual (buttons included),
    but it does NOT save or re-apply data/filter state, so page filters such as
    the time-period slicer persist across bookmark clicks.

    Selected-visuals scopes set ``options.applyOnlyToTargetVisuals`` to
    ``true``.

    Raises ``PbiCliError`` if the bookmark does not exist, or when *data_visuals*
    is requested but the bookmark captures no data visuals.
    """
    modes = [bool(data_visuals), bool(all_visuals), bool(visuals)]
    if sum(modes) > 1:
        raise PbiCliError("At most one of data_visuals, all_visuals, or visuals may be supplied.")

    bm_file = _bookmark_path(definition_path, name)
    if not bm_file.exists():
        raise PbiCliError(f"Bookmark '{name}' not found.")

    bm = _read_json(bm_file)
    options = dict(bm.get("options") or {})

    if data_visuals:
        target = _data_visual_names(bm)
        if not target:
            raise PbiCliError(
                f"Bookmark '{name}' captures no data visuals; cannot derive a "
                "selected-visuals scope."
            )
        options = {**options, "applyOnlyToTargetVisuals": True, "targetVisualNames": target}
        scope = "selected-visuals"
    elif visuals:
        target = sorted(set(visuals or []))
        options = {**options, "applyOnlyToTargetVisuals": True, "targetVisualNames": target}
        scope = "selected-visuals"
    else:
        options.pop("applyOnlyToTargetVisuals", None)
        options["targetVisualNames"] = []
        target = []
        scope = "all-visuals"

    if suppress_data:
        options["suppressData"] = True
    else:
        options.pop("suppressData", None)

    new_bm = {**bm, "options": options}
    _write_json(bm_file, new_bm)

    return {
        "status": "updated",
        "bookmark": name,
        "scope": scope,
        "suppress_data": suppress_data,
        "target_visuals": target,
        "target_count": len(target),
    }


def bookmark_set_visibility(
    definition_path: Path,
    name: str,
    page_name: str,
    visual_name: str,
    hidden: bool,
) -> dict[str, Any]:
    """Set a visual's hidden/visible state inside a bookmark's explorationState.

    When *hidden* is ``True``, sets ``singleVisual.display.mode = "hidden"``.
    When *hidden* is ``False``, removes the ``display`` key from ``singleVisual``
    (presence of ``display`` is what hides the visual in Power BI Desktop).

    Creates the ``explorationState.sections.{page_name}.visualContainers.{visual_name}``
    path if it does not already exist in the bookmark.

    Raises ``PbiCliError`` if the bookmark does not exist.
    Returns a status dict with name, page, visual, and the new visibility state.
    """
    bm_file = _bookmark_path(definition_path, name)
    if not bm_file.exists():
        raise PbiCliError(f"Bookmark '{name}' not found.")

    bm = _read_json(bm_file)

    # Navigate / build the explorationState path immutably.
    exploration = dict(bm.get("explorationState") or {})
    sections = dict(exploration.get("sections") or {})
    page_section = dict(sections.get(page_name) or {})
    visual_containers = dict(page_section.get("visualContainers") or {})
    container = dict(visual_containers.get(visual_name) or {})
    single_visual = dict(container.get("singleVisual") or {})

    if hidden:
        single_visual = {**single_visual, "display": {"mode": "hidden"}}
    else:
        single_visual = {k: v for k, v in single_visual.items() if k != "display"}

    new_container = {**container, "singleVisual": single_visual}
    new_visual_containers = {**visual_containers, visual_name: new_container}
    new_page_section = {**page_section, "visualContainers": new_visual_containers}
    new_sections = {**sections, page_name: new_page_section}
    new_exploration = {**exploration, "sections": new_sections}
    new_bm = {**bm, "explorationState": new_exploration}

    _write_json(bm_file, new_bm)

    return {
        "status": "updated",
        "bookmark": name,
        "page": page_name,
        "visual": visual_name,
        "hidden": hidden,
    }
