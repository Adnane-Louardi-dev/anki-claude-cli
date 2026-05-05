---
name: generate-flashcards
description: Turn course material (PDFs, Markdown notes) dropped in `inputs/` into Anki .apkg decks — one deck per input file or folder, named after the source. Use when the user asks to generate flashcards from source material, build a study deck from a textbook chapter or notes, or run the AI flashcard pipeline.
---

# generate-flashcards

You are the orchestrator for an AI flashcard generation pipeline.

## The mental model

**One input → one deck → one `.apkg` file.** Each top-level entry in `inputs/` is processed independently. After a successful run, the source is moved to `inputs/processed/` so the next run only handles new material.

```
inputs/
├── chapter-3.pdf       →  out/chapter-3.apkg     (deck: "chapter-3")
└── ml-notes/           →  out/ml-notes.apkg      (deck: "ml-notes")
    ├── lecture1.md
    └── lecture2.md

inputs/processed/       ← already-generated sources live here
```

The user's claim to fame is **deck quality**, not deck volume. One well-formed atomic card beats five mushy ones. Reject the temptation to over-generate.

## Process

1. **Inventory `inputs/`** (excluding `inputs/processed/`). Each top-level file (`.pdf`, `.md`, `.markdown`, `.txt`) and each top-level directory is one job.
2. **If `inputs/` has nothing new**, tell the user and stop. Do not reach into `inputs/processed/`.
3. **If the user passed `--all`** (or said something like "regenerate everything"), also include entries already in `inputs/processed/` by treating that directory as the source.
4. **For each job**, run the four-stage pipeline (below) in a job-scoped working directory `out/<name>/` where `<name>` is the file stem or folder name. Artifacts go there so jobs don't clobber each other.
5. **After all jobs**, summarize: list each deck, card count by type, and where the `.apkg` files are.

## The four stages (per job)

Each subagent runs in its own context window. Invoke them via the Agent tool with `subagent_type` matching the agent name. Pass paths explicitly.

1. **`extractor`** — reads the job's input(s), emits `out/<name>/concept-outline.json`: a flat list of `{concept, summary, source_ref, figure_paths[]}` where `figure_paths` are PNGs already extracted into `out/<name>/media/`.
2. **`card-writer`** — consumes `concept-outline.json`, writes `out/<name>/drafts.yaml`. One concept becomes 1–3 atomic cards (Basic or Cloze). Tags reflect source structure.
3. **`diagram-maker`** — adds Mermaid-rendered diagrams to cards that benefit from them, dropping PNGs into `out/<name>/media/`. Skipped silently if `mmdc` is not installed.
4. **`reviewer`** — reads `drafts.yaml`, drops duplicates, fixes ambiguous wording, flags unverified claims, writes the final `out/<name>/cards.yaml`.

## Packaging

After the four stages succeed, package the deck:

```bash
anki-cli-unofficial load --yes \
    --media-dir out/<name>/media \
    --deck "<name>" \
    out/<name>/cards.yaml \
    out/<name>.apkg
```

The CLI defaults `--deck` to the input filename's stem if you omit `--deck`, but pass it explicitly to be safe (a folder of markdown wouldn't have its name derived correctly otherwise).

If the CLI exits non-zero, surface its error message verbatim and stop the job — do not retry. Do **not** move the source file to `processed/` for a failed job.

## After a successful job

Move the source out of the queue:

```bash
mv inputs/<name>{,.pdf}        inputs/processed/
# or for folders:
mv inputs/<name>/              inputs/processed/
```

This is what makes re-runs predictable: dropping a new file into `inputs/` next week processes only the new file. The user's existing decks in Anki are untouched.

## Re-running a previously generated source

If the user wants to regenerate `chapter-3.pdf` from scratch, instruct them to move it back: `mv inputs/processed/chapter-3.pdf inputs/`. Then run the skill again. (Or accept a `--all` flag and process `inputs/processed/` in place.)

When the user re-imports the new `out/chapter-3.apkg` into Anki, Anki merges by note GUID. Since GUIDs change between pipeline runs, this will create duplicate cards in Anki. Warn the user before they re-import a regenerated deck — the cleanest path is to delete the old `chapter-3` deck in Anki first.

## Output contract (the YAML schema every agent must respect)

```yaml
- type: Basic                # "Basic" or "Cloze" — the only types we support in v1
  tags: [chapter-3, neural-networks]
  fields:                    # field names must match the note type exactly
    Front: "What is backpropagation?"
    Back: "An algorithm that computes the gradient of the loss with respect to each weight by applying the chain rule backwards through the network."
```

For Cloze:

```yaml
- type: Cloze
  tags: [chapter-3]
  fields:
    Text: "{{c1::Backpropagation}} computes gradients via the chain rule."
    Back Extra: ""
```

Field-name matching is strict (validated in [ankicli/loader.py](ankicli/loader.py)). A typo like `front` instead of `Front` will fail the load step.

## Card design conventions (the difference between this deck and AI slop)

- **Minimum information principle.** One card, one fact.
- **No leading questions.** "What is the most important benefit of X?" is bad. "What does X do?" is fine.
- **Atomic.** A card the user gets wrong should point to one missing piece of knowledge, not a topic.
- **Cloze for definitions, Basic for Q→A facts.**
- **Diagrams when structure beats prose** (sequences, hierarchies, comparisons). Otherwise plain text.
- **No "according to the text" hedging.** The card should stand on its own.

## Failure handling

- If `inputs/` has only `processed/` and no new entries, tell the user clearly and stop.
- If the extractor finds zero concepts in a job, surface the filename and skip to the next job — do not produce an empty deck.
- If a job's `cards.yaml` has fewer than 5 cards after review, ask the user whether to keep it (might indicate weak source material).
- The reviewer agent has authority to drop cards. Trust its decisions.

## After the run

Tell the user, per deck:
- The `.apkg` path.
- Card count by type (Basic/Cloze) and by tag.
- Anything the reviewer flagged but didn't drop ("3 cards reference unverified claims; review before studying").
- The source file's new location: `inputs/processed/<name>`.
