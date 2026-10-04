"""Tests for pbi_cli.core.deps_backend (static table dependency analysis).

Builds a minimal PBIP project (SemanticModel + Report) in tmp_path and
verifies per-table classification: used-report, used-model, unused,
review, and auto-date exclusion.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pbi_cli.core.deps_backend import model_deps

_AUTO_DATE_NAME = "LocalDateTable_00f04e14-35d4-43b1-9efd-69379a2a5b9e"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _table_tmdl(name: str, body: str = "") -> str:
    return f"table {name}\n{body}"


@pytest.fixture()
def pbip(tmp_path: Path) -> Path:
    """Minimal PBIP: 6 tables exercising every classification branch."""
    sm = tmp_path / "proj.SemanticModel" / "definition"
    rp = tmp_path / "proj.Report" / "definition"

    _write(
        sm / "model.tmdl",
        "model Model\n"
        "\tref table Fact\n"
        "\tref table Dim\n"
        "\tref table Orphan\n"
        "\tref table Island\n"
        "\tref table Bridge\n"
        "\tref table Stale\n",
    )
    _write(sm / "database.tmdl", "database db\n")
    _write(
        sm / "relationships.tmdl",
        "relationship r1\n\tfromColumn: Fact.dim_id\n\ttoColumn: Dim.id\n\n"
        "relationship AutoDetected_x\n\tfromColumn: Island.k\n\ttoColumn: Bridge.k\n",
    )

    _write(sm / "tables" / "Fact.tmdl", _table_tmdl("Fact"))
    _write(sm / "tables" / "Dim.tmdl", _table_tmdl("Dim"))
    _write(sm / "tables" / "Orphan.tmdl", _table_tmdl("Orphan"))
    _write(sm / "tables" / "Island.tmdl", _table_tmdl("Island"))
    _write(sm / "tables" / "Bridge.tmdl", _table_tmdl("Bridge"))
    _write(sm / "tables" / "Stale.tmdl", _table_tmdl("Stale"))
    _write(sm / "tables" / f"{_AUTO_DATE_NAME}.tmdl", _table_tmdl(_AUTO_DATE_NAME))

    # Measure in Fact referencing Dim -> Dim is used-model via DAX too
    _write(
        sm / "tables" / "Measures.tmdl",
        "table Measures\n\tmeasure Total = SUM(Dim[Amount])\n",
    )

    # Report: visual references Fact (exact entity); stale selector mentions
    # "Stale" only as a substring inside a longer metadata string.
    _write(rp / "report.json", json.dumps({"name": "report"}))
    _write(
        rp / "pages" / "p1" / "visuals" / "v1" / "visual.json",
        json.dumps(
            {
                "query": {"Entity": "Fact"},
                "selector": {"metadata": "gold Stale.Manager_L2"},
            }
        ),
    )
    return tmp_path


def _by_name(result: dict) -> dict[str, dict]:
    return {t["name"]: t for t in result["tables"]}


def test_classifications(pbip: Path) -> None:
    result = model_deps(pbip / "proj.SemanticModel")
    tables = _by_name(result)

    assert tables["Fact"]["classification"] == "used-report"
    assert tables["Dim"]["classification"] in ("used-model", "used-report")
    assert tables["Orphan"]["classification"] == "unused"
    assert tables["Island"]["classification"] == "review"  # dangling island
    assert tables["Stale"]["classification"] == "review"  # raw-only mention
    assert tables["Bridge"]["classification"] == "review"


def test_auto_date_excluded_by_default(pbip: Path) -> None:
    result = model_deps(pbip / "proj.SemanticModel")
    names = {t["name"] for t in result["tables"]}
    assert _AUTO_DATE_NAME not in names
    assert result["summary"]["auto_date_tables_excluded"] == 1


def test_auto_date_included_with_flag(pbip: Path) -> None:
    result = model_deps(pbip / "proj.SemanticModel", include_auto_date=True)
    tables = _by_name(result)
    assert tables[_AUTO_DATE_NAME]["classification"] == "auto-date"
    assert result["summary"]["auto_date_tables_excluded"] == 0


def test_report_autodetect_and_relationship_counts(pbip: Path) -> None:
    result = model_deps(pbip / "proj.SemanticModel")
    assert result["summary"]["report_definition"] is not None
    tables = _by_name(result)
    assert tables["Fact"]["relationships"]["total"] == 1
    assert tables["Dim"]["relationships"]["partners"] == ["Fact"]
    assert tables["Fact"]["report_refs"]["exact"] == 1


def test_model_tmdl_not_counted_as_raw_mention(pbip: Path) -> None:
    """`ref table` lines in model.tmdl are structural, not usage."""
    result = model_deps(pbip / "proj.SemanticModel")
    for t in result["tables"]:
        assert "model.tmdl" not in t["raw_model_mentions"]


def test_path_resolution_from_pbip_and_parent(pbip: Path) -> None:
    _write(pbip / "proj.pbip", "{}")
    from_parent = model_deps(pbip)
    from_pbip = model_deps(pbip / "proj.pbip")
    assert from_parent["summary"]["tables_assessed"] == from_pbip["summary"]["tables_assessed"]


def test_missing_model_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        model_deps(tmp_path)
