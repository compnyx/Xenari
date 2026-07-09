# Xenari

Canon source package for the Xenari conlang.

This repository is intentionally small. The SQLite database is the canonical
lexicon; the Markdown docs are teaching references for LLMs and humans, not the
source of truth.

## Contents

- `xenari.db` - canonical SQLite lexicon database.
- `xenari_db.py` - database wrapper for lookup, search, export, and validation.
- `xenari_tool.py` - CLI/helper used to lookup, speak, gloss, and export Xenari.
- `data/xenari-dict.json` - generated full JSON dictionary export.
- `docs/LLM_REFERENCE.md` - compact grammar and usage reference for LLMs.
- `examples/phrases.md` - known-good examples.
- `scripts/export_json.py` - regenerate `data/xenari-dict.json` from `xenari.db`.

## Quick Start

```bash
python3 xenari_tool.py stats
python3 xenari_tool.py lookup love
python3 xenari_tool.py info fatyih
python3 xenari_tool.py validate fatyih qip
python3 xenari_tool.py speak "I love you" --evidential witnessed
python3 xenari_tool.py search "soul"
python3 xenari_tool.py near "dangerous"
python3 xenari_tool.py relations fatyih
python3 xenari_tool.py propose-root glimmer "soft unsteady light"
python3 xenari_tool.py reverse "ra mex ka neq ta zrent sa xa"
python3 xenari_tool.py audit
python3 xenari_tool.py lint
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
python3 xenari_tool.py audit 25
python3 xenari_tool.py doctor
```

It reports duplicate root strings, duplicate meanings/headwords, stale
conflict/reanalysis markers, broad English-key collisions, and phonotactic
validator failures.

`doctor` is the compact release-gate check for common phrase generation,
critical lookups, and actionable audit failures.

Use `lint` for softer review targets that need human judgment, such as
phrase-like definitions, English-looking roots, and placeholder categories. Lint
findings are not automatic cleanup failures.

Use `propose-root` before coining vocabulary:

```bash
python3 xenari_tool.py propose-root glimmer "soft unsteady light" --limit 8
python3 xenari_tool.py near "soft unsteady light"
```

It suggests valid unused roots, shows near existing meanings, guesses category,
and warns about close roots or Englishy/cognate smell before anything touches
the DB.

Use `relations` to inspect semantic and compound links:

```bash
python3 xenari_tool.py relations fatyih
```

Use `reverse` for a canon-side best-effort Xenari to English check:

```bash
python3 xenari_tool.py reverse "ra mex ka neq ta zrent sa xa"
```

The browser translator and Python CLI share regression fixtures in
`data/translator-fixtures.json`.

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
