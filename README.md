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
python3 xenari_tool.py parity
python3 xenari_tool.py search "soul"
python3 xenari_tool.py near "dangerous"
python3 xenari_tool.py relations fatyih
python3 xenari_tool.py propose-root glimmer "soft unsteady light"
python3 xenari_tool.py coin glimmer "soft unsteady light"
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

Use `lint` for softer review targets that need human judgment, such as
phrase-like definitions, English-looking roots, and placeholder categories. Lint
findings are not automatic cleanup failures.

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

Use `translate` for auto-direction translation, or `reverse` for an explicit
canon-side Xenari to English check:

```bash
python3 xenari_tool.py translate "I love you"
python3 xenari_tool.py translate "ra mex ka neq ta zrent sa xa"
python3 xenari_tool.py reverse "ra mex ka neq ta zrent sa xa"
```

The browser translator and Python CLI share regression fixtures in
`data/translator-fixtures.json`. Use `parity` for the Python side of that
contract and `npm run test:xenari` in `nyx-site` for the browser side.

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
