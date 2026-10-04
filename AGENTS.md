# pbi-cli — Developer Notes

A standalone, MIT-licensed derivative of [github.com/MinaSaad1/pbi-cli](https://github.com/MinaSaad1/pbi-cli),
rebased onto upstream **v3.12.0**. See [`ATTRIBUTION.md`](ATTRIBUTION.md) for lineage and licensing.
This file documents the fork-specific extensions and the conventions an agent should follow.

Install editable so `pbi` resolves to this source tree:

```bash
pip install -e --no-deps
```

## Added commands

### Output formatting (2026-07-27)

- `pbi format display-units <visual> -p <page> [--field "..."] --units none|thousands|millions|billions|auto` — set `labelDisplayUnits` per-field (auto-locates `objects.values` vs `objects.value`) or visual-level. PBIR file edit, no Desktop needed.
- `pbi format data-labels <visual> -p <page> [--field "..."] --show|--hide` — toggle data labels per-field or visual-level.
- `pbi format set-object <visual> -p <page> --object <name> --property <key> --value <val> [--field "..."] [--type bool|num|color|str] [--remove]` — generic PBIR `objects` setter.
- `pbi table update <name> [--description "..."] [--hidden|--visible]` — update description and/or visibility on existing tables. Requires `pbi connect`.
- `pbi desktop open <file.pbip> [--kill-existing] [--no-wait-model]` — launch Power BI Desktop, discover the Analysis Services port, connect and persist. `pbi desktop close [--force]` stops PBIP + `msmdsrv`. `pbi desktop status` shows running processes and port.

### Static dependency scan (2026-08-05)

- `pbi model deps [-p <path>] [--report <path>] [--include-auto-date]` — static per-table dependency scan of a PBIP project (TMDL + PBIR JSON; no Desktop or connection). Classifies tables `used-report` / `used-model` / `review` / `unused`; `LocalDateTable_*` / `DateTableTemplate_*` are excluded by default (they are background-only). Backend: `core/deps_backend.py`; bundled skill: `power-bi-unused-tables`.

### Visual and filter search (2026-08-20)

- `pbi visual where ... [--all-pages] [--title-pattern "..."] [--uses-measure "T[M]"] [--uses-field "T[C]"]` — extended `where` filters: search across all pages (adds a `page` key per result), match by literal visual title, and match by the fields/measures a visual references (queryState projections + sortDefinition + conditional-formatting inputs + field parameters). `--uses-measure` restricts to `Measure` refs; `--uses-field` matches any kind. Specs accept `Table[Name]` or a bare `Name`. Measure-driven titles cannot be matched by `--title-pattern`.
- `pbi filters list ... --condition` — summarize filters as `{name, type, field, condition}` instead of raw JSON.
- `pbi filters where --page <id> [--visual <name>] --field "T[F]" ... [--type Categorical|TopN|RelativeDate|Advanced] [--condition]` — find filters by field reference (a bare `F` matches on property alone; repeatable `--field` = OR).
- `pbi filters add-advanced --page <id> [--visual <name>] (--measure "T[M]" | --column "T[C]") [--op eq|neq|gt|gte|lt|lte] [--value 1]` — add an Advanced Comparison filter (`<field> <op> <value>`), the Power BI "Advanced filtering" shape. Integers get an `L` literal suffix, floats `D`, strings single-quoted.

Backends: `core/bulk_backend.py` (`visual_where`), `core/filter_backend.py` (`filter_add_advanced`, `filter_where`, `_summarize_filter`).

### Static-table codec (2026-09-23)

- `pbi static decode <source> [--b64|--b64-file] [--json|--csv] [--out <file>]` — decode a Power BI static table (Base64 + **raw DEFLATE** M payload) to rows. `<source>` accepts `@file.m`, `@model.tmdl`, `@-` (stdin), or literal text; the default output is a JSON array-of-arrays, `--json` adds `{columns, rows, format}`, `--csv` emits CSV. Declared column names/types are recovered from the `type table[...]` clause when present. File-static (no connection or Desktop).
- `pbi static encode [--rows @file.json|@-] [--b64-file <existing payload>] [--columns "A:text,B:int"] [--form json|csv|auto] [--template] [--base64-only] [--out <file>]` — encode a JSON array-of-arrays (or CSV) into the Base64 payload plus a paste-ready `Table.FromRows` / `Csv.Document` M expression. Always emits raw DEFLATE (matches `Compression.Deflate`); `--template` reproduces the exact `let _t = ((type nullable text) meta [Serialized.Text = true]) in type table[...]` wrapper. File-static.
- Backend: `core/static_table_backend.py`. Gotcha: a bare `--b64` carries no `type table[...]`, so names/types come out generic (`Column1..N`, types inferred); pass the full M expression or a `.m`/TMDL file to recover declared names/types. The CSV form has no type metadata, so decode infers types; use `--form json` for a lossless typed round-trip.

## Conventions & gotchas

- **`--report-path`/`--path` and `--json` are group/global options** — `-p` precedes the subcommand (`pbi visual -p <path> where ...`); `--json` goes right after `pbi` (`pbi --json visual ...`). They are not accepted after the subcommand.
- **Tests:** run `python -m pytest -q` from the repo root. `ruff` and `mypy` are dev extras (not required to run the suite).
- The `pbi` launcher is on PATH; editable-install edits take effect immediately with no reinstall.
- Report-layer commands work file-statically against a PBIP folder; model-layer commands require a live `pbi connect`.
