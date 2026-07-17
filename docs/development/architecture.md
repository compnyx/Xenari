# Xenari Architecture

`src/xenari/data/xenari.db` is the canonical lexicon. The root `xenari.db`
path is a compatibility link. The Python package under `src/xenari`
provides lookup, translation, audit, mutation, export, and CLI behavior around
that canon. Generated dictionary JSON is derived and must not be edited by hand.

## Package boundaries

- `src/xenari/data/xenari.db`: canonical vocabulary and metadata.
- `src/xenari/db`: database connection, schema, queries, and canon mutation.
- `src/xenari/translate`: forward and reverse translation behavior.
- `src/xenari/services`: focused lookup, audit, export, mutation, LLM, and gap services.
- `src/xenari/facade.py`: compatibility-oriented `Xenari` facade composing services.
- `src/xenari/cli`: argument parsing and command dispatch.
- `data/`: generated dictionary and shared translator fixtures.
- `tests/`: behavior and compatibility tests.

The top-level `xenari_*.py` modules are compatibility shims. New code should
import from the `xenari` package. `python3 xenari_tool.py ...` remains supported.

## Integration paths

Site synchronization uses `--site-root`, then `XENARI_SITE_ROOT`, then
`~/nyx-site`. Repository code must not contain host-specific absolute paths.

## Refactoring rule

Split modules by semantic responsibility, not by the numbered hardening loop in
which behavior was introduced. Compatibility shims remain until downstream
consumers have migrated to package imports.
