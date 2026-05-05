# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`anki-cli-unofficial` — an AI-powered Anki deck generator. The Python CLI takes YAML-described flashcards and produces an Anki `.apkg` archive. A Claude Code skill at [.claude/skills/generate-flashcards/SKILL.md](.claude/skills/generate-flashcards/SKILL.md) orchestrates four subagents (extractor, card-writer, diagram-maker, reviewer) that turn dropped PDFs/Markdown in `inputs/` into the YAML the CLI consumes.

Published to PyPI as `anki-cli-unofficial` via GitHub Actions on tag push (see [.github/workflows/publish-to-pypi.yml](.github/workflows/publish-to-pypi.yml)).

## Development

```shell
pip install -e ".[dev]"
pytest                                     # full suite (requires anki>=2.1.50)
pytest tests/test_parse_cards.py           # YAML-only tests, no anki dep
pytest -v -k "field_mapping"               # single test by name match
ruff check                                 # lint
```

CI runs on Python 3.10/3.11/3.12 — see [.github/workflows/test.yml](.github/workflows/test.yml).

## Architecture

Two layers in the Python package, plus the AI pipeline as a separate concern:

1. **YAML → Anki notes — [ankicli/loader.py](ankicli/loader.py).**
   - `parse_cards(path)` does YAML schema validation only — checks `type`/`tags`/`fields` shape. Anki-aware validation (note type and field names exist in the collection) happens in `Loader.load`.
   - `Loader` opens the Anki `Collection`, resolves the note type via `col.models.by_name`, creates a note via `col.new_note(notetype)`, and assigns YAML fields **by field name → declared field index**, not by dict order. Unknown note types raise `UnknownNoteTypeError`; unknown fields raise `UnknownFieldError`. Both subclass `ValueError`.
   - Field values are scanned with `SOUND_RE`/`IMG_RE` regexes for `[sound:...]` and `<img src="..."/>`; matching files are copied from `--media-dir` to the collection media store via `col.media.add_file`. Missing media warns but does not fail.

2. **CLI — [ankicli/cli.py](ankicli/cli.py).**
   - `argparse` with one subcommand, `load`. Resolves the Anki home dir (temp sandbox by default, or `--anki-dir`).
   - Non-interactive by default when `--yes` is passed. Refuses to prompt if stdin isn't a TTY and `--yes` wasn't given.
   - `--allow-default-anki-dir` is the only way to write into the user's real Anki directory.
   - Stable exit codes: `0` ok, `2` bad input, `3` Anki error, `4` user aborted. Errors caught at the boundary translate `CardSchemaError` / `UnknownNoteTypeError` / `UnknownFieldError` to clean log lines, no stack traces.
   - Logging via stdlib `logging`; emoji-prefixed messages go through `log.info/error`. `--quiet` and `--verbose` toggle level.

3. **Claude Code agents — [.claude/skills/](.claude/skills/) and [.claude/agents/](.claude/agents/).**
   The skill is the orchestrator. The four agents run in sequence, each in its own context window. They communicate via files in the repo root (`concept-outline.json`, `drafts.yaml`, `cards.yaml`) and `media/`. Agents shell out to `anki-cli-unofficial load --yes` rather than importing `Loader` — deliberately low-coupled, so a broken agent can't trash the loader's behavior.

### YAML contract

```yaml
- type: Basic                # must match an Anki model name (locale-dependent: "Basique" in fr)
  tags: [tag1, tag2]         # optional, defaults to []
  fields:                    # field-name → value; mapping order does not matter
    Front: '<img src="car.jpg" />'
    Back: '[sound:voiture.mp3] Voiture'
```

`Cloze` is also fully supported (`Text` and `Back Extra` fields).

### Two operating modes

- **Sandbox (default):** `cli.py` creates a temp dir as a fresh Anki home, loads cards into it, exports a `.apkg`, and prints the OS-specific command to open Anki against the sandbox so the user can verify before importing.
- **Real Anki dir (`--anki-dir`):** loads cards directly into an existing collection. **Refuses to export** in this mode (avoids dumping the entire collection). If the path matches the OS default Anki dir, also requires `--allow-default-anki-dir`.

### Localization

Anki model names and the default deck are localized. French Anki uses `Basique` and `"Par défaut"`. The CLI handles this via `--deck` and the YAML `type` value; the user's `--anki-dir` must have been initialized with the matching locale (`anki -l fr -b ./ankidir`). See README.md "Multilingual" section.

## Conventions

- The loader is reused by every entry path (CLI, tests, agents). Don't add agent-specific code paths into it.
- Tests live in [tests/](tests/). The conftest uses `pytest.importorskip("anki")` so the test module skips cleanly when anki is missing — useful for the `test_parse_cards.py` subset that has no anki dep.
- Python deps are declared in [pyproject.toml](pyproject.toml) (PEP 621). The legacy `setup.py` and `scripts/anki-cli-unofficial` shim were removed; the console script is now a `[project.scripts]` entry point.
