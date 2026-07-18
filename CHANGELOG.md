# Xenari changelog

Xenari follows semantic versioning for its documented Python API, console
commands, packaged data schema, and shared translator fixtures.

## Unreleased

## 0.2.0 - 2026-07-18

- Reorganized the implementation as an installable `src/xenari` package.
- Added installed-wheel, read-only canon, lifecycle, parity, and site drift gates.
- Preserved temporal modifiers and strengthened the Xenari candidate linter.
- Split translation, database mutation, and CLI responsibilities into focused modules.
- Removed obsolete compatibility modules and historical development logs.
- Added conservative sense-level part-of-speech metadata, explicit grammar
  configuration, structured parser stages, duplicate review tooling, and
  static/fuzz quality gates.
- Made particle inference sense-specific so lexical uses such as
  `disturb -> xi` and `module -> ta` cannot inherit grammar-particle metadata.
- Replaced the six-mixin public facade with explicit lexicon, translation,
  curation, and health components while preserving the established flat API.
- Added one generated, packaged runtime-table contract shared by Python and the
  browser translator.

## 0.1.0 - 2026-07-09

- Established the SQLite canon, translator, curation CLI, generated dictionary,
  and paired browser integration.
