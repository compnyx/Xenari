# Xenari Architecture

`src/xenari/data/xenari.db` is the canonical lexicon. The root `xenari.db`
path is a compatibility link. The Python package under `src/xenari` provides
lookup, translation, audit, mutation, export, and CLI behavior around that
canon. Generated dictionary JSON is derived and must not be edited by hand.

## Package boundaries

- `src/xenari/data/xenari.db`: canonical vocabulary and metadata.
- `src/xenari/data/translator-fixtures.json`: packaged Python/browser contract.
- `src/xenari/db`: database connection, schema, queries, and canon mutation.
- `src/xenari/translate`: forward and reverse translation behavior.
- `src/xenari/services`: focused lookup, health, export, curation, LLM, and gap workflows.
- `src/xenari/facade.py`: compatibility-oriented `Xenari` facade composing services.
- `src/xenari/cli`: argument parsing and command dispatch.
- `data/`: source-checkout links and generated release artifacts.
- `tests/`: behavior and compatibility tests.

The root compatibility surface is intentionally limited to `xenari_tool.py`,
`xenari_db.py`, and their `xenari_compat.py` bootstrap. New code must import
from the `xenari` package. `python3 xenari_tool.py ...` remains supported.

Runtime resources must resolve from package data, not by walking upward to a
presumed Git checkout. Repository-only exports use an identified checkout or
the explicit `XENARI_REPO_ROOT` / `XENARI_GENERATED_DICTIONARY` overrides.

## Integration paths

Site synchronization uses `--site-root`, then `XENARI_SITE_ROOT`, then
`~/nyx-site`. Repository code must not contain host-specific absolute paths.

## Refactoring rule

Split modules by semantic responsibility, not by the numbered hardening loop in
which behavior was introduced. Do not add a compatibility shim without a known
downstream consumer and a documented removal condition.
