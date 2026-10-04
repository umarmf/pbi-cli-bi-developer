# PBIP Soft Guidelines

Best-practice recommendations, not hard constraints. Where `pbip-guardrails.md` lists things that *corrupt* files, this lists things that *produce a wrong or stale* model. Deviate with a reason.

---

## 1. Column selection when repointing a dimension to a new source

When choosing a source column for a report dimension or attribute, **semantic fit is necessary but not sufficient** — also verify the column is actually populated for the reporting period. A column that "looks perfect" can be useless if the source stopped writing to it.

**Before adopting a column, sample it (for example with `pbi dax execute` against a connected model) for all three:**

1. **Population %** — `COUNTROWS` where the column is non-blank vs total. A column that is 5% populated is rarely fit for a primary axis.
2. **Recency / max date** — join the column to a date and check the most recent populated row. **A column frozen at an old date is a trap** — it loads fine and looks clean, but reports only historical data and goes silently blank for new periods.
3. **Cardinality / value quality** — `DISTINCT` of the column. Ten clean buckets vs 177 messy IDs is a real tradeoff against population %.

### Worked example

A `latest_channel` column looked ideal — ten clean channel buckets (Paid Search, Paid Social, Organic Social, …) — but **its data only ran up to the previous year**. The source had stopped populating it for current-year records, so building the channel dimension on it pushed every new record into the blank bucket (67%+ unattributed). A messier but live-populated source column (~177 values, ~79% populated) was the correct ongoing choice. Channel conformance was then derived from that live column via a `dim_channel.channel_group` lookup.

**Rule of thumb:** prefer a live-populated column (even if messier) over a clean-looking column that is frozen. If a clean column is frozen, flag it to the data owner to resume population — do not build a dimension on it in the meantime.

### Related: route classification through the conformance dimension, not the raw column

Measures that classify by channel should filter the **conformance column** (`dim_channel[channel_group]`), not the raw source column directly. That way the classification survives a source-column swap without rewriting the measure — only the `dim_channel` calculation and its relationship change.

---

## 2. Calculated-table recomputation

Calculated tables (for example `dim_channel`, `dim_date`) only recompute when the model processes. After editing a calculated table's DAX, a model **refresh** (or at minimum a recalc) is required before the new values appear — opening the file alone may show stale rows. If a rebuilt dimension looks empty or holds old values after an edit, refresh before diagnosing further.
