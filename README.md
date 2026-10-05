# pbi-cli-bi-developer

A standalone, MIT-licensed fork of **[pbi-cli](https://github.com/MinaSaad1/pbi-cli)** by
[Mina Saad](https://www.mina-saad.com/pbi-cli), maintained by [umarmf](https://github.com/umarmf),
and **rebased onto upstream v3.12.0**. See [`ATTRIBUTION.md`](ATTRIBUTION.md) for provenance.

<p>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python">
  <a href="https://github.com/umarmf/pbi-cli-bi-developer/actions"><img src="https://img.shields.io/github/actions/workflow/status/umarmf/pbi-cli-bi-developer/ci.yml?branch=master&style=flat-square&label=CI" alt="CI"></a>
  <a href="https://github.com/umarmf/pbi-cli-bi-developer/blob/master/LICENSE"><img src="https://img.shields.io/github/license/umarmf/pbi-cli-bi-developer?style=flat-square&color=06d6a0" alt="License"></a>
  <a href="https://github.com/umarmf"><img src="https://img.shields.io/badge/GitHub-umarmf-1a1a2e?style=flat-square&logo=github" alt="GitHub"></a>
</p>

---

## Why pbi-cli?

→ [Read "Why pbi-cli?" in the upstream README](https://github.com/MinaSaad1/pbi-cli/blob/master/README.md#why-pbi-cli)

---

## Upstream vs this fork

This repository tracks [pbi-cli](https://github.com/MinaSaad1/pbi-cli) and is **rebased onto upstream
v3.12.0**, so it keeps every upstream command and fix (including the `field_resolver`-based
`visual bind` / `bulk-bind`). On top of that it adds the work below.

| Area | Upstream pbi-cli | This fork |
|------|------------------|-----------|
| **Desktop lifecycle** | launch via an external script | `pbi desktop open/close/status` — launch, discover the Analysis Services port, connect/persist, stop |
| **Model cleanup** | — | `pbi model deps` — static per-table dependency scan (`used-report` / `used-model` / `review` / `unused`), no Desktop needed; ships the `power-bi-unused-tables` skill |
| **Static tables** | — | `pbi static decode` / `pbi static encode` — Base64 + raw-DEFLATE M payload ↔ rows |
| **Visual formatting** | `format get/clear`, background rules | `pbi format display-units`, `format data-labels`, `format set-object` (generic PBIR `objects` setter) |
| **Visual search** | `visual where` (type / name / position) | + `--all-pages`, `--title-pattern`, `--uses-measure`, `--uses-field` |
| **Filters** | list / add-categorical / add-topn / add-relative-date | + `filters where` (find by field), `filters add-advanced` (Advanced Comparison), `filters list --condition` |
| **Bookmarks** | list / get / add / delete / set-visibility | + `bookmarks set-scope` (all-visuals + `--suppress-data` — the config that stops bookmarks resetting slicers) |
| **Tables** | create / delete / list | + `table update --description/--hidden` |
| **Docs** | skills + README | + [`reference/`](reference/) — PBIP field notes: manifest, guardrails, guidelines, gotchas |
| **Tests** | 546 test functions | 696 tests collected (CI: `ruff`, `ruff format --check`, `mypy`, `pytest` all green) |

**Upstream is retained, not replaced:** DAX, modeling, deployment/TMDL, security/RLS, partitions,
diagnostics/tracing, report scaffolds, pages, themes, and custom visuals all work unchanged. This
fork does not remove or rename any upstream command.

---

## Get Started

This fork is not published to PyPI. Requires **Windows**, **Python 3.10+**, and **Power BI Desktop**.

```bash
pipx install "git+https://github.com/umarmf/pbi-cli-bi-developer.git"   # install (handles PATH)
pbi-cli skills install                                                 # register the Claude Code skills
pbi connect                                                            # connect to Power BI Desktop
```

Or clone and use an editable install:

```bash
git clone https://github.com/umarmf/pbi-cli-bi-developer.git
cd pbi-cli-bi-developer
pip install -e .
```

---

## Semantic Model Layer

Same as upstream, plus the fork commands `pbi desktop open/close/status`, `pbi model deps`,
`pbi static decode/encode`, and `pbi table update` (see the [fork delta](#upstream-vs-this-fork)).

→ [Upstream: Semantic Model Layer](https://github.com/MinaSaad1/pbi-cli/blob/master/README.md#semantic-model-layer)

---

## Report Layer

Same as upstream, plus `pbi format display-units` / `data-labels` / `set-object`, the extended
`pbi visual where` options, `pbi filters where` / `add-advanced`, and `pbi bookmarks set-scope`
(see the [fork delta](#upstream-vs-this-fork)).

→ [Upstream: Report Layer](https://github.com/MinaSaad1/pbi-cli/blob/master/README.md#report-layer)

---

## Architecture

→ [Upstream: Architecture](https://github.com/MinaSaad1/pbi-cli/blob/master/README.md#architecture)

---

## Skills

Ships **14** skills — the upstream set plus **`power-bi-unused-tables`**.

→ [Upstream: Skills](https://github.com/MinaSaad1/pbi-cli/blob/master/README.md#skills)

---

## Custom Visual Authoring

→ [Upstream: Custom Visual Authoring](https://github.com/MinaSaad1/pbi-cli/blob/master/README.md#custom-visual-authoring)

---

## All Commands

The full command reference is upstream. This fork's additions are listed in the
[fork delta](#upstream-vs-this-fork).

→ [Upstream: All Commands](https://github.com/MinaSaad1/pbi-cli/blob/master/README.md#all-commands)

---

## REPL Mode

→ [Upstream: REPL Mode](https://github.com/MinaSaad1/pbi-cli/blob/master/README.md#repl-mode)

---

## Development

Same workflow as upstream (`ruff`, `mypy`, `pytest`), run against this fork — **696 tests**. Clone this
repository, then `pip install -e ".[dev]"`.

→ [Upstream: Development](https://github.com/MinaSaad1/pbi-cli/blob/master/README.md#development)

---

## Bundled third-party software

Same Microsoft Analysis Services client libraries as upstream; see this repository's
[`NOTICE`](NOTICE) and [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).

→ [Upstream: Bundled third-party software](https://github.com/MinaSaad1/pbi-cli/blob/master/README.md#bundled-third-party-software)

---

## Contributing

→ [Upstream: Contributing](https://github.com/MinaSaad1/pbi-cli/blob/master/README.md#contributing)

---

## Fork-specific docs

- [`reference/`](reference/) — PBIP field notes: manifest, guardrails, guidelines, gotchas
- [`AGENTS.md`](AGENTS.md) — developer / agent notes for this fork
- [`CHANGELOG.md`](CHANGELOG.md) — the fork entry, above the upstream changelog

---

## License

MIT, with the bundled Microsoft Analysis Services client libraries licensed separately. See
[`LICENSE`](LICENSE), [`NOTICE`](NOTICE), and [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).

Upstream pbi-cli is MIT © pbi-cli contributors; modifications in this repository are © 2026 umarmf.
See [`ATTRIBUTION.md`](ATTRIBUTION.md).
