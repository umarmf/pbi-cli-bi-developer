---
name: Power BI Unused Tables
description: Assess which tables in a PBIP semantic model are safe to delete using pbi-cli's static dependency scan (pbi model deps). Invoke this skill whenever the user asks "which tables can I delete", "unused tables", "clean up the model", "table dependencies", "what uses this table", "safe to delete", "dead tables", or wants to slim down a PBIP model. Works file-static on the PBIP folder -- no PBI Desktop launch or pbi connect needed.
tools: pbi-cli
---

# Power BI Unused Tables Skill

Find deletion-candidate tables in a PBIP project via static dependency analysis.

## Prerequisites

- A PBIP project on disk (`<name>.SemanticModel` + `<name>.Report` folders)
- No `pbi connect` needed -- this is file-static (TMDL + PBIR JSON parsing)
- PBI Desktop must be **closed** before any deletion edits (it re-serializes files on save and clobbers external edits)

## The Command

```bash
# JSON output (preferred for agent consumption)
pbi --json model deps -p <path/to/project.SemanticModel>

# Auto-detect from CWD (walks up for a .SemanticModel)
pbi --json model deps

# Point at a .pbip file or parent folder -- both resolve
pbi --json model deps -p <path/to/project.pbip>

# Explicit report override (sibling .Report is auto-detected otherwise)
pbi --json model deps -p <model.SemanticModel> --report <report.Report>

# Include auto date/time background tables (excluded by default)
pbi --json model deps -p <model.SemanticModel> --include-auto-date
```

## Classification Semantics

Each table gets ONE classification:

| Class | Meaning | Action |
|---|---|---|
| `unused` | Zero references: no relationships, no DAX, no M, no report bindings | Deletion candidate -- verify, then delete |
| `review` | Weakly connected: dangling island (<=1 relationship, nothing else), or only raw/substring mentions (possibly stale metadata) | **Human judgment required** -- see edge cases below |
| `used-model` | No direct report refs, but referenced by measures/calc columns/relationships | Keep (indirect dependency) |
| `used-report` | Referenced by report visuals/filters/bookmarks | Keep |
| `auto-date` | `LocalDateTable_*` / `DateTableTemplate_*` | Ignore -- see below |

Per-table `reasons[]` explains the verdict. Trust the reasons, not just the class.

## Auto Date/Time Tables: Always Ignore

`LocalDateTable_*` and `DateTableTemplate_*` are **background artifacts** -- they
only work behind the scenes and only matter when deleting tables via direct TMDL
edits. They are excluded from the assessment by default (`--include-auto-date`
only if you specifically need them). Do NOT propose them as deletion candidates.

## Judgment Layer (what the command cannot decide)

The scan reports; you decide. Always manually verify these before recommending deletion:

1. **Stale formatting selectors** -- a `report_raw_mentions` hit like
   `"metadata": "gold dim_X.Manager_L2"` inside a visual's conditional-formatting
   selector may reference a table name that doesn't even exist (renamed table).
   Raw-only mentions are suspect, NOT real usage. Read the flagged file.
2. **Dangling islands** -- a table with exactly one `AutoDetected_*` relationship
   and nothing else (e.g. a channel-map joined to a bucket table that is already
   reachable directly from a fact/dim) contributes no filtering. Safe to delete
   together with its relationship.
3. **Field parameters & helper tables** -- hidden calc tables (`isHidden` +
   `partition = calculated`) that ARE referenced by visuals are live field
   parameters (e.g. Manager Level Selector pattern). Hidden != unused.
4. **"Last Refresh" tables** -- small M tables evaluating `DateTime.LocalNow()`
   are the user-facing refresh-timestamp standard. Keep.
5. **Copied-from-sibling-project tables** -- a table used in a sibling project
   (e.g. `Channel KPIs` in marketing/sales-team reports) but unreferenced here
   is dead weight in THIS project. Judge per project, not across the repo.
6. **M-internal dependencies** -- cross-query M references (one table's partition
   referencing another query by name) show up as `raw_model_mentions`. If a
   candidate has raw model mentions, inspect them first.

## Deletion Procedure (once the user approves)

For each approved table, per the PBIP guardrails:

1. **Close PBI Desktop** (it clobbers external edits on save).
2. Delete `definition/tables/<name>.tmdl`.
3. In `definition/model.tmdl`: remove the `ref table <name>` line AND its
   `PBI_QueryOrder` annotation entry.
4. In `definition/relationships.tmdl`: remove every relationship where the
   table is an endpoint.
5. Neutralize DAX consumers: delete or rewrite measures/calculated columns in
   OTHER tables that reference the deleted table (the scan's `dax_refs` /
   `raw_model_mentions` lists tell you if any exist).
6. Stale Q&A synonyms in `cultures/*.tmdl` are inert -- safe to leave
   (Desktop auto-cleans on next open).
7. **NAMEOF guardrail**: if any surviving table contains `NAMEOF()` references
   to the deleted table, do NOT text-replace -- it corrupts the file. Recreate
   the field parameter via the Desktop GUI instead.
8. Reopen the `.pbip` in Desktop and confirm the model loads; save once.

## Workflow

```bash
# Step 1: Scan
pbi --json model deps -p <project.SemanticModel> > deps.json

# Step 2: Review every 'review' table manually (edge cases above)

# Step 3: Present candidates to the user with evidence -- NEVER auto-delete

# Step 4: After approval, execute the deletion procedure per table

# Step 5: Re-run the scan to confirm a clean state
pbi --json model deps -p <project.SemanticModel>
```

## Rules

- **Report, never auto-delete.** The command's job is evidence; deletion is always user-approved.
- **Per-project judgment.** Usage in sibling projects is irrelevant; only this project's references count.
- Cultures (`cultures/*.tmdl`) Q&A synonyms and `model.tmdl` `ref table` lines are structural, not usage -- the scan already excludes both.
