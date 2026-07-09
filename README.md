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
python3 xenari_tool.py audit
python3 xenari_tool.py doctor
```

Regenerate JSON after DB edits:

```bash
python3 scripts/export_json.py
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
