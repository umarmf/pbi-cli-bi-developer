# PBIP Gotchas (field notes)

Hard-won behaviours of Power BI Project (PBIP) files and Power BI Desktop, collected while building and
debugging semantic models and PBIR reports. These are the things that are not in the schema docs, cause
opaque errors, or silently produce a wrong model. Written generically — no project-specific content.

---

## Desktop and the on-disk model

### Power BI Desktop re-serializes every PBIP file on save
When Desktop has a PBIP open and saves (explicitly, or implicitly when a visual is added), it rewrites
**every** `visual.json` and TMDL file from its in-memory model. Consequences:
1. An externally-edited invalid property is normalized/stripped on save.
2. Any on-disk edit made while Desktop is open is overwritten on the next save.

**Safe workflow for external edits:** stop Desktop (force-kill, do not save) → edit files → reopen.

### `cache.abf` holds unsaved TOM changes
`cache.abf` stores in-memory model state, **including changes made over a TOM connection** (descriptions,
format strings, etc.) that were never persisted to TMDL by a Desktop save. Deleting `cache.abf` to force a
clean reload silently wipes all such unsaved changes.

**Before deleting `cache.abf`:** connect, dump what you need to preserve, delete, reopen, re-apply, then save
via Desktop to persist to TMDL.

### TOM `SaveChanges()` against Desktop's engine does not write TMDL
Connecting to Desktop's local Analysis Services process (`msmdsrv`) via TOM and calling
`model.SaveChanges()` updates the **in-memory** model only. The on-disk `*.tmdl` files are written only when
**Desktop itself saves**. To persist external TOM edits headlessly, activate the Desktop window and
send the save shortcut, then poll the target `.tmdl` `LastWriteTime` to confirm. When Desktop already has the
file open, reconcile with **"Apply External Changes"** + save; external TOM edits to the engine are not
picked up by Desktop's own save.

### Desktop save via SendKeys can fail to focus
`WScript.Shell.AppActivate(pid)` can silently fail (window exists but is not activatable). Reliable
sequence: restore (`ShowWindow(hwnd, 9)`) → `SetForegroundWindow(hwnd)` via a `user32` P/Invoke →
send the save shortcut → poll `cache.abf` `LastWriteTime`.

---

## Hand-authored TMDL

### M quoted identifiers use double quotes; new files must be CRLF + BOM-free
Two failure modes when writing `tables/*.tmdl` by hand, both surfacing only as a load-time
**"M Engine error: Token Literal expected"** (Desktop then opens an empty model):
- **M quoted identifiers are `#"Name"` (double quotes), never `#'Name'`** — single quotes make the M lexer
  read a literal and fail. Applies to cross-query references such as `Source = #"Dim Org Node"`; the
  unquoted form only works for names without spaces.
- **New TMDL files must be CRLF + BOM-free UTF-8.** Many editors emit LF-only, and Power BI's parser is
  line-ending-sensitive. Fix at the byte level if needed; editing an existing CRLF file preserves it.

### `isNameInferred` is only valid for calculated-table columns
When converting a table partition from `calculated` → `m`, remove `isNameInferred` from the column
definition **and** change `sourceColumn: [ColumnName]` (bracketed) → `sourceColumn: ColumnName` (unbracketed).
Leaving `isNameInferred` causes a hard load error:
*"Property 'isNameInferred' is unknown and is not expected in the situation it appears."*
M-partition columns are always explicitly named; only calculated-table columns can have inferred names.

### Table/column descriptions serialize as `///` comments
A table/column `Description` (the field-list hover tooltip) serializes to TMDL as a **triple-slash summary
comment** (`/// <text>`, on the line before the `table X` statement) — not a `description:` property. Set it
via TOM (`Table.Description` / `Column.Description`, e.g. `pbi table update --description`).

### Removing a table that has no on-disk "disabled load" representation
In single-file-per-table models (M inline in `tables/*.tmdl`, no `expressions.tmdl`) there is **no on-disk
representation for a disabled-load query**. To make an existing table "not load" via file edits, remove it
from TMDL: delete `tables/<name>.tmdl`, drop its `ref table` + `PBI_QueryOrder` entry in `model.tmdl`, remove
its relationships, and neutralize DAX consumers (calc columns/tables). `loadAsTableDisabled` only takes
effect through a Desktop apply.

---

## PBIR report JSON

### Conditional-formatting `FillRule` — only `linearGradient` is safe to hand-author
The only `FillRule` types that round-trip safely are `linearGradient2` / `linearGradient3` (gradient / colour
scale). A hand-authored `"FillRule": { "fieldValue": {} }` (field-value colour from a hex-returning measure)
is **not a valid schema** — Desktop strips it to `{}` on load/save and the renderer then crashes
(`visitFillRuleDefinition → Cannot read properties of undefined (reading 'min')`), breaking the whole visual.
- **Field-value colouring via raw JSON: do not attempt.** Use the GUI (Format → Data colour → fx → Field
  value) and read back the generated JSON.
- **Binary red/green:** use `linearGradient2` with anchors straddling the threshold and scope it to one
  measure via a `selector` with a `dataViewWildcard` (required for the rule to apply to all categories).
- **Reference/Average/Constant lines:** no reliable hand-authored shape — prefer the GUI Analytics pane.

### Bookmarks: scope is `applyOnlyToTargetVisuals`, and "Data" is `suppressData`
- The all-visuals vs selected-visuals discriminator is **`options.applyOnlyToTargetVisuals`**, not
  `targetVisualNames`. A bookmark can carry a non-empty `targetVisualNames` and still behave as all-visuals if
  the flag is absent/false.
- To stop a bookmark from resetting slicer/window selections while keeping its show/hide behaviour, leave it
  all-visuals and set **`suppressData: true`** (uncheck the bookmark's "Data" checkbox) — do **not** switch it
  to selected-visuals; that breaks navigation-button hiding.
- Visual **visibility (hidden/shown) is stored only in bookmark `explorationState`**
  (`singleVisual.display.mode: "hidden"`); `visual.json` has no hidden flag. Stacked toggle pairs are driven
  entirely by bookmarks.
- Bookmark `displayName` is safe to rename in-file — button `visualLink.bookmark` references use the bookmark
  `name` ID, not the displayName.

---

## Model semantics and DAX

### Blank buckets rank first in TOPN / RANKX — always guard
`TOPN(1, ..., DESC)` and `RANKX` treat a blank group as a real, often-largest value. A blank bucket can
steal a Top-N slot and make a Top-N visual show N−1 named rows. Guard both sides: exclude blanks from the
iteration table (`FILTER(ALLSELECTED(col), NOT ISBLANK(col))`) and return `BLANK()` for blank rows — and
remember `BLANK() <= 20` is `TRUE` in DAX, so guard the filter with `NOT ISBLANK(r) && r <= N`.

### A Top-N KPI and its table must rank the same population
Rank the same column the visual groups by (id-based vs name-based grouping is a classic silent mismatch), and
treat filtered-out rows (inactive, blank) identically in **every** measure in the chain. Otherwise the KPI
total and the table it summarises disagree.

### Matrix pivot columns make visual-level measure filters evaluate per-cell
With columns = a date hierarchy, a visual-level `Filtered = 1` filter evaluates per (row × column) cell, not
per row, so extra members sneak in. Make ranking measures pivot-immune by adding the pivot column to the
`ALL(...)`/`ALLSELECTED(...)` of the ranking measure.

### `REMOVEFILTERS` caveats
- **Companion sort column:** `REMOVEFILTERS(dim_x[status])` does **not** cascade to a separate `status_sort`
  column unless that column is configured as the Sort-By-Column of `status`. If a visual binds both, remove
  filters on **both**.
- **Bidirectional date/period table:** when a slicer table relates bidirectionally to the date table, a
  measure's `REMOVEFILTERS('dim_date')` does not remove the filter — it re-arrives from the still-filtered
  slicer table. Capture `MIN/MAX(dim_date[date])` into variables first, then `REMOVEFILTERS` **both** tables.
- **Argument evaluation order:** `CALCULATE(x, REMOVEFILTERS(dim_date), FILTER(fact, ...))` still evaluates the
  `FILTER` argument **with** the date filter. Wrap it: `CALCULATETABLE(FILTER(...), REMOVEFILTERS(dim_date))`.

### `pbi column list` / `column get` omit `sortByColumn`
The absence of `SortByColumn` in those outputs is a reporting gap, not evidence it is unset. Verify via a
direct TOM read (`Columns[C].SortByColumn.Name`) if it matters.

### `table create` (TOM) does not infer columns
For both M-partition and calculated-partition tables you must create each column explicitly
(`pbi column create ... --source-column`). Calculated-table columns use the bracketed source-column form,
M-partition columns the unbracketed form. Refresh before relying on the columns.

### Heavy DAX window functions / per-row `CALCULATE` in calculated tables
`OFFSET`/`PARTITIONBY` fail in calculated tables when the relation has duplicate rows, and a per-row
`CALCULATE(MIN(...))` next-row lookup over hundreds of thousands of rows can time out. A buffered/sorted M
implementation (`Table.Buffer` → `Table.Sort` → `Table.Group` → `Table.AddIndexColumn`) computes interval /
SCD2-style tables in seconds.

---

## Tooling / shell

### `LocalDateTable_*` / `DateTableTemplate_*` are background-only
Auto date/time tables only work in the background and only matter when deleting tables via direct TMDL edits.
Ignore them when assessing safe-to-delete tables — they are never deletion candidates. `pbi model deps`
excludes them by default (`--include-auto-date` to list).

### Monetary measure format pattern
A common convention is `formatString: #,0.00;(#,0.00)` plus `PBI_FormatHint={"isCustom":true}`, with millions
shown via the visual's `labelDisplayUnits` rather than baked into the format string.

### Passing DAX string literals through a CLI on PowerShell 5.1
PowerShell 5.1 mangles embedded `"` in native-command arguments. For DAX string literals, **double the
quotes** inside a single-quoted PowerShell string (so `""20""` arrives as `"20"`). For commands that take no
spaces in the argument, the `--%` stop-parsing token plus `\"` is the reliable escape. Prefer passing DAX via
`--file` or stdin for multi-line expressions.

### `pbi` option placement
`--report-path` / `--path` and `--json` are group/global options: put `-p` **before** the subcommand and
`--json` **right after** `pbi`. They are not accepted after the subcommand.
