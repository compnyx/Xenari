# Xenari Translator Hardening Campaign

Status: Loop 2 of 6 completed on 2026-07-10. This is a living audit and handoff file, not a claim that the translator is complete.

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

## Loop 2 baseline

Starting revisions were Xenari `1dee384` and nyx-site `4c22cfc`; both worktrees were clean. The Loop 1 baseline still passed with 26 Python tests, 31 forward fixtures, 14 reverse fixtures, a healthy doctor report, and passing site translator/page contracts.

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

| # | Input | Coverage | Current result |
| --- | --- | --- | --- |
| 1 | I'm not going to work today. | contraction, negation, future | fixed and shared-fixtured |
| 2 | She didn’t kiss him yesterday. | smart apostrophe, past negation | fixed and shared-fixtured |
| 3 | We’ve never seen the alien. | smart apostrophe, present perfect, negation | fixed by established `toq` override; still not a dedicated fixture |
| 4 | They’ll build the door tomorrow. | contraction, future | `build` is now a verb in both engines; exact `zeq` versus `req ha` output remains a recorded known mismatch because English does not encode the canon presence/knownness distinction |
| 5 | Can’t you hear the alarm? | smart apostrophe, modal, negated question | fixed and shared-fixtured with canon lookup `cromq` |
| 6 | Why did the elevator stop? | WH question, past | fixed and shared-fixtured as bare `voq` plus an elevator subject and past `semax`, without yes/no `va` |
| 7 | Where will you go? | WH question, future | fixed and shared-fixtured as bare `qur`; both engines preserve future `qeng` without `va` |
| 8 | Who broke the red window? | WH subject, past | shared honest fallback: canon has no interrogative `who` root, so neither engine invents or drops it |
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
| 27 | Wait—what? | em dash, dialogue question | fixed and shared-fixtured as an imperative `trekq` clause plus bare `qan`; em/en dashes now form conservative clause seams |
| 28 | Hey, are you there? | greeting plus question | fixed and shared-fixtured as `prax` plus a `qroxang` copular yes/no clause ending in `va` |
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

## Loop 2 findings

- Canon and the site grammar agree that `va` is only the clause-final yes/no marker. Content interrogatives are bare roots: `qan` what/which, `qur` where, `cil` how, and `voq` why.
- Canon does not contain an interrogative `who`. The numerous English `who...` sound/vocalization mappings are not grammar roots, so row 8 must remain explicit unsupported grammar until a curator decides whether the language needs one.
- Canon has reviewed roots for every everyday action in scope. Browser failures came from POS inference and collision selection, not missing vocabulary: `mrob` build, `krimp` say, `qabrerd` touch, `tulo` slam, `semax` stop/cease, and `zont` break.
- `trekq` is the canon “to wait” root. The old Python `wait` → `kam` shortcut conflated waiting with stop-motion and was corrected for row 27.
- `kam` means stop-motion and must not be reused for the general verb “stop”; general stop/cease/halt frames now use `semax`.
- The pronoun sources do not justify one automatic English `they` reading. Canon distinguishes `leq` present other, `req` absent known, and `zeq` indefinite; standalone English also leaves number ambiguous. Python still chooses `zeq`, while the browser chooses `req ha`. This exact difference is now tested and reported rather than hidden.
- Safe noun-subject correction can be bounded to the reviewed intransitive `stop/slam` frame. No general English transitivity parser was introduced.

## Loop 2 changes

- Added twelve shared forward fixtures and five reverse fixtures for Loop 2 questions, noun subjects, everyday verbs, and past rendering.
- Separated supported WH roots from the yes/no flag in Python; browser metadata/tests now prove WH clauses omit `va` while established yes/no clauses retain it.
- Preserved unsupported `who` and `when` grammar as readable fallbacks instead of dropping the interrogative meaning.
- Added narrow Python noun-subject handling for `stop/stopped` and `slam/slammed`; browser POS overrides now let its existing subject walk parse the same frames.
- Aligned reviewed Python/browser overrides for build/built, say/said, touch/touched, slam/slammed, stop/stopped, and break/broke/broken. Reverse past glosses now cover built, said, broke, slammed, and stopped.
- Added explicit `semax` English mappings for stop/stops/stopped/stopping/halt/halted so lookup and translator logic prefer the general stop/cease verb over noisy auto-mapped feeding and stopped-clock rows.
- Normalized em/en dashes into conservative clause seams and aligned `Wait—what?` plus `Hey, are you there?`.
- Added `npm run test:xenari:drift`, a deterministic six-row Python-versus-browser corpus report. It fails on new or changed drift and reports the one exact approved known mismatch.
- No new canon root was added, but `xenari.db` mapping rows changed for `semax`; DB-derived dictionary exports were regenerated for the repo and site.

## Remaining loops

### Loop 2 — questions, noun subjects, and everyday POS parity

- [x] Turn rows 4, 6, 7, 8, 27, and 28 into focused known-failure/contract cases.
- [x] Align WH roots and yes/no marking without conflating WH questions with `va` questions.
- [x] Fix noun-subject role assignment for reviewed safe intransitives such as “the elevator stopped”.
- [x] Audit and align the reviewed everyday verb POS set.
- [x] Review `zeq`/`req` from canon grammar; preserve and fixture the unresolved ambiguity instead of choosing semantics without support.
- [x] Add a repeatable Python-versus-browser corpus diff command.

### Loop 3 — shared clause grammar

- [ ] Design a small common clause/frame vocabulary for condition, relative, and purpose relations.
- [ ] Fix rows 10–18 one construction family at a time.
- [ ] Preserve arguments explicitly when a subordinate clause cannot be translated.
- [ ] Add reverse fixtures for every new forward construction.
- [ ] Decide how initial `when` is distinguished from temporal subordination before replacing the Loop 2 readable fallback.
- [ ] Keep the `who` interrogative gap and `they` ordinal ambiguity explicit unless canon is curated first.
- [ ] Do not broaden noun-subject promotion until verb valency or another reviewed safe frame justifies it.

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
- `python3 xenari_tool.py stats`: 9,334 roots; 11,051 English mappings; 83 categories
- `npm run test:xenari`: translator and page contracts passed
- `npm run build`: 16 pages built successfully
- `git diff --check`: clean in both repositories

## Loop 2 release checklist

- [x] Inspect both repository histories/worktrees and rerun the clean Loop 1 baseline.
- [x] Review Python and browser translator implementations before patching.
- [x] Verify content-question, pronoun, and everyday-verb behavior against canon DB/docs/code.
- [x] Add shared fixtures plus focused Python/browser regressions.
- [x] Add the repeatable paired drift report and preserve its one semantic ambiguity explicitly.
- [x] Mirror browser changes in the site changelogs and translator asset version.
- [x] Run all requested final gates without committing, pushing, deploying, syncing externally, or restarting services.

Final Loop 2 gate:

- `pytest -q`: 27 passed
- `python3 xenari_tool.py doctor`: status ok
- `python3 xenari_tool.py parity`: 43 forward and 19 reverse fixtures passed
- `python3 xenari_tool.py stats`: 9,334 roots; 11,046 English mappings; 83 categories
- `npm run test:xenari`: translator, six-row drift, and page contracts passed; drift report has 5 matches, 1 recorded known mismatch, 0 unexpected
- `npm run build`: 16 pages built successfully
- `git diff --check`: clean in both repositories

Remaining failures carried forward:

- Row 4 still needs a canon policy or context-aware UI for English `they`; Python `zeq` and browser `req ha` remain intentionally unchanged.
- Row 8 still lacks a canon interrogative `who` root; no root was coined in this loop.
- Initial `when` is an explicit unsupported shared fallback until Loop 3 distinguishes WH and temporal frames.
- Rows 10–18 remain the Loop 3 clause-grammar corpus. Broader noun-subject syntax and dialogue rows 23, 26, 29, and 30 remain later-loop work.
