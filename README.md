# Xenari

Canon source package for the Xenari conlang.

This repository is intentionally small. The SQLite database is the canonical
lexicon; the Markdown docs are teaching references for LLMs and humans, not the
source of truth.

## Contents

- `xenari.db` - canonical SQLite lexicon database.
- `xenari_db.py` - database wrapper for lookup, search, export, and validation.
- `xenari_tool.py` - compatibility CLI/import entrypoint.
- `xenari_core.py` - `Xenari` facade assembled from focused tool mixins.
- `xenari_cli.py` - command-line interface.
- `xenari_lookup.py`, `xenari_translate.py`, `xenari_export.py`,
  `xenari_health.py`, `xenari_mutation.py` - focused helper modules.
- `data/xenari-dict.json` - generated full JSON dictionary export.
- `docs/LLM_REFERENCE.md` - compact grammar and usage reference for LLMs.
- `examples/phrases.md` - known-good examples.
- `scripts/export_json.py` - regenerate `data/xenari-dict.json` from `xenari.db`.

## Quick Start

```bash
python3 xenari_tool.py stats
python3 xenari_tool.py lookup love
python3 xenari_tool.py inspect fatyih
python3 xenari_tool.py info fatyih
python3 xenari_tool.py validate fatyih qip
python3 xenari_tool.py speak "I love you" --evidential witnessed
python3 xenari_tool.py translate "I love you"
python3 xenari_tool.py translate "ra mex ka neq ta zrent sa xa"
python3 xenari_tool.py workbench
python3 xenari_tool.py review --output xenari-qc-report.md
python3 xenari_tool.py parity
python3 xenari_tool.py search "soul"
python3 xenari_tool.py near "dangerous"
python3 xenari_tool.py relations fatyih
python3 xenari_tool.py propose-root glimmer "soft unsteady light"
python3 xenari_tool.py coin glimmer "soft unsteady light"
python3 xenari_tool.py reverse "ra mex ka neq ta zrent sa xa"
python3 xenari_tool.py audit
python3 xenari_tool.py lint
python3 xenari_tool.py curate --placeholder --limit 20
python3 xenari_tool.py categorize --root anhthu
python3 xenari_tool.py relate brak plonq --relation synonym --dry-run
python3 xenari_tool.py doctor
python3 xenari_tool.py meta
python3 xenari_tool.py sync
```

Regenerate JSON after DB edits:

```bash
python3 xenari_tool.py sync
python3 xenari_tool.py sync --site
python3 xenari_tool.py export json
python3 xenari_tool.py export site
```

Run regression tests after tool or parser changes:

```bash
python3 xenari_tool.py parity
pytest -q
```

## Canon Rules

- `xenari.db` is canon.
- Generated files must be rebuilt from the DB, not edited by hand.
- `docs/LLM_REFERENCE.md` should stay compact. Do not paste the full lexicon into
  it.
- Use `data/xenari-dict.json` or the SQLite DB for full vocabulary access.

## Audit

Use `audit` before and after lexicon cleanup:

```bash
python3 xenari_tool.py workbench
python3 xenari_tool.py audit 25
python3 xenari_tool.py doctor
```

It reports duplicate root strings, duplicate meanings/headwords, stale
conflict/reanalysis markers, broad English-key collisions, and phonotactic
validator failures.

`doctor` is the compact release-gate check for common phrase generation,
critical lookups, and actionable audit failures.

`workbench` is the agent-friendly command to run before or after a change. It
prints stats, doctor status, audit counters, a small lint preview, and the next
commands that usually matter.

Use `review` when you want a shareable, read-only Markdown artifact for a human
or Codex follow-up:

```bash
python3 xenari_tool.py review --limit 10
python3 xenari_tool.py review --limit 20 --output xenari-qc-report.md
```

The report combines doctor, parity, audit, lint, and curation queues. It never
writes the database; `--output` only writes the Markdown report file.

Use `gaps` when you want to harvest missing script vocabulary before coining
anything:

```bash
python3 xenari_tool.py gaps scripts/movie.txt --output xenari-gap-harvest.md
python3 xenari_tool.py gaps scripts/*.txt --limit 0 --phrase-min-count 1
python3 xenari_tool.py gaps scripts/movie.txt --format json --output xenari-gap-harvest.json
```

`gaps` is a read-only vacuum pass over script text. It captures every unknown
word that is not already covered by the DB/lexicon lookup, keeps raw forms and
source contexts, and sorts candidates into review buckets:

- lexical gaps
- phrase gaps
- sound effects
- vocalizations
- names and places
- inflection variants
- script format markers
- grammar-covered function words
- extraction noise

Sound effects and vocalizations are first-class lexical candidates, not junk.
Use them for impact, ambience, body sounds, interjections, and emotion roots.
Script format markers such as `INT`, `EXT`, and `cont'd` are separated from the
lexical queue so screenplay structure does not crowd out real vocabulary gaps.
`--phrase-min-count` controls repeated phrase sensitivity; use `1` when you want
even one-off phrase candidates. `--limit 0` prints every candidate in Markdown.

Use `lint` for softer review targets that need human judgment, such as
phrase-like definitions, English-looking roots, and placeholder categories. Lint
findings are not automatic cleanup failures.

Use `curate` for the deeper human-review queue:

```bash
python3 xenari_tool.py curate --placeholder --limit 20
python3 xenari_tool.py curate --phrases --limit 20
python3 xenari_tool.py curate --relations --limit 20
python3 xenari_tool.py curate 20
```

With no section flag, `curate` shows all three queues. Placeholder suggestions
are grouped by proposed category and include confidence plus the matched reason.
Relation candidates are hypotheses classified as possible synonyms, register
variants, category clashes, or false friends. They are review aids, not facts.

Use `categorize` to preview the same placeholder-category proposals. A write
requires `--yes` and a root/category target, or explicit `--all`. Ambiguous rows
are skipped unless `--include-ambiguous` is also present. `--limit` controls
display only, not the rows written.

```bash
python3 xenari_tool.py categorize --root anhthu
python3 xenari_tool.py categorize --root anhthu --yes
python3 xenari_tool.py categorize --category Uncategorized --limit 20
python3 xenari_tool.py categorize --category Uncategorized --yes
python3 xenari_tool.py categorize --all --yes
```

Every `categorize --yes` write creates a timestamped SQLite backup beside the
database before updating rows. Prefer root-level writes; review a category-wide
preview before using a category target or `--all`.

Use `propose-root` before coining vocabulary:

```bash
python3 xenari_tool.py propose-root glimmer "soft unsteady light" --limit 8
python3 xenari_tool.py coin glimmer "soft unsteady light"
python3 xenari_tool.py near "soft unsteady light"
```

It suggests valid unused roots, shows near existing meanings, guesses category,
and warns about close roots or Englishy/cognate smell before anything touches
the DB.

Use `coin` for the safer root-coining workflow. Without `--root`, it scouts
near meanings and candidate roots. With `--root`, it previews the add. With
`--yes`, it writes, syncs generated JSON, and runs `doctor`.

```bash
python3 xenari_tool.py coin glimmer "soft unsteady light" --limit 8
python3 xenari_tool.py coin glimmer "soft unsteady light" --root zakglu --dry-run
python3 xenari_tool.py coin glimmer "soft unsteady light" --root zakglu --yes
python3 xenari_tool.py coin glimmer "soft unsteady light" --root zakglu --yes --site
```

Use `relations` to inspect semantic and compound links:

```bash
python3 xenari_tool.py inspect fatyih
python3 xenari_tool.py relations fatyih
```

For a relation candidate, inspect both roots before recording anything. Curate
only prints a `relate ... --dry-run` suggestion for synonym/register hypotheses
with exactly two roots. `relate` previews by default, requires an explicit
relation type, and creates a timestamped backup before a `--yes` write.

```bash
python3 xenari_tool.py relations brak
python3 xenari_tool.py relations plonq
python3 xenari_tool.py relate brak plonq --relation synonym --dry-run
python3 xenari_tool.py relate brak plonq --relation synonym --notes "curator-reviewed" --yes
```

Use `translate` for auto-direction translation, or `reverse` for an explicit
canon-side Xenari to English check:

```bash
python3 xenari_tool.py translate "I love you"
python3 xenari_tool.py translate "ra mex ka neq ta zrent sa xa"
python3 xenari_tool.py reverse "ra mex ka neq ta zrent sa xa"
python3 xenari_tool.py llm-context "If you can't translate it, fix it."
python3 xenari_tool.py llm-lint "ra mex ka neq ta zrent sa xa"
```

The browser translator and Python CLI share regression fixtures in
`data/translator-fixtures.json`. Use `parity` for the Python side of that
contract and `npm run test:xenari` in `nyx-site` for the browser side.
The shared fixtures cover pronoun object case (`you love me`), pronoun
possessives (`my hat`), and tense/negation reverse rendering.

For LLM-backed translation experiments, use `llm-context` to package compact
canon hints for the model and `llm-lint` to check a proposed Xenari candidate.
The LLM is the semantic translator/interpreter; this tool only checks hard
constraints such as known roots, known particles, and basic clause shape.
Do not treat the deterministic translator as the semantic judge.

## Mutating The DB

DB mutation commands preview by default and require `--yes` to write:

```bash
python3 xenari_tool.py add byte qevk "byte" --dry-run
python3 xenari_tool.py add byte qevk "byte" --yes
python3 xenari_tool.py map perilous fatyih "dangerous adjective" --yes
python3 xenari_tool.py remove oldroot --dry-run
python3 xenari_tool.py remove oldroot --yes
```

After any DB mutation, run:

```bash
python3 xenari_tool.py sync --site
python3 xenari_tool.py doctor
pytest -q
```

## Metadata

The DB contains a small `tool_meta` table for internal schema/tool metadata.
Check it with:

```bash
python3 xenari_tool.py meta
```
