# PBIP Hard Guardrails

Constraints that cause silent file corruption, opaque Power BI errors, or a model crash on load.
Verify against these before writing any PBIP file.

---

## 1. BOM Encoding

**Trap:** `Set-Content`, `Out-File`, and `>` in PowerShell write UTF-8 **with BOM**. Power BI rejects BOM files with opaque errors.

**Rule:** write files BOM-free:

```powershell
[System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
```

---

## 2. NBSP Indentation in `unappliedChanges.json`

**Trap:** M code in `text` arrays sometimes uses **non-breaking spaces** (`U+00A0`, bytes `C2 A0`) for indentation rather than regular spaces. An exact-match edit silently fails because typed spaces are `0x20`.

**Pattern:** some entries use `" \u00a0\u00a0 "` (space-NBSP-NBSP-space), others use four regular spaces. It is inconsistent per table.

**Rule:** when text-editing `unappliedChanges.json`, verify the replacement count with
`[regex]::Matches($content,[regex]::Escape($old)).Count` before writing, and abort on a mismatch.

---

## 3. Power BI Desktop Auto-Cleanup

**Trap:** Power BI Desktop deletes "unused" table TMDL files and overwrites `model.tmdl` / `relationships.tmdl` on close.

**Rule:**
1. Commit to git immediately **before** opening Power BI Desktop.
2. Run `git status` immediately **after** closing it.
3. Restore any files the GUI dropped or altered.

---

## 4. Duplicate Relationship ID Crash

**Trap:** two entries with the same relationship ID or name block (for example a duplicate `AutoDetected_xxxxxxxx`) cause the model to open with zero tables and unhelpful DAX errors.

**Rule:** after modifying `relationships.tmdl`, grep for duplicate names/UUIDs before headless validation.

---

## 5. `LocalDateTable` Circular Dependency

**Trap:** `LocalDateTable_*` files are gitignored auto-generated artifacts. On a fresh clone without a local cache, `model.tmdl` references them but they do not exist on disk. Power BI cannot load without them and cannot generate them until the model loads.

**Rule:** strip every `LocalDateTable` reference from `model.tmdl` and table TMDL files before the first GUI open. Power BI regenerates them on the first successful load.

---

## 6. `lastLoadedAsTableFormulaText` in `unappliedChanges.json`

**Trap:** `lastLoadedAsTableFormulaText` is a stale snapshot of the last successful load. It uses triple-backslash quoting (`\\\"`) where the `text` array uses `\"`, so a search/replace scoped to `\"` touches only the active `text` array.

**Rule:** never modify `lastLoadedAsTableFormulaText`. Power BI overwrites it on apply — leaving it stale is correct.

---

## 7. Stale `cache.abf` After Copying a Project

**Trap:** when you copy a PBIP project (for example duplicating `old-project` → `new-project`), both `*.SemanticModel\.pbi\cache.abf` and `*.Report\.pbi\cache.abf` still contain serialized model state from the **source** project. Power BI Desktop loads the cache first, so it displays the old project's model (old measures, old relationships) even when the TMDL on disk has been rewritten. The on-disk TMDL is ignored while a matching cache exists.

**Symptom:** you open the project and see the old model; on close, Power BI auto-cleans your TMDL changes to match the cached state — loss of work.

**Rule:** after copying a PBIP project, immediately:
1. Update **`<new>.pbip`** → `artifacts[0].report.path` to the new `.Report` folder name. **If you skip
   this, opening the new `.pbip` silently loads the ORIGINAL report + model — the #1 cloning gotcha.**
2. Update `*.Report\definition.pbir` → `datasetReference.byPath.path` to point at the new `*.SemanticModel` folder.
3. Delete both cache files before opening (see Rule 3).

```powershell
# Fix definition.pbir
$oldPath = "../old-project.SemanticModel"
$newPath = "../new-project.SemanticModel"
(Get-Content "new-project.Report\definition.pbir") -replace $oldPath, $newPath | Set-Content "new-project.Report\definition.pbir"

# Delete stale caches
Remove-Item -LiteralPath "new-project.SemanticModel\.pbi\cache.abf" -Force
Remove-Item -LiteralPath "new-project.Report\.pbi\cache.abf" -Force
```

**Symptom without the fix:** report visuals load from the new report folder but the model loads from the original semantic model — updated visuals with old measures, silently wrong data.

---

## 8. Stale Relationships After Table/Column Changes

**Trap:** changing a column's `sourceColumn` regenerates its internal `lineageTag`/ID, silently invalidating every relationship that references that column. Changing a table (adding/removing columns, repointing its data source) can orphan downstream files too. Power BI gives opaque errors such as *"uses an invalid column ID"* with no hint about which file still holds the stale reference.

**Rule:** after any table or column change in TMDL, audit and fix **all** downstream files. No single-file edit is safe in isolation — the model is a distributed graph across several files.

### Drop a Table

| File | Action |
|------|--------|
| `definition/tables/<name>.tmdl` | Delete the file |
| `definition/model.tmdl` | Remove the `ref table` line and its `PBI_QueryOrder` entry |
| `definition/relationships.tmdl` | Remove all relationships referencing the table (both `fromColumn` and `toColumn`) |
| `definition/tables/LocalDateTable_*.tmdl` | Delete every `LocalDateTable` file that only existed for this table's date columns |
| `definition/model.tmdl` | Remove the corresponding `ref table LocalDateTable_*` entries |
| Other `definition/tables/*.tmdl` | Remove any `Variation` blocks on other tables' columns that point to the dropped table's `LocalDateTable`s |

### Repoint a Column's `sourceColumn`

| File | Action |
|------|--------|
| `definition/relationships.tmdl` | Delete or update every relationship where `fromColumn` or `toColumn` references `<table>.<oldColumn>`. Changing `sourceColumn` regenerates the internal column ID, so all existing relationships become invalid. |
| `definition/tables/<table>.tmdl` | If the column had a `variation` block (date columns), update the relationship UUID and `defaultHierarchy` LocalDateTable name. |

### Common Hit Pattern

Repointing a dimension column (for example a `dim_region` from one source column to another) invalidates every relationship that referenced the old column, e.g. `dim_campaign.region → dim_region.region`. Symptoms: an **"invalid column ID"** error on load.

---

## 9. When to Defer to Power BI Desktop (vs. File Surgery)

**Principle:** the model is a distributed graph across many files (Rule 8). When a change touches many coordinated references *and* Desktop auto-manages them, do it in the Desktop GUI — hand-editing risks a model crash on load with no way to verify the render.

**Always do in Desktop (right-click / drag-drop), not by hand:**

| Change | Why Desktop |
|---|---|
| **Delete a table** | The GUI auto-removes its `tables/*.tmdl`, `relationships.tmdl` entries, dependent `LocalDateTable_*`, **`cultures/*.tmdl` Q&A blocks, and bookmark state**. Cultures files are routinely 100k+ lines with the table referenced in many clusters — hand-removal is the #1 way to brick a model. |
| **Repoint a visual with many field refs** | A visual's `projections` + sort `metadata` + `filterConfig` all key off field identity. Coordinated Column↔Measure rewrites across a 1000-line `visual.json` are unverifiable blind; drag-drop is instant and checked. |
| **Field parameters (`NAMEOF()`)** | Hard dependency on lineage tags — must be re-created in the GUI (see Rule 5). |
| **Anything you cannot visually verify** | If you cannot open the item in Desktop to confirm it renders, prefer the GUI. |

**Signal that a task is Desktop territory:** a grep shows the target in many files / many clusters (especially `cultures/`, `bookmarks/`), or a single visual references the field more than ~5 times. Stop, grep to measure the blast radius, and if it is wide and Desktop auto-cleans it → hand it to Desktop with exact steps.

**Safe to do by hand:** TMDL measure-expression edits, single relationship add/remove (with the duplicate-id check from Rule 4), `definition.pbir` / `.pbip` / `.platform` path and displayName fixes, page/visual filter additions via `pbi filters`, cache deletion (Rule 7) — anything isolated to one or two files with no downstream ref cascade.
