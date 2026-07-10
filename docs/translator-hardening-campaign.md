# Xenari Translator Hardening Campaign

Status: Loop 1 of 6 completed on 2026-07-10. This is a living audit and handoff file, not a claim that the translator is complete.

## Campaign guardrails

- `xenari.db` is canon. Lexicon mutations happen through DB-aware commands/helpers before exports.
- `data/xenari-dict.json` and the site dictionary files are generated artifacts, never hand-edited sources.
- Parser changes require focused regressions. Shared forward/reverse fixtures are the Python/browser contract.
- No loop commits, deploys, service restarts, or external syncs. Nyx reviews and publishes separately.
- Each loop should leave a bounded diff and carry unresolved examples forward explicitly.

## Loop 1 baseline

Starting revisions were Xenari `13097a3` and nyx-site `afcdf9d`; both worktrees were clean. Canon reported 9,334 roots, 11,046 English mappings, and 83 categories.

The clean baseline passed:

- `pytest -q`: 24 passed
- `python3 xenari_tool.py doctor`: status ok
- `python3 xenari_tool.py parity`: 26 forward and 14 reverse fixtures passed
- `npm run test:xenari`: translator and page contracts passed

No crashes occurred in the 30-sentence manual audit. The more serious failures were structurally plausible output made from real but wrong roots, dropped question/comparison meaning, and large Python/browser differences.

## Command and test inventory

| Area | Command or file | What it checks |
| --- | --- | --- |
| Python suite | `pytest -q` | CLI, lookup, mutation guards, translation, reverse parsing, gap harvesting, exports |
| Health gate | `python3 xenari_tool.py doctor` | audit, lookup, and known-sentence smoke checks |
| Shared contract | `python3 xenari_tool.py parity` | Python against `data/translator-fixtures.json` |
| Browser contract | `npm run test:xenari` | browser parser against shared fixtures plus translator-page checks |
| Canon size | `python3 xenari_tool.py stats` | root, English-map, and category counts |
| Canon QC | `python3 xenari_tool.py audit 20` | duplicates, stale markers, invalid roots |
| Interactive translation | `python3 xenari_tool.py translate "..."` | automatic direction selection |
| Explicit forward/reverse | `speak`, `gloss`, `reverse` | direct parser paths and readable reverse warnings |
| Script gap audit | `python3 xenari_tool.py gaps ...` | read-only word/phrase/sound/vocalization harvesting |
| Derived-data sync | `python3 xenari_tool.py sync --site` | regenerate canon and site dictionaries after DB changes |
| Site release gate | `npm run build` | Astro compilation and generated-page validation |
| Diff hygiene | `git diff --check` in both repos | whitespace and patch integrity |

## Current weak spots

1. Python and browser maintain separate verb/POS override tables and separate parsing logic. Shared fixtures cover only their safest intersection.
2. The DB export has no authoritative part-of-speech field. The browser infers POS from category/definition text, so roots such as `build`, `say`, `touch`, and `slam` can load as nouns even when the translator needs a verb sense.
3. Common English inflections in the DB can outrank the intended base concept (`said`, `seen`, `stopped`, and similar script-gap rows). Translator overrides currently protect only selected verbs.
4. The generic Python forward parser handles pronoun-first transitive clauses best. Noun subjects, imperatives, WH subjects, obliques, and multiple nouns can be assigned the wrong role without becoming unknown.
5. Clause splitting is intentionally conservative but loses some punctuation/ellipsis intent. Python infers yes/no questions from opening auxiliaries; the browser retains terminal punctuation.
6. Conditionals, relative clauses, and purpose clauses do not share one representation. Each engine can emit well-formed-looking but materially different structures.
7. Comparatives and superlatives have canon particles, but neither translator has a proven shared implementation. Loop 1 now preserves these clauses as explicit unsupported grammar instead of silently deleting the comparison.
8. Sound effects and vocalizations resolve to canon roots, but bare-fragment particles and inflected action readings differ between Python and the browser.
9. Reverse translation is a heuristic reader, not a full validator. It warns on malformed frames but cannot prove semantic round-trip fidelity.

## Python/site drift risks

- Python `verb_map` can intentionally override noisy DB lookups; browser `EXTRA_MAPPINGS` can override the generated dictionary. Updating only one changes semantics immediately.
- Python uses `zeq` for indefinite/abstract third person; the browser still contains a separate `req` plural-third-person convention. This needs a grammar-led decision, not an incidental parser edit.
- Browser dictionary collision selection and Python `_lookup_score` are not the same algorithm.
- Python returns a single rendered string. Browser results carry `wordPairs`, `partial`, `unknown`, notes, and display suffixes; parity tests currently compare only rendered text.
- The Astro page needs a cache-bust change whenever browser translator behavior changes.
- The site test reads the shared canon fixture by workspace-relative path, which is useful locally but brittle outside this paired checkout.

## Manual audit corpus and outcomes

All 30 inputs were run through `python3 xenari_tool.py translate`; the same corpus was then run through the browser parser for drift review.

| # | Input | Coverage | Loop 1 result |
| --- | --- | --- | --- |
| 1 | I'm not going to work today. | contraction, negation, future | fixed and shared-fixtured |
| 2 | She didn’t kiss him yesterday. | smart apostrophe, past negation | fixed and shared-fixtured |
| 3 | We’ve never seen the alien. | smart apostrophe, present perfect, negation | fixed by established `toq` override; still not a dedicated fixture |
| 4 | They’ll build the door tomorrow. | contraction, future | Python improved; browser verb POS and pronoun drift remain |
| 5 | Can’t you hear the alarm? | smart apostrophe, modal, negated question | fixed and shared-fixtured with canon lookup `cromq` |
| 6 | Why did the elevator stop? | WH question, past | remaining: Python defaults the subject incorrectly; browser drops the verb |
| 7 | Where will you go? | WH question, future | remaining: Python drops `where`; browser and Python disagree on question marking |
| 8 | Who broke the red window? | WH subject, past | remaining: neither engine has a safe shared WH-subject frame |
| 9 | Have you seen my hat? | present perfect, question, possession | fixed and shared-fixtured |
| 10 | If I see the alien, I will run. | conditional | remaining: both engines split/attach the condition differently |
| 11 | If the door is open, we can enter. | conditional, modal | remaining: major structure and verb-sense drift |
| 12 | I would help you if I could. | conditional fragments | remaining: trailing modal clause loses its predicate |
| 13 | The woman who built the translator loves you. | subject relative | remaining: roles and relative-clause boundaries are unsafe |
| 14 | I see the dog that bit the stranger. | object relative | remaining: Python drops the relative action; browser emits a different subordinate frame |
| 15 | The hat which is red belongs to me. | copular relative | remaining: both outputs are structurally suspect |
| 16 | I opened the door to help you. | purpose clause | remaining: Python drops purpose; browser treats it as a goal phrase |
| 17 | We went to the forest to find water. | motion plus purpose | remaining: goal/object assignment diverges |
| 18 | She built a tool for me to translate the sentence. | ditransitive purpose | remaining: both engines lose different arguments |
| 19 | The alien is taller than the human. | comparative | now an honest unsupported-grammar result in both engines |
| 20 | This tool is better than that tool. | irregular comparative | now an honest unsupported-grammar result in both engines |
| 21 | That is the fastest ship. | superlative | honest fallback added to shared fixtures |
| 22 | Bang! The door slammed. | sound effect, past action | remaining: sound root is known; `slammed` and bare-fragment rendering drift |
| 23 | Shhh, listen to the wind. | vocalization, imperative | Python stale `listen` root fixed to `grip`; imperative/fragment drift remains |
| 24 | Ugh... the elevator is broken. | vocalization, predicate | remaining: `ugh` is a real gap candidate and `broken` is not safely predicative |
| 25 | Beep beep beep. | repeated sound effect | root resolves; browser adds a bare-fragment animacy particle that Python omits |
| 26 | No, I won’t. | dialogue ellipsis, negation | remaining: missing elided predicate produces empty-looking clauses |
| 27 | Wait—what? | em dash, dialogue question | remaining: dash normalization and question-word preservation differ |
| 28 | Hey, are you there? | greeting plus question | greeting is safe; location/existential analysis drifts |
| 29 | I said, “Don’t touch that.” | quoted dialogue, smart punctuation | curly/ASCII quote normalization aligned; speech and imperative semantics remain |
| 30 | Yes? Fine. | dialogue fragments | no crash, but roots/register and bare-fragment particles drift |

Important Loop 1 fixes are captured in shared fixtures rather than adding giant exact-output blobs for the unresolved corpus. The unresolved rows above are the known-failure seed list for Loop 2.

## Loop 1 changes

- Normalized `can't`/`cannot` to `can not` in both engines so modality, negation, and question status survive tokenization.
- Made Python auxiliary handling consume `do/did`, future modals, and potential modals instead of leaking them into noun/root lookup.
- Added Python handling for auxiliary-opened yes/no questions and time-adverb skipping.
- Aligned high-confidence existing-root overrides: `hear/heard` → `cromq`, `listen` → `grip`, `seen` → `toq`.
- Extended the safe going-to-work frame to negation and a real goal phrase.
- Added explicit comparative/superlative unsupported results to prevent plausible but meaning-losing output.
- Normalized all translator-supported apostrophe variants in the gap harvester.
- Normalized curly dialogue quotes in the browser tokenizer.
- Fixed the translator page's input/output panel nesting and added a page-level regression.
- Added five shared forward fixtures plus focused Python/browser/gap tests.
- No canon word was added and `xenari.db` was not changed; therefore no generated dictionary sync was required in Loop 1.

## Next five loops

### Loop 2 — questions, noun subjects, and everyday POS parity

- [ ] Turn rows 4, 6, 7, 8, 27, and 28 into focused known-failure/contract cases.
- [ ] Align WH roots and yes/no marking without conflating WH questions with `va` questions.
- [ ] Fix noun-subject role assignment for intransitives such as “the elevator stopped”.
- [ ] Audit a small reviewed set of everyday verb POS overrides (`build`, `say`, `touch`, `slam`, `stop`).
- [ ] Decide `zeq`/`req` behavior from canon grammar and fixture it.
- [ ] Add a repeatable Python-versus-browser corpus diff command or test helper.

### Loop 3 — shared clause grammar

- [ ] Design a small common clause/frame vocabulary for condition, relative, and purpose relations.
- [ ] Fix rows 10–18 one construction family at a time.
- [ ] Preserve arguments explicitly when a subordinate clause cannot be translated.
- [ ] Add reverse fixtures for every new forward construction.

### Loop 4 — comparisons and modifier semantics

- [ ] Verify canon use of `maq`, `qruv`, `trox`, and `qren` before implementation.
- [ ] Implement regular, irregular, and superlative comparisons in both engines.
- [ ] Replace Loop 1 comparison fallbacks with exact shared fixtures only after grammar review.
- [ ] Audit adjective/noun collision behavior and modifier ordering.

### Loop 5 — dialogue, sounds, and gap tooling

- [ ] Fix ellipsis, quote boundaries, em dashes, and imperative fragments.
- [ ] Decide fragment rendering for sound effects/vocalizations and align both engines.
- [ ] Review `ugh` and other recurring everyday vocalizations DB-first; coin only reviewed gaps.
- [ ] Expand gap-tool tests for typography, repeated sounds, speaker labels, and stage directions.

### Loop 6 — fuzzing, reverse safety, and release gate

- [ ] Add deterministic generated/fuzz corpora with fixed seeds and bounded size.
- [ ] Record every new failure before fixing it.
- [ ] Stress direction detection, malformed Xenari recovery, long input, and punctuation-only input.
- [ ] Measure forward/browser drift and reverse round-trip categories, not only exact text.
- [ ] Run doctor, audit, parity, full Python/site tests, builds, stale sweeps, and final documentation review.

## Loop 1 release checklist

- [x] Inspect named canon and site files, history, and changelogs.
- [x] Run clean baseline Python/site tests and health commands.
- [x] Run 30 varied manual sentences through the CLI and browser parser.
- [x] Add focused shared fixtures and tool tests.
- [x] Apply bounded high-confidence parser, mapping, normalization, and page fixes.
- [x] Preserve unresolved cases as Loop 2 seeds.
- [x] Complete final full validation and diff/stale sweep.

Final Loop 1 gate:

- `pytest -q`: 26 passed
- `python3 xenari_tool.py doctor`: status ok
- `python3 xenari_tool.py parity`: 31 forward and 14 reverse fixtures passed
- `python3 xenari_tool.py stats`: 9,334 roots; 11,046 English mappings; 83 categories
- `npm run test:xenari`: translator and page contracts passed
- `npm run build`: 16 pages built successfully
- `git diff --check`: clean in both repositories
