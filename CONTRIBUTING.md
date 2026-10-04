# Contributing to pbi-cli

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/umarmf/pbi-cli-bi-developer.git
cd pbi-cli
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest                          # all tests
pytest -x -q                    # stop on first failure
pytest --cov=pbi_cli            # with coverage
pytest -m "not e2e"             # skip integration tests
```

## Code Quality

All checks must pass before submitting a PR:

```bash
ruff check src/ tests/          # linting
ruff format --check src/ tests/ # formatting
mypy src/                       # type checking
```

## Pull Request Process

1. Fork the repo and create a feature branch from `master`
2. Write tests for new functionality (target 80%+ coverage)
3. Ensure all checks pass (`ruff`, `mypy`, `pytest`)
4. Keep PRs focused on a single change
5. Use conventional commit messages: `feat:`, `fix:`, `docs:`, `test:`, `chore:`

## Project Structure

```
src/pbi_cli/
  commands/       # Click command groups (one file per domain)
  core/           # MCP client, config, output formatting
  skills/         # Claude Code SKILL.md files (bundled)
  utils/          # REPL, helpers
tests/            # Mirrors src/ structure
```

## Adding a New Command Group

1. Create `src/pbi_cli/commands/your_cmd.py`
2. Use `run_tool()` from `_helpers.py` for MCP calls
3. Register the group in `main.py` `_register_commands()`
4. Add tests in `tests/test_commands/test_your_cmd.py`

## Adding a New Skill

1. Create `src/pbi_cli/skills/your-skill/SKILL.md`
2. Follow the frontmatter format from existing skills
3. Test with `pbi-cli skills list` and `pbi-cli skills install`

## Reporting Issues

Open an issue on [GitHub](https://github.com/umarmf/pbi-cli-bi-developer/issues) with:

- What you expected to happen
- What actually happened
- Steps to reproduce
- Python version and OS

## Code of Conduct

Be respectful and constructive. We're all here to make Power BI development better.
