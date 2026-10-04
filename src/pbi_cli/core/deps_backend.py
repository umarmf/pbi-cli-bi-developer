"""Static dependency analysis for PBIP semantic models (file-based, no Desktop).

Scans TMDL model files and (optionally) the sibling PBIR report to classify
each table as used (report/model), a deletion candidate, or requiring review.

Auto date/time background tables (``LocalDateTable_*`` / ``DateTableTemplate_*``)
are excluded from the assessment by default: they only work in the background
and only matter when deleting tables via direct TMDL edits.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Auto date/time background tables (excluded from assessment by default)
_AUTO_DATE_RE = re.compile(r"^(LocalDateTable|DateTableTemplate)_[0-9a-fA-F-]{36}$")

# TMDL table declaration: `table Name` or `table 'Name With Space'`
_TABLE_DECL_RE = re.compile(r"(?m)^table\s+(?:'([^']+)'|(\S.*))\s*$")

# Relationship block pieces
_REL_SPLIT_RE = re.compile(r"(?m)^relationship\s+")
_REL_COL_RE = re.compile(r"(?m)(fromColumn|toColumn):\s*(.+?)\.([^\r\n]+?)\s*$")

# Model files that never count as a meaningful reference
_INERT_DIRS = ("cultures",)


def model_deps(
    model_path: Path,
    report_path: Path | None = None,
    include_auto_date: bool = False,
    max_examples: int = 5,
) -> dict[str, Any]:
    """Assess per-table usage in a PBIP project.

    Args:
        model_path: Path to a ``.SemanticModel`` folder, its ``definition``
            folder, a ``.pbip`` file, or a parent folder containing exactly
            one ``.SemanticModel``.
        report_path: Optional path to the ``.Report`` folder (or its
            ``definition``). Auto-detected as a sibling when omitted.
        include_auto_date: Include ``LocalDateTable_*`` / ``DateTableTemplate_*``
            background tables in the table list (class ``auto-date``).
        max_examples: Cap on example file lists per table.

    Returns:
        Dict with ``summary`` and per-table ``tables`` list. Each table has a
        ``classification``: ``used-report`` | ``used-model`` | ``unused`` |
        ``review`` | ``auto-date``, plus ``reasons`` explaining the verdict.
    """
    definition = _resolve_model_definition(model_path)
    report_definition = _resolve_report_definition(definition, report_path)

    tables_dir = definition / "tables"
    table_files: dict[str, Path] = {}
    for f in sorted(tables_dir.glob("*.tmdl")):
        table_files[_table_name(f)] = f

    table_contents = {name: _read(p) for name, p in table_files.items()}
    relationships = _parse_relationships(definition / "relationships.tmdl")

    # Other model files (raw substring scan for M cross-query refs etc.)
    # model.tmdl is excluded: its `ref table` lines and PBI_QueryOrder
    # annotation reference every table structurally, which is not usage.
    other_model_files = [
        p
        for p in definition.rglob("*.tmdl")
        if "tables" not in p.relative_to(definition).parts
        and p.name != "model.tmdl"
        and not any(part in _INERT_DIRS for part in p.relative_to(definition).parts)
    ]
    other_model_contents = {p: _read(p) for p in other_model_files}

    # Report JSON files
    report_files: list[Path] = []
    if report_definition is not None:
        report_files = sorted(report_definition.rglob("*.json"))
    report_contents = {p: _read(p) for p in report_files}

    results: list[dict[str, Any]] = []
    auto_date_count = 0
    for name in sorted(table_files):
        is_auto = bool(_AUTO_DATE_RE.match(name))
        if is_auto and not include_auto_date:
            auto_date_count += 1
            continue

        content = table_contents[name]
        entry: dict[str, Any] = {
            "name": name,
            "hidden": bool(re.search(r"(?m)^\s*isHidden\b", content)),
            "partition": _partition_type(content),
            "measures": len(re.findall(r"(?m)^\s*measure\s", content)),
        }

        # Relationships (both endpoints)
        rels = [r for r in relationships if name in (r["from_table"], r["to_table"])]
        entry["relationships"] = {
            "total": len(rels),
            "inactive": sum(1 for r in rels if r["inactive"]),
            "partners": sorted(
                {r["to_table"] if r["from_table"] == name else r["from_table"] for r in rels}
            ),
        }

        # DAX references from other tables (measures, calc columns/partitions)
        dax_re = _dax_ref_re(name)
        dax_from = sorted(
            other for other, c in table_contents.items() if other != name and dax_re.search(c)
        )
        entry["dax_refs"] = {"count": len(dax_from), "from_tables": dax_from[:max_examples]}

        # Raw mentions in other model files (M cross-query, expressions, etc.)
        raw_model = sorted(
            _relpath(p, definition)
            for p, c in other_model_contents.items()
            if name in c and p.name != "relationships.tmdl"
        )
        # Raw mentions in other tables not already caught as DAX refs
        raw_tables = sorted(
            other
            for other, c in table_contents.items()
            if other != name and name in c and other not in dax_from
        )
        entry["raw_model_mentions"] = (raw_model + raw_tables)[:max_examples]

        # Report references: exact entity ("Name") vs raw substring (suspect)
        exact_re = re.compile(r'"' + re.escape(name) + r'"')
        exact_files, raw_only_files = [], []
        for p, c in report_contents.items():
            if exact_re.search(c):
                exact_files.append(_relpath(p, report_definition))
            elif name in c:
                raw_only_files.append(_relpath(p, report_definition))
        entry["report_refs"] = {
            "exact": len(exact_files),
            "files": exact_files[:max_examples],
        }
        entry["report_raw_mentions"] = raw_only_files[:max_examples]

        entry["classification"], entry["reasons"] = _classify(entry, is_auto)
        results.append(entry)

    order = {"review": 0, "unused": 1, "used-model": 2, "used-report": 3, "auto-date": 4}
    results.sort(key=lambda e: (order.get(e["classification"], 9), e["name"]))

    by_class: dict[str, int] = {}
    for e in results:
        by_class[e["classification"]] = by_class.get(e["classification"], 0) + 1

    return {
        "status": "success",
        "summary": {
            "model_definition": str(definition),
            "report_definition": str(report_definition) if report_definition else None,
            "tables_assessed": len(results),
            "auto_date_tables_excluded": auto_date_count,
            "by_classification": by_class,
        },
        "tables": results,
    }


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _classify(entry: dict[str, Any], is_auto: bool) -> tuple[str, list[str]]:
    if is_auto:
        return "auto-date", [
            "Background auto date/time table; excluded from unused-table assessment."
        ]

    reasons: list[str] = []
    rel = entry["relationships"]
    dax = entry["dax_refs"]["count"]
    exact = entry["report_refs"]["exact"]
    raw_model = entry["raw_model_mentions"]
    raw_report = entry["report_raw_mentions"]

    if rel["total"] == 0 and dax == 0 and exact == 0 and not raw_model and not raw_report:
        return "unused", ["No references in relationships, DAX, M, or the report layer."]

    if exact > 0:
        reasons.append(f"Referenced by {exact} report file(s).")

    if dax > 0:
        reasons.append(f"Referenced in DAX by: {', '.join(entry['dax_refs']['from_tables'])}.")

    if rel["total"] > 0:
        kind = "inactive " if rel["inactive"] == rel["total"] else ""
        reasons.append(f"{rel['total']} {kind}relationship(s) with: {', '.join(rel['partners'])}.")

    # Review conditions
    if exact == 0 and dax == 0 and rel["total"] == 0 and (raw_model or raw_report):
        reasons.append(
            "Only raw/substring mentions found (may be stale metadata or M usage) -- "
            "inspect before deleting."
        )
        return "review", reasons

    if exact == 0 and dax == 0 and rel["total"] <= 1:
        reasons.append(
            "Only weakly connected (<=1 relationship, no DAX/report refs) -- "
            "verify it is not a dangling island before deleting."
        )
        return "review", reasons

    if raw_report:
        reasons.append(
            "Raw-only report mention(s) (e.g. formatting selector metadata) -- "
            "verify these are not stale references to renamed tables."
        )

    if exact == 0:
        return "used-model", reasons + ["No direct report usage; used indirectly via model."]
    return "used-report", reasons


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _relpath(path: Path, base: Path | None) -> str:
    if base is None:
        return str(path)
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _table_name(tmdl_path: Path) -> str:
    """Parse the table name from the `table <name>` declaration (fallback: stem)."""
    head = _read(tmdl_path)[:2000]
    m = _TABLE_DECL_RE.search(head)
    if m:
        return (m.group(1) or m.group(2)).strip()
    return tmdl_path.stem


def _partition_type(content: str) -> str:
    if re.search(r"(?m)^\s*partition\s+\S.*=\s*calculated\b", content):
        return "calculated"
    if re.search(r"(?m)^\s*partition\s+\S.*=\s*m\b", content):
        return "m"
    return "none"


def _dax_ref_re(name: str) -> re.Pattern[str]:
    """Match DAX table references: 'Table Name' or TableName[ (identifier-safe)."""
    pats = [re.escape(f"'{name}'") + r"(?=\[|\b)"]
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        pats.append(r"\b" + re.escape(name) + r"\[")
    return re.compile("|".join(pats))


def _parse_relationships(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    content = _read(path)
    rels = []
    for block in _REL_SPLIT_RE.split(content)[1:]:
        endpoints = _REL_COL_RE.findall(block)
        if len(endpoints) < 2:
            continue
        (_f_kind, f_table, f_col), (_t_kind, t_table, t_col) = endpoints[0], endpoints[1]
        rels.append(
            {
                "from_table": f_table.strip(),
                "from_column": f_col.strip(),
                "to_table": t_table.strip(),
                "to_column": t_col.strip(),
                "inactive": "isActive: false" in block,
                "autodetected": block.lstrip().startswith("AutoDetected_"),
            }
        )
    return rels


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _resolve_model_definition(path: Path) -> Path:
    """Normalise a user-supplied path to the model ``definition`` folder."""
    path = path.resolve()

    if path.is_file() and path.suffix == ".pbip":
        sm = path.parent / f"{path.stem}.SemanticModel"
        return _require_definition(sm, path)

    if path.is_dir():
        if path.name == "definition" and (path / "model.tmdl").exists():
            return path
        if path.name.endswith(".SemanticModel"):
            return _require_definition(path, path)
        # Parent folder containing exactly one *.SemanticModel
        candidates = [c for c in path.iterdir() if c.is_dir() and c.name.endswith(".SemanticModel")]
        if len(candidates) == 1:
            return _require_definition(candidates[0], path)
        if len(candidates) > 1:
            raise FileNotFoundError(
                f"Multiple .SemanticModel folders under '{path}'; pass the model folder explicitly."
            )

    raise FileNotFoundError(
        f"No .SemanticModel found at '{path}'. "
        "Expected a .SemanticModel folder, its definition folder, a .pbip file, "
        "or a parent folder containing one .SemanticModel."
    )


def _require_definition(sm_folder: Path, original: Path) -> Path:
    definition = sm_folder / "definition"
    if not definition.is_dir() or not (definition / "model.tmdl").exists():
        raise FileNotFoundError(
            f"No model definition found for '{original}': expected '{definition}' with model.tmdl."
        )
    return definition


def _resolve_report_definition(model_definition: Path, report_path: Path | None) -> Path | None:
    """Resolve the report definition folder, or None if not available."""
    if report_path is not None:
        p = report_path.resolve()
        if p.name == "definition" and (p / "report.json").exists():
            return p
        defn = p / "definition"
        if defn.is_dir() and (defn / "report.json").exists():
            return defn
        raise FileNotFoundError(
            f"No PBIR definition found at '{report_path}' (expected definition/report.json)."
        )

    # Auto-detect sibling: <base>.SemanticModel -> <base>.Report
    sm_folder = model_definition.parent
    base = sm_folder.name[: -len(".SemanticModel")]
    defn = sm_folder.parent / f"{base}.Report" / "definition"
    if defn.is_dir() and (defn / "report.json").exists():
        return defn
    return None
