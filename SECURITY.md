# Security Policy

## Supported Versions

Only the latest 3.x release line receives security fixes. Users on older
major versions should upgrade.

| Version  | Supported        |
|----------|------------------|
| 3.10.x   | Yes              |
| 3.9.x    | Critical fixes   |
| < 3.9    | No               |
| 2.x      | No               |
| 1.x      | No               |

## Reporting a Vulnerability

If you discover a security vulnerability in pbi-cli, please report it
responsibly. **Do not open a public issue.**

Use [GitHub private vulnerability reporting](https://github.com/umarmf/pbi-cli-bi-developer/security/advisories/new)
to submit the report.

Please include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

- **Acknowledgment**: within 48 hours
- **Initial assessment**: within 1 week
- **Fix release**: as soon as possible, severity-dependent

## Architecture and Trust Boundaries

pbi-cli connects to a locally running Power BI Desktop instance via direct
in-process .NET interop. **There is no MCP server, no subprocess, and no
network listener.** Earlier 1.x releases used a separate
`PBIDesktopMCPServer.exe` subprocess; that architecture was removed in 2.x
and this document reflects the current 3.x behavior.

- **Direct in-process .NET interop.** pbi-cli loads bundled Microsoft
  Analysis Services Tabular Object Model (TOM) and ADOMD.NET client
  assemblies into the Python process via `pythonnet` / `clr-loader`. See
  `src/pbi_cli/core/dotnet_loader.py` and `src/pbi_cli/core/tom_backend.py`.
  The bundled DLLs live in `src/pbi_cli/dlls/` and are Microsoft binaries
  redistributed under the Microsoft Software License Terms for Microsoft
  Analysis Management Objects (AMO) and Microsoft Analysis Services -
  ADOMD.NET. See [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md) and
  [`NOTICE`](NOTICE) for details.
- **Local-only connection.** pbi-cli connects to Power BI Desktop's
  embedded Analysis Services instance over a loopback TCP port that
  Desktop binds at launch. pbi-cli does not open any network sockets for
  inbound traffic and does not communicate over the public network.
- **No credentials persisted.** Connection metadata (port, workspace
  path, model name) is stored at `~/.pbi-cli/connections.json`. No
  tokens, passwords, or session credentials are written to disk. The
  file should have user-only read/write permissions.
- **Report-layer commands are fully offline.** `pbi report`, `pbi visual`,
  `pbi filters`, `pbi bookmarks`, `pbi format`, and `pbi theme` operate on
  PBIR JSON files on disk. They do not require `pbi connect` and do not
  touch the Power BI Desktop process.

## Global Configuration Modifications

pbi-cli integrates with Claude Code by writing to the user's global Claude
configuration directory. Users should be aware of exactly which files are
modified and when. This section is authoritative; if behavior diverges from
the description below, please file a security advisory.

### Files written

| Path                           | Written by              | Contents                                                                                                                                                                               |
|--------------------------------|-------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `~/.claude/CLAUDE.md`          | `pbi-cli skills install` | Appends a block wrapped in `<!-- pbi-cli:start -->` / `<!-- pbi-cli:end -->` markers that lists the 12 bundled skills and their trigger conditions. Source: `src/pbi_cli/core/claude_integration.py`. |
| `~/.claude/skills/power-bi-*/` | `pbi-cli skills install` | Copies the 12 bundled `SKILL.md` files from `src/pbi_cli/skills/` so Claude Code discovers them. Source: `src/pbi_cli/commands/skills_cmd.py`.                                         |

No other paths under `~/.claude/` are read or modified. pbi-cli does not
access user conversation history, project memory files, unrelated skills,
or any other Claude Code state.

### When it happens

- **`pbi-cli skills install`** — the explicit install command (3.10.3+).
  Before writing anything, the command displays the exact paths it will
  modify and requires the user to confirm. Passing `--yes` / `-y` skips
  the prompt for non-interactive use.
- **`pbi-cli skills uninstall`** — removes the skill files and, when
  removing all skills, cleans up the `CLAUDE.md` block between its
  marker comments.
- **`pbi connect`** — connects to Power BI Desktop only. It does **not**
  write to `~/.claude/`. On a successful connection it checks whether
  skills are installed and, if not, prints a one-line tip:
  `Run 'pbi-cli skills install' to register pbi-cli skills with Claude Code.`

### Opt-out

Claude Code integration is fully opt-in as of 3.10.3. Simply do not run
`pbi-cli skills install` and `~/.claude/` is never touched.

To remove a previously installed integration, run:

```
pbi-cli skills uninstall
```

### Why this matters

`~/.claude/CLAUDE.md` is Claude Code's global instruction file and is
loaded into every Claude Code session across every project on the
machine. Modifying it affects Claude's behavior everywhere, not just for
Power BI work. The pbi-cli block is bounded by comment markers so it can
be removed cleanly, but users on multi-tenant or sensitive machines
should be aware of this before running `pbi-cli skills install`.

## Bundled Binaries

`pbi-cli-tool` ships Microsoft Analysis Services client library DLLs
inside the PyPI wheel under `src/pbi_cli/dlls/`. These are unmodified
Microsoft binaries redistributed under Microsoft's own license terms,
**not** under MIT. See [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md)
and [`NOTICE`](NOTICE) at the repo root for full terms and attribution.
