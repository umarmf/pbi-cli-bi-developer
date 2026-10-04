# PBIP Reference Manifest

Structural definitions, syntax formats, and file layout for a Power BI Project (PBIP).

---

## 1. Project Layout

```text
[Project Name].SemanticModel/
├── .pbi/
│   └── unappliedChanges.json
├── definition/
│   ├── expressions.tmdl
│   ├── model.tmdl
│   ├── relationships.tmdl
│   └── tables/
│       └── <table_name>.tmdl

[Project Name].Report/definition/
├── report.json
└── pages/<page-id>/
    ├── page.json
    └── visuals/<visual-id>/
        └── visual.json
```

---

## 2. Measure Syntax

### Implemented (with expression)
```tmdl
measure 'Total Sales' = SUM(fact_sales[amount])
    formatString: $#,0.00
    displayFolder: Financial Metrics
    lineageTag: <uuid>
```

### Placeholder (no expression)
```tmdl
measure 'Target Revenue'
    displayFolder: Pipeline Projections
    lineageTag: <uuid>
```

**No `=` after the measure name for placeholders.** The name stands alone on its own line.

---

## 3. TMDL Multi-line DAX Expressions

Multi-line DAX **must** be wrapped in triple backticks:

```tmdl
measure 'Spend' = ```

    VAR CurrentSegmentSpend =
        CALCULATE(
            [Total Spend],
            REMOVEFILTERS(dim_segment[segment])
        )
    RETURN
        CurrentSegmentSpend

    ```
    displayFolder: Folder Name
    lineageTag: <uuid>
```

Single-line expressions go on the same line as `measure`. Comments go **after** the expression, not between `=` and the expression.

---

## 4. Visual JSON Column Binding

Each measure reference appears in three locations inside `visual.json`:

| Key | Role | Example |
|-----|------|---------|
| `Property` | Hard logical binding to the model | `"Property": "Total Sales"` |
| `queryRef` | Internal Power BI lookup key | `"queryRef": "_Measures Table.Total Sales"` |
| `nativeQueryRef` | Literal display name | `"nativeQueryRef": "Total Sales"` |

Image metadata `selector.metadata` and sort definitions also reference measures by `queryRef` format. When updating a visual, update all locations.

When repointing a visual to a new schema, target the `Property` key inside `Column.Expression` blocks — it dictates the active data-model binding. `queryRef` and `nativeQueryRef` are secondary display attributes.

---

## 5. NAMEOF() Field Parameters

Tables containing `NAMEOF()` hold hard dependencies on internal column lineage tags.

**Do NOT text-search-and-replace** strings inside these TMDL files. They must be re-created via the Power BI Desktop GUI after the underlying tables resolve.

---

## 6. Visual Type Mappings

PBIR JSON uses different type names than Power BI Desktop. Common mappings:

| PBIR `visualType` | Power BI Desktop label |
|---|---|
| `pivotTable` | Matrix |
| `clusteredBarChart` | Clustered bar chart |
| `clusteredColumnChart` | Clustered column chart |
| `lineChart` | Line chart |
| `pieChart` | Pie chart |
| `donutChart` | Donut chart |
| `scatterChart` | Scatter chart |
| `ribbonChart` | Ribbon chart |
| `tableEx` | Table |
| `card` | Card (single number) |
| `cardVisual` | Multi-row card |
| `slicer` | Slicer |
| `advancedSlicerVisual` | Advanced (date/relative) slicer |
| `funnel` | Funnel |
| `gauge` | Gauge |
| `multiRowCard` | Multi-row card |
| `waterfall` | Waterfall chart |
| `pageNavigator` | Page navigation |
| `visualGroup` | Visual container group |
| `shape` | Shape / rectangle |
| `textbox` | Text box |
| `image` | Image |
| `actionButton` | Button |

When reading `visual.json`, use the PBIR type, not the Desktop label.

---

## 7. Visual Container Groups

Visual container groups (grouped visuals on a page) have their own `visual.json` at:

```text
pages/<page_id>/visuals/<group_id>/visual.json
```

The `visualGroup.displayName` field contains the human-readable group name. To map group IDs to names, read each group's `visual.json`.
