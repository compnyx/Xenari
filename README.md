# Xenari

Canonical lexicon, translation engine, and curation tooling for the Xenari
conlang.

SQLite is the source of truth. Generated dictionaries, documentation, and site
assets are derived from it and must never be edited as canon.

## Layout

- `src/xenari/data/xenari.db` - canonical SQLite lexicon.
- `src/xenari/` - installable Python package.
- `src/xenari/db/` - lexicon queries, audits, and guarded mutation.
- `src/xenari/translate/` - forward and reverse translation.
- `src/xenari/services/` - curation, export, health, LLM, and gap workflows.
- `src/xenari/cli/` - command-line parsing and dispatch.
- `src/xenari/data/translator-fixtures.json` - shared behavior contract.
- `src/xenari/data/xenari-runtime.json` - generated, packaged runtime tables.
- `data/xenari-dict.json` - generated full dictionary export.
- `tests/` - behavior, canon, packaging, and compatibility checks.
- `docs/reference/LLM_REFERENCE.md` - compact grammar reference.
- `docs/development/architecture.md` - ownership and integration boundaries.
- `docs/development/versioning.md` - compatibility and release policy.

The root `xenari.db` link and `xenari_tool.py` entrypoint support repository
workflows. New Python code should import from the `xenari` package.

## Install Or Run From The Checkout

```bash
python3 -m pip install -e '.[dev]'
xenari stats
```

The checkout entrypoint works without installation:

```bash
python3 xenari_tool.py stats
python3 xenari_tool.py lookup love
python3 xenari_tool.py translate "I love you"
python3 xenari_tool.py translate "ra mex ka neq ta zrent sa xa"
```

Run `xenari --help` or `python3 xenari_tool.py --help` for the complete command
surface and current options.

## Common Workflows

Inspect canon and tool health:

```bash
python3 xenari_tool.py doctor
python3 xenari_tool.py parity
python3 xenari_tool.py workbench
python3 xenari_tool.py review --output xenari-qc-report.md
python3 xenari_tool.py audit 20
python3 xenari_tool.py lint 20
```

Search and inspect vocabulary:

```bash
python3 xenari_tool.py lookup love
python3 xenari_tool.py inspect fatyih
python3 xenari_tool.py search dangerous
python3 xenari_tool.py near "soft unsteady light"
python3 xenari_tool.py relations fatyih
python3 xenari_tool.py categories
python3 xenari_tool.py pos verb --limit 20
python3 xenari_tool.py pos --unknown --limit 20
python3 xenari_tool.py pos --proposals --format json
```

Translate and validate model output:

```bash
python3 xenari_tool.py speak "I see the alien" --evidential witnessed
python3 xenari_tool.py gloss "I love you"
python3 xenari_tool.py reverse "ra mex ka neq ta zrent sa xa"
python3 xenari_tool.py speak "Run!" --format json
python3 xenari_tool.py speak "Please help me!"
python3 xenari_tool.py reverse "ra nu praq ta nrotm vi ko xo ngu"
python3 xenari_tool.py llm-context "If you can't translate it, fix it."
python3 xenari_tool.py llm-lint "ra mex ka neq ta zrent sa xa"
```

Harvest vocabulary gaps without mutating canon:

```bash
python3 xenari_tool.py gaps scripts/movie.txt --output xenari-gaps.md
python3 xenari_tool.py gaps scripts/*.txt --format json --limit 0
```

Curate and coin with explicit previews:

```bash
python3 xenari_tool.py curate --placeholder --limit 20
python3 xenari_tool.py categorize --root anhthu
python3 xenari_tool.py propose-root glimmer "soft unsteady light"
python3 xenari_tool.py coin glimmer "soft unsteady light" --root zakglu --dry-run
python3 xenari_tool.py relate brak plonq --relation synonym --dry-run
python3 xenari_tool.py duplicates --confidence high --kind possible_synonym --limit 20
python3 xenari_tool.py pos-set ear cromq noun --dry-run
python3 xenari_tool.py benchmark --iterations 100 --format json
python3 xenari_tool.py check --format json
```

## Mutation Safety

Database writes preview by default and require `--yes`. Schema migrations and
guarded curation writes create timestamped SQLite backups before changing
canon. Part of speech is attached to an English-key/root sense, not globally
to a potentially polysemous Xenari root.

```bash
python3 xenari_tool.py add byte qevk "byte" --dry-run
python3 xenari_tool.py add byte qevk "byte" --yes
python3 xenari_tool.py map perilous fatyih "dangerous adjective" --yes
python3 xenari_tool.py remove oldroot --dry-run
```

After a canon change, regenerate derived data and run the release gates:

```bash
python3 xenari_tool.py check
```

The aggregate check verifies canon health, shared translator fixtures, and both
generated package exports. Site drift/build checks remain in the paired site
repository because they require its JavaScript toolchain.

```bash
python3 xenari_tool.py sync --site
python3 xenari_tool.py doctor
python3 xenari_tool.py parity
python3 xenari_tool.py export-json --check
python3 xenari_tool.py export-runtime --check
pytest -q
```

`sync --site` resolves the site checkout from `--site-root`, then
`XENARI_SITE_ROOT`, then `~/nyx-site`. It refreshes both the dictionary and
the versioned Python/browser runtime contract.

## Canon And Quality Rules

- Mutate `src/xenari/data/xenari.db` first; regenerate everything else.
- Do not merge roots solely because their English glosses overlap. Synonyms,
  registers, particles, and derived families can legitimately share wording.
- Treat translator fixtures as a cross-runtime contract, not examples to update
  merely to make a failing implementation green.
- Add focused regressions for grammar, parser, CLI, or validator behavior.
- Keep the LLM reference compact; use the DB or generated JSON for vocabulary.

The browser and Python translators share the fixture contract. Run
`npm run test:xenari` in `nyx-site` after translator or fixture changes.

`speak`, `gloss`, `translate`, and `reverse` accept `--format json`. The
structured report distinguishes complete, partial, and unsupported deterministic
output by reading explicit translator diagnostics; it is not a claim of semantic
certainty.

## Further Documentation

- [Architecture](docs/development/architecture.md)
- [Versioning and compatibility](docs/development/versioning.md)
- [Changelog](CHANGELOG.md)
- [LLM grammar reference](docs/reference/LLM_REFERENCE.md)
- [Known-good phrases](examples/phrases.md)
