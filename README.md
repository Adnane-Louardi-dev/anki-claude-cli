# anki-cli-unofficial

**AI-powered Anki deck generator, batteries-included with [Claude Code](https://claude.com/claude-code).**

Drop a PDF, a folder of Markdown notes, or both into `inputs/`. Run one slash command. Get a polished `.apkg` deck — atomic cards, embedded figures, auto-generated diagrams, deduped and reviewed.

> Not affiliated with the official Anki project. The CLI runs against a sandbox Anki directory by default; never points at your real collection unless you explicitly opt in.

---

## Quick start (AI mode)

Prerequisites:
- Python 3.10+
- [Anki Desktop](https://apps.ankiweb.net/) installed (the CLI reads/writes Anki collections)
- [Claude Code](https://claude.com/claude-code) installed and authenticated
- Optional, for diagrams: `npm install -g @mermaid-js/mermaid-cli`

```shell
git clone https://github.com/julien-sobczak/anki-cli
cd anki-cli
pip install -e .
```

Then in the project directory:

```shell
# 1. Drop your source material
cp ~/Downloads/chapter-3.pdf inputs/

# 2. Open Claude Code in this repo
claude

# 3. Run the skill
> /generate-flashcards
```

You get `out/chapter-3.apkg` — a deck named `chapter-3` (after the file). Import it into Anki.

**Re-running:** drop another file (`chapter-4.pdf`) into `inputs/` later and run `/generate-flashcards` again. The pipeline only processes new files; already-generated sources have been moved to `inputs/processed/` and won't be touched. Your existing `chapter-3` deck in Anki stays as it is.

**Regenerating a deck:** move the file back from `inputs/processed/` into `inputs/` and re-run. (Heads up: the new `.apkg` will create duplicates if imported on top of the old deck — delete the old deck in Anki first.)

The four-stage pipeline runs:

```
inputs/*.pdf, *.md
        │
        ▼
  /generate-flashcards   ← orchestrator skill
        │
        ├── extractor      → concept-outline.json (concepts, figures)
        ├── card-writer    → drafts.yaml (atomic Basic / Cloze cards)
        ├── diagram-maker  → media/*.png (Mermaid → PNG)
        └── reviewer       → cards.yaml (deduped, reviewed)
        │
        ▼
  anki-cli-unofficial load --yes --media-dir media cards.yaml deck.apkg
```

Open `deck.apkg` in Anki, hit **Import**, and you're done.

### What makes the deck good

The hard work is in the agent prompts under [.claude/agents/](.claude/agents/). The differences from generic AI flashcard tools:

- **Atomic cards by construction.** The card-writer agent enforces the [minimum-information principle](https://supermemo.guru/wiki/20_rules_for_formulating_knowledge): one card, one fact.
- **A real reviewer pass.** The [reviewer agent](.claude/agents/reviewer.md) drops duplicates, fixes leading questions, splits multi-fact answers, flags unverified claims. This is the line between a deck you'd actually study and AI slop.
- **Diagrams when structure beats prose.** The [diagram-maker](.claude/agents/diagram-maker.md) emits Mermaid for sequences, hierarchies, and comparisons — rendered locally to PNG, no external image API.
- **Source figures preserved.** The extractor pulls embedded figures out of PDFs into `media/` and the writer attaches them to the relevant cards.

---

## Manual mode (YAML)

You can also write cards by hand and skip the AI pipeline. The YAML schema is the same one the agents produce.

```yaml
# cards.yaml
- type: Basic
  tags: [idiom]
  fields:
    Front: "Avoir la banane! <small>idiom</small>"
    Back: "To feel great. (literally: to have the banana)"

- type: Cloze
  tags: [chemistry]
  fields:
    Text: "Photosynthesis converts {{c1::light energy}} into {{c2::chemical energy}}."
    Back Extra: ""
```

Run:

```shell
anki-cli-unofficial load --yes --media-dir ./media cards.yaml deck.apkg
```

### CLI options

```
anki-cli-unofficial load [-h] [--anki-dir ANKI_DIR] [--media-dir MEDIA_DIR]
                         [--deck DECK] [--yes] [--force]
                         [--allow-default-anki-dir]
                         input_file output_file

  --anki-dir              Anki user directory (default: a fresh temp directory)
  --media-dir             Local directory containing media referenced in input_file
  --deck                  Deck name (created if missing). Defaults to the input file's stem.
  --yes, -y               Auto-confirm all prompts (required for scripted use)
  --force                 Overwrite the output archive if it exists
  --allow-default-anki-dir  Permit writing to your real Anki directory (dangerous)
  -v, --verbose           Verbose logging
  -q, --quiet             Warnings and errors only
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0    | Success |
| 2    | Bad input (missing file, invalid YAML, unknown note type or field) |
| 3    | Anki error during load or export |
| 4    | User aborted at a prompt |

### Media

Embed media in card fields with the standard Anki syntax:
- `<img src="filename.jpg" />` for images
- `[sound:filename.mp3]` for audio

The CLI copies referenced files from `--media-dir` into the collection's media store. Missing files log a warning but don't fail the load.

### Multilingual / non-English Anki

If your Anki installation uses a non-English locale, the default note types and deck name are translated. Initialize a sandbox Anki dir in the right locale and use the translated names in your YAML:

```shell
# Create a French Anki home
anki -l fr -b ./ankidir

# Use translated names in YAML
- type: Basique
  fields:
    Recto: 'Avoir la banane!'
    Verso: 'To feel great.'

# Pass the localized deck name
anki-cli-unofficial load --yes \
    --deck="Par défaut" \
    --anki-dir="./ankidir/Utilisateur 1/" \
    cards.yaml deck.apkg
```

### Running against your real Anki collection

**Don't.** The CLI defaults to a sandbox temp directory for a reason — bugs happen. If you really need to load directly into your collection:

1. Back up your Anki dir (zip the whole thing — Anki's internal backups don't include media).
2. Pass `--anki-dir <path>` and `--allow-default-anki-dir`.
3. The CLI refuses to export when targeting an existing collection. Open Anki, find the new cards by tag, and use **Browser → Export** manually.

---

## Development

```shell
git clone https://github.com/julien-sobczak/anki-cli
cd anki-cli
pip install -e ".[dev]"
pytest
```

Tests run against a fresh per-test Anki collection (see [tests/conftest.py](tests/conftest.py)). CI runs on Python 3.10/3.11/3.12 — see [.github/workflows/test.yml](.github/workflows/test.yml).

### Architecture at a glance

- [ankicli/loader.py](ankicli/loader.py) — YAML → Anki notes. Validates schema, maps fields by name (not dict order), copies referenced media. Pure library code, no CLI concerns.
- [ankicli/cli.py](ankicli/cli.py) — argparse, logging, exit codes. Orchestrates `Loader` for the `load` subcommand.
- [.claude/skills/generate-flashcards/](.claude/skills/generate-flashcards/) — the Claude Code skill that wraps the AI pipeline.
- [.claude/agents/](.claude/agents/) — the four subagents (extractor, card-writer, diagram-maker, reviewer).

The agents shell out to `anki-cli-unofficial load` rather than importing the loader as a library — keeps coupling low.

### Release

Bump `version` in [pyproject.toml](pyproject.toml), commit, push, create a tag in GitHub. CI builds and publishes to PyPI via [.github/workflows/publish-to-pypi.yml](.github/workflows/publish-to-pypi.yml).

---

## License

MIT. See [LICENSE](LICENSE).
