# Xenari Architecture

`src/xenari/data/xenari.db` is the canonical lexicon. The root `xenari.db`
path is a compatibility link. The Python package under `src/xenari` provides
lookup, translation, audit, mutation, export, and CLI behavior around that
canon. Generated dictionary JSON is derived and must not be edited by hand.

## Package boundaries

- `src/xenari/data/xenari.db`: canonical vocabulary and metadata.
- `src/xenari/data/translator-fixtures.json`: packaged Python/browser contract.
- `src/xenari/data/xenari-runtime.json`: generated, packaged runtime tables.
- `src/xenari/db`: database connection, schema, queries, and canon mutation.
- `src/xenari/translate`: forward and reverse translation behavior.
- `src/xenari/services`: focused lookup, health, export, curation, LLM, and gap workflows.
- `src/xenari/components.py`: explicit lexicon, translation, curation, and health services.
- `src/xenari/facade.py`: shared state and a thin compatibility-oriented `Xenari` API.
- `src/xenari/cli`: argument parsing and command dispatch.
- `data/`: source-checkout links and generated release artifacts.
- `tests/`: behavior and compatibility tests.

The root compatibility surface is intentionally limited to `xenari_tool.py`.
New code must import from the `xenari` package. The repository entrypoint adds
the local `src` directory itself, so `python3 xenari_tool.py ...` remains
supported without maintaining duplicate import modules.

Runtime resources must resolve from package data, not by walking upward to a
presumed Git checkout. Repository-only exports use an identified checkout or
the explicit `XENARI_REPO_ROOT`, `XENARI_GENERATED_DICTIONARY`, or
`XENARI_GENERATED_RUNTIME` overrides.

## Integration paths

Site synchronization uses `--site-root`, then `XENARI_SITE_ROOT`, then
`~/nyx-site`. It copies the generated dictionary and runtime contract; browser
code consumes those artifacts rather than maintaining copies of Python tables.
Repository code must not contain host-specific absolute paths.

## Known boundaries

Mypy currently gates the new immutable grammar, runtime-contract, version,
and typed translation-model modules. The older translation mixins still use
dynamic facade attributes and are being migrated module by module; they are
not falsely declared type-clean. Ruff, tests, parity, and coverage continue to
cover the full package.

- Python and browser translation use separate parsers but consume one generated
  grammar/runtime contract. Packaged fixtures define the behavior both runtimes
  promise.
- The lexicon stores conservative part-of-speech metadata on individual English
  mapping senses. Unknown and genuinely ambiguous senses remain unannotated and
  use legacy browser inference; curator review expands coverage safely.
- Generic forward translation is strongest for simple, pronoun-led clauses.
  Unsupported or ambiguous structures must remain explicit partial results.
- `xenari.translation_report.v1` exposes those explicit markers as structured
  status/confidence diagnostics for API and CLI consumers; it does not elevate
  the deterministic translator into a semantic authority.
- Reverse translation is a readable heuristic, not proof of semantic
  round-trip fidelity.
- `benchmark` records representative local lookup, search, forward, and reverse
  timings without enforcing hardware-dependent pass/fail thresholds.
- Changes to translator behavior or mappings must pass both Python parity and
  the paired site drift suite.

## Refactoring rule

Split modules by semantic responsibility, not by the numbered hardening loop in
which behavior was introduced. Do not add a compatibility shim without a known
downstream consumer and a documented removal condition.

Behavior mixins are implementation details of the explicit service components;
the public `Xenari` object no longer inherits their combined hierarchy. New code
may call a component directly (`translator`, `lexicon_service`, `curation`, or
`health`), while the facade forwards the established flat method API.
