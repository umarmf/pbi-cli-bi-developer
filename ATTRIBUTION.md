# Attribution

`pbi-cli-bi-developer` is a **standalone derivative** of
[**pbi-cli**](https://github.com/MinaSaad1/pbi-cli) by
[MinaSaad1](https://github.com/MinaSaad1), used and extended under the MIT License.

It is not published as a GitHub fork, but it is built directly on pbi-cli's codebase.

## Upstream

- **Project:** pbi-cli — <https://github.com/MinaSaad1/pbi-cli>
- **License:** MIT, with bundled Microsoft Analysis Services client libraries under a separate license
  (see below)
- **Base version:** rebased onto upstream **v3.12.0**

## Modifications

- **Copyright (c) 2026 umarmf** — the fork-specific additions and changes in this repository.
- **Original copyright (c) pbi-cli contributors** — retained verbatim in [`LICENSE`](LICENSE).

The modifications include additional commands (desktop lifecycle, static-table codec, static model
dependency scan, output-formatting helpers), extended visual/filter search, and a bundled
`power-bi-unused-tables` skill. See [`CHANGELOG.md`](CHANGELOG.md) and [`AGENTS.md`](AGENTS.md) for details.

## Licensing

This distribution is licensed under **`MIT AND LicenseRef-Microsoft-AS-Client-Libraries`**:

- **MIT** — this project's own source, and the upstream pbi-cli source it derives from.
- **Microsoft Analysis Services client libraries** — the bundled `.dll` files under
  `src/pbi_cli/dlls/` are redistributed under Microsoft's separate terms. See
  [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md) and [`NOTICE`](NOTICE).

Any redistribution of this project (or a derivative of it) must retain `LICENSE`, `NOTICE`,
`THIRD_PARTY_LICENSES.md`, and this attribution file.
