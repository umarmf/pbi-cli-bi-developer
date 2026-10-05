# pbi-cli-bi-developer

A standalone, MIT-licensed fork of **[pbi-cli](https://github.com/MinaSaad1/pbi-cli)** by
[Mina Saad](https://www.mina-saad.com/pbi-cli), maintained by [umarmf](https://github.com/umarmf),
and rebased onto upstream **v3.12.0**.

pbi-cli gives Claude Code (and other AI agents) the ability to manage Power BI semantic models **and**
PBIR reports through `pbi` commands.

This fork keeps the full upstream command surface and adds:

- `pbi desktop open/close/status` — Power BI Desktop lifecycle management
- `pbi model deps` — static per-table dependency scan + the `power-bi-unused-tables` skill
- `pbi static decode` / `pbi static encode` — Base64 + raw-DEFLATE static-table codec
- `pbi format display-units` / `data-labels` / `set-object` — PBIR formatting helpers
- extended `visual where`, `filters where` / `add-advanced`, `bookmarks set-scope`, `table update`
- PBIP field notes in [`reference/`](https://github.com/umarmf/pbi-cli-bi-developer/tree/master/reference)

**Full documentation** (including everything inherited from upstream) is in the repository README:

- README — <https://github.com/umarmf/pbi-cli-bi-developer#readme>
- Fork delta — <https://github.com/umarmf/pbi-cli-bi-developer#fork-delta-upstream-vs-this-fork>
- Upstream pbi-cli — <https://github.com/MinaSaad1/pbi-cli>
- Attribution & licensing — [ATTRIBUTION.md](https://github.com/umarmf/pbi-cli-bi-developer/blob/master/ATTRIBUTION.md)

## License

MIT, with the bundled Microsoft Analysis Services client libraries licensed separately. See
[LICENSE](https://github.com/umarmf/pbi-cli-bi-developer/blob/master/LICENSE),
[NOTICE](https://github.com/umarmf/pbi-cli-bi-developer/blob/master/NOTICE), and
[THIRD_PARTY_LICENSES.md](https://github.com/umarmf/pbi-cli-bi-developer/blob/master/THIRD_PARTY_LICENSES.md).
