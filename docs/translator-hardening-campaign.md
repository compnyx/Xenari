# Xenari Translator Hardening Campaign

Status: Loop 7 completed on 2026-07-10. This is a living audit and handoff file, not a claim that the translator is complete.

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

## Loop 3 baseline

Starting revisions were Xenari `4a05b16` and nyx-site `fb55b5b`; both worktrees were clean. The supervised Loop 2 baseline passed with 27 Python tests, 43 forward fixtures, 19 reverse fixtures, a healthy doctor report, 9,334 roots / 11,051 English mappings / 83 categories, and the site translator suite reporting five drift matches plus the one approved `they` mismatch.

Rows 10–18 still produced dropped arguments, malformed relative attachment, or unrelated comma-separated clauses. Initial `when` was an honest but over-broad fallback that did not distinguish a WH question from temporal subordination.

## Loop 4 baseline

Starting revisions were Xenari `9eb9774` and nyx-site `ed5084a`; both worktrees were clean before Codex CLI began. The Loop 3 baseline still passed with 29 Python tests, 59 forward fixtures, 26 reverse fixtures, a healthy doctor report, 9,334 roots / 11,051 English mappings / 83 categories, and the site translator suite reporting twelve drift matches plus the one approved `they` mismatch.

The Codex CLI pass stalled after a partial Python-only patch, so Nyx killed only that hung loop process, reviewed the partial diff, and finished the Python/browser parity, fixture, documentation, and site-release work manually.

## Loop 5 baseline

Starting revisions were Xenari `f74143f` and nyx-site `7b75da6`; both worktrees were clean. The Loop 4 baseline passed with 30 Python tests, 79 forward fixtures, 26 reverse fixtures, a healthy doctor report, 9,334 roots / 11,051 English mappings / 83 categories, and the site translator suite reporting twelve drift matches plus the one approved `they` mismatch.

The 15-row dialogue audit had no crashes, but repeated sounds collapsed, browser fragments gained fake animacy particles, imperative punctuation triggered `va`, generic parsing invented first-person command subjects, inline stage directions merged with narration, and the gap harvester discarded inline `SPEAKER: dialogue` text.

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
5. Clause splitting now aligns reviewed quote, dash, ellipsis, and bracketed-stage seams. It still juxtaposes quoted speech rather than encoding a speech-complement relation, and arbitrary nested quotation remains unsupported.
6. Conditionals, relative clauses, temporal subordination, and purpose clauses now share bounded reviewed frames. Nested clauses, object-gap relatives, stative conditions, and omitted predicates still require explicit partial fallbacks.
7. Superlative and modifier noun phrases now have a bounded shared implementation using reviewed roots such as `qruv`, `xant`, `qrunq`, `vriq`, and `po`. Comparatives use `maq` only for the compared quality and remain readable partials because canon has no settled comparison-standard marker; stale `qren`, `trox`, and `xlu` guesses are explicitly forbidden by tests.
8. Reviewed sound effects and vocalizations now render as aligned bare lexical fragments with repetition preserved. Unreviewed forms remain explicit gaps, and arbitrary English sound-report syntax is not treated as a verb frame.
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
| 10 | If I see the alien, I will run. | conditional | fixed and shared-fixtured as `pevoq [condition] ti [main]` |
| 11 | If the door is open, we can enter. | conditional, modal | readable partial: preserves the modal main clause and marks the unsupported stative condition |
| 12 | I would help you if I could. | conditional fragments | readable partial: preserves “I would help you” and marks the missing predicate after `could` |
| 13 | The woman who built the translator loves you. | subject relative | fixed with animate subject relativizer `su zre … ti` and both matrix arguments retained |
| 14 | I see the dog that bit the stranger. | object relative | fixed: dog remains the matrix object and the animate subject-gap relative is attached to its head NP |
| 15 | The hat which is red belongs to me. | copular relative | fixed with inanimate `vro`, a bounded copular relative, and the goal argument retained |
| 16 | I opened the door to help you. | purpose clause | fixed with `frex`; purpose subject, verb, and object are retained |
| 17 | We went to the forest to find water. | motion plus purpose | fixed: forest remains the motion goal and water remains the purpose object |
| 18 | She built a tool for me to translate the sentence. | ditransitive purpose | fixed: tool remains the matrix object; “me” and sentence remain purpose subject/object |
| 19 | The alien is taller than the human. | comparative | fixed as a readable partial: quality plus `maq` is translated, while the “than …” standard is preserved in a compact warning |
| 20 | This tool is better than that tool. | irregular comparative | fixed as the same readable partial frame using `nax maq` and the demonstrative object phrase |
| 21 | That is the fastest ship. | superlative | fixed and shared-fixtured as `suhpi kag qruv` in a copular frame |
| 22 | Bang! The door slammed. | sound effect, past action | fixed and shared-fixtured as bare `tesena` plus the reviewed past intransitive `tulo` frame |
| 23 | Shhh, listen to the wind. | vocalization, imperative | fixed and shared-fixtured as bare `shava` plus a goal-marked `grip` imperative using `fa … ko xo` |
| 24 | Ugh... the elevator is broken. | vocalization, predicate | honest shared partial: `ugh` remains an explicit missing vocalization and `spokta` is retained without claiming that action `zont` means a broken state |
| 25 | Beep beep beep. | repeated sound effect | fixed and shared-fixtured as three bare `nqozo` roots with no fake animacy particle |
| 26 | No, I won’t. | dialogue ellipsis, negation | fixed as refusal `nguq` plus a compact missing-predicate partial; no empty-looking pronoun clause remains |
| 27 | Wait—what? | em dash, dialogue question | fixed and shared-fixtured as an imperative `trekq` clause plus bare `qan`; em/en dashes now form conservative clause seams |
| 28 | Hey, are you there? | greeting plus question | fixed and shared-fixtured as `prax` plus a `qroxang` copular yes/no clause ending in `va` |
| 29 | I said, “Don’t touch that.” | quoted dialogue, smart punctuation | fixed as a past `krimp` clause plus a separate negated `qabrerd` imperative; quotation relation remains conservative juxtaposition |
| 30 | Yes? Fine. | dialogue fragments | fixed and shared-fixtured with reviewed `naxq` affirmation and casual agreement `stux`, both bare |

The table is cumulative. Loop 3 promotes rows 10–18 into shared exact or readable-partial contracts without claiming support for their more complex variants.
Loop 4 promotes rows 19–21 and a broader possessive/quantity modifier corpus into shared exact or readable-partial contracts without inventing a canon “than” marker.
Loop 5 promotes rows 22–30 plus the requested imperative, quote, stage-direction, sound-report, and typographic variants into shared exact or readable-partial contracts without adding a root or DB mapping.

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

## Loop 3 findings

- Canon and the published grammar already define all four frame families needed here: conditionals use `pevoq … ti`; temporal clauses use `su cruv/prexq/vrem … ti`; relatives use role/animacy-specific relativizers inside `su … ti`; purpose uses `frex` without tense/evidential marking on the purpose predicate.
- `zre` and `vro` are relativizers, not general English `who`/`which` roots. Bounded relative clauses can use them safely, while initial interrogative `who` remains unsupported.
- Initial auxiliary-opened `when` is a WH question and has no reviewed interrogative root. Initial `when/once/after/before/while …, …` is temporal subordination and can use the canon frame. The two cases must be detected before ordinary comma splitting.
- “If the door is open” is a stative condition, not automatically the action verb “open.” Loop 3 preserves the supported modal main clause and marks the condition partial instead of substituting `xleq` unsafely.
- An English modal fragment such as “if I could” has no recoverable predicate. The translator now retains the matrix clause and states that the conditional predicate is missing.
- Canon inspection found existing reviewed roots for every needed action. Several Python translator-only overrides were stale or weaker than the direct canon entries: `help → qlemp` pointed to “make/shape,” while `pegzos` is help; `zaqa`, `xleq`, and `trek` are direct roots for run, open, and find. No root or DB mapping was added.
- Subject-gap relatives with one reviewed predicate are now bounded. Object-gap `thu`/`pla`, oblique `qlo`, stacked relatives, nested speech, and attachment ambiguity remain outside this loop.

## Loop 3 changes

- Added a shared bounded clause parser in Python and browser for complete simple conditionals, initial temporal subordination, subject-gap relatives in matrix subject/object roles, copular relatives, and explicit/implicit-subject purpose clauses.
- Replaced clause-sized dumps with compact `[partial: …]` outputs for unsupported initial `when`, stative conditions, missing conditional predicates, and nested relative structures. Relative fallback retains the known head noun; conditional/temporal fallback retains the known main clause.
- Added 16 shared forward fixtures and seven reverse fixtures. Seven forward fixtures are marked stress cases: initial WH `when`, three temporal markers, a person relative, a conditional using `semax`, and a nested relative that deliberately remains partial.
- Expanded the paired Python/browser drift corpus from six to thirteen sentences. It now reports twelve exact matches, one approved `they` ordinal mismatch, and zero unexpected differences.
- Aligned translator overrides to existing canon roots: run `zaqa`, open `xleq`, help `pegzos`, find `trek`, enter `logi`, belong `mifzxuri`, plus their reviewed inflections. General stop remains `semax`; no Loop 3 output uses stop-motion `kam`.
- Added structured reverse handling for conditional, temporal, and relative boundaries; existing purpose recovery now reads the new `frex` fixtures. Reverse output remains a readable heuristic rather than a validator.
- Added corpus-shape tests requiring at least ten Loop 3 forward fixtures, four reverse fixtures, five stress fixtures, every targeted family, no Loop 3 `[untranslated: …]` dump, and no `kam` token.
- No DB row or generated dictionary changed, so `python3 xenari_tool.py sync --site` was intentionally not run.

## Remaining loops

### Loop 2 — questions, noun subjects, and everyday POS parity

- [x] Turn rows 4, 6, 7, 8, 27, and 28 into focused known-failure/contract cases.
- [x] Align WH roots and yes/no marking without conflating WH questions with `va` questions.
- [x] Fix noun-subject role assignment for reviewed safe intransitives such as “the elevator stopped”.
- [x] Audit and align the reviewed everyday verb POS set.
- [x] Review `zeq`/`req` from canon grammar; preserve and fixture the unresolved ambiguity instead of choosing semantics without support.
- [x] Add a repeatable Python-versus-browser corpus diff command.

### Loop 3 — shared clause grammar

- [x] Design a small common clause/frame vocabulary for condition, relative, temporal, and purpose relations.
- [x] Fix or preserve rows 10–18 honestly one construction family at a time.
- [x] Preserve arguments explicitly when a subordinate clause cannot be translated.
- [x] Add reverse fixtures across every newly supported construction family.
- [x] Distinguish initial WH `when` from initial temporal subordination before ordinary clause splitting.
- [x] Keep the `who` interrogative gap and `they` ordinal ambiguity explicit unless canon is curated first.
- [x] Keep noun-subject handling inside the reviewed simple and relative frames rather than broad promotion.

### Loop 4 — comparisons and modifier semantics

- [x] Verify canon use of `maq`, `qruv`, `trox`, `qren`, and `xlu` before implementation.
- [x] Implement bounded comparative partials, superlatives, possessives, demonstratives, quantifiers, and plural noun phrases in both engines.
- [x] Replace Loop 1 comparison fallbacks with shared fixtures where grammar is reviewed; preserve comparison-standard uncertainty explicitly.
- [x] Audit adjective/noun collision behavior and modifier ordering for the reviewed Loop 4 noun-phrase set.

### Loop 5 — dialogue, sounds, and gap tooling

- [x] Fix reviewed ellipsis, quote boundaries, em dashes, bracketed stage seams, and imperative fragments.
- [x] Render reviewed sound effects/vocalizations as bare lexical roots and preserve repetition in both engines.
- [x] Review `ugh` DB-first and preserve it as a vocalization gap rather than coining or substituting a root.
- [x] Expand gap-tool tests for typography, repeated sounds, inline speaker labels, and inline stage directions.

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
- `python3 xenari_tool.py stats`: 9,334 roots; 11,051 English mappings; 83 categories
- `npm run test:xenari`: translator, six-row drift, and page contracts passed; drift report has 5 matches, 1 recorded known mismatch, 0 unexpected
- `npm run build`: 16 pages built successfully
- `git diff --check`: clean in both repositories

Remaining failures carried forward:

- Row 4 still needs a canon policy or context-aware UI for English `they`; Python `zeq` and browser `req ha` remain intentionally unchanged.
- Row 8 still lacks a canon interrogative `who` root; no root was coined in this loop.
- Initial interrogative `when` remains an explicit unsupported shared fallback; temporal `when` is a separate Loop 3 frame.
- Rows 10–18 are the Loop 3 clause-grammar corpus. Broader noun-subject syntax and dialogue rows 23, 26, 29, and 30 remain later-loop work.

## Loop 3 release checklist

- [x] Inspect both clean worktrees, recent history, campaign rows 10–18, grammar docs, translator code, fixtures, and tests before editing.
- [x] Verify every selected relation particle and action root through `inspect`, `search`, and `lookup` before parser changes.
- [x] Add at least ten forward, four reverse, and five stress fixtures; final additions were 16, seven, and seven respectively.
- [x] Align Python/browser forward and reverse behavior, retaining the single canon-driven `they` known mismatch.
- [x] Update Python tests, site tests, both site changelogs, and `translatorAssetVersion` (`20260710-hardening-loop3`).
- [x] Avoid DB/generated-data edits because the loop reused existing canon roots and mappings.
- [x] Run every requested local gate without committing, pushing, deploying, syncing externally, or restarting services.

Final Loop 3 gate:

- `pytest -q`: 29 passed
- `python3 xenari_tool.py doctor`: status ok
- `python3 xenari_tool.py parity`: 59 forward and 26 reverse fixtures passed
- `python3 xenari_tool.py stats`: 9,334 roots; 11,051 English mappings; 83 categories
- `npm run test:xenari`: translator, thirteen-row drift, and page contracts passed; drift report has 12 matches, 1 recorded known mismatch, 0 unexpected
- `npm run build`: 16 pages built successfully
- `git diff --check`: clean in both repositories

Remaining failures carried forward from Loop 3:

- Initial interrogative `when` and `who` still lack canon question roots; neither is synthesized from a subordinator/relativizer.
- Stative conditions such as “if the door is open,” missing-predicate conditions such as “if I could,” and nested/stacked/object-gap/oblique relatives remain compact readable partials.
- English `they` remains the only drift known-mismatch: Python uses `zeq`; browser uses `req ha`.
- Reverse translation reads the new boundaries but still simplifies articles, agreement, and purpose wording; it does not validate arbitrary nested Xenari.
- Comparison rows 19–21 and dialogue/sound rows 22–30 remain assigned to later loops.

## Loop 4 findings

- Canon confirms `maq` as the comparative/more particle and `qruv` as the superlative/most particle.
- `trox` is sweat, `qren` is mirror/reflector, and `xlu` is climb. They are not comparison-standard, equative, or inferior markers; Loop 4 tests assert they do not appear in comparative output.
- Canon has reviewed quantifier roots for the bounded set used here: `fqam` one, `vriq` two, `xant` many, `qrunq` all/whole, `frox` some, `klog` few, `cleg` each/every, and `nulxant` none/no.
- `nulxant` carries the “no/none” meaning directly. Loop 4 outputs such as “no water” and “no people open the door” do not add `ngu`.
- The documented noun-phrase modifier order places quantifier-style material after the head noun. The translator now renders reviewed phrase fragments such as `zrump vriq`, `pronx xant`, and `suhpi kag qruv`.
- English `their` still differs between Python and browser because of the unresolved `zeq`/`req ha` policy. Loop 4 avoids adding that as a shared exact fixture.

## Loop 4 changes

- Added a bounded Loop 4 noun-phrase parser to Python and the browser for possessives, demonstratives, reviewed qualities, reviewed superlatives, reviewed quantifiers, and simple plural nouns.
- Added simple Loop 4 clause rendering so quantifier and possessive noun phrases survive as subjects/objects inside conditionals, temporals, relatives, and purpose clauses.
- Replaced the old blanket superlative fallback for reviewed examples. “That is the fastest ship” now renders exactly, while “The alien is taller than the human” renders a partial comparative that preserves the unmodeled standard.
- Extended the Loop 3 shared-frame parser to accept Loop 4 noun phrases inside `if`, `when`, relative, and purpose frames.
- Added 20 Loop 4 forward fixtures across comparative, superlative, possessive, quantity, conditional, temporal, relative, and purpose families. Eight are marked stress cases.
- Added Python and browser tests proving Loop 4 fixtures do not leak `[untranslated: …]`, `nulxant` frames do not add `ngu`, and stale roots `qren`, `trox`, and `xlu` are not used for comparison.
- No DB row or generated dictionary changed, so `python3 xenari_tool.py sync --site` was intentionally not run.

## Loop 4 release checklist

- [x] Inspect both clean worktrees, recent history, campaign rows 19–21, grammar docs, translator code, fixtures, and tests before publishing.
- [x] Verify comparison and quantifier roots through canon search/lookup rather than trusting Codex's guessed semantics.
- [x] Review and finish the partial Codex CLI diff after the Loop 4 worker stalled.
- [x] Add shared fixtures plus focused Python/browser regressions.
- [x] Mirror Python changes in the browser translator and bump `translatorAssetVersion` (`20260710-hardening-loop4`).
- [x] Update both site changelogs.
- [x] Avoid DB/generated-data edits because the loop reused existing canon roots and mappings.

Final Loop 4 gate:

- `pytest -q`: 30 passed
- `python3 xenari_tool.py doctor`: status ok
- `python3 xenari_tool.py parity`: 79 forward and 26 reverse fixtures passed
- `python3 xenari_tool.py stats`: 9,334 roots; 11,051 English mappings; 83 categories
- `npm run test:xenari`: translator, thirteen-row drift, and page contracts passed; drift report has 12 matches, 1 recorded known mismatch, 0 unexpected
- `npm run build`: 16 pages built successfully
- `git diff --check`: clean in both repositories

Remaining failures carried forward from Loop 4:

- Canon still lacks a settled comparison-standard marker, so comparative standards are preserved as partial notes rather than encoded in Xenari grammar.
- Dialogue/sound rows 22–30 remain assigned to Loop 5.
- Initial interrogative `when`, interrogative `who`, `they` ordinal ambiguity, stative conditions, missing predicates, and nested/object-gap relatives remain unchanged from Loop 3.

## Loop 5 findings

- Canon already contains reviewed fragment roots for the requested known sounds and vocalizations: `tesena` bang, `nqozo` beep, `shava` shhh, `xeha` huh, `ux` uh, `aza` ah, `oxu` ouch, `glivun` whirr, `qelto` whoosh, and `priva` drip. Fragment rendering did not need new vocabulary.
- Canon has no `ugh` root or English mapping. Search produced only unrelated fuzzy matches, so Loop 5 keeps it as `[untranslated: ugh; no Xenari root for: ugh]` and lets the gap harvester classify it as a vocalization candidate.
- `nguq` is the reviewed refusal “no,” `naxq` the reviewed affirmation “yes,” and `stux` casual agreement “ok/fine.” Broad lookup collisions had produced a trap-weapon root, a plural-looking unrelated root, and adjectival thin/fine readings in dialogue fragments.
- The published grammar explicitly defines `ko` as imperative tense, `xo` as the default imperative evidential, and imperative negation as `ko xo ngu`. Commands do not require an invented first-person `ka neq` subject and exclamation punctuation is not yes/no `va`.
- `groz` is the existing whisper fragment/noun, while `tyequga` is the reviewed verb “makes soft whispering sounds”; the direct `whispered` mapping resolves to the noun-like `vpogrkep` hushed speech. `tulo` is the reviewed slam root while `slams` can collide with a separate inflection row. Narrow translator overrides select the established verb/action roots without changing canon mappings.
- Canon does not establish an English-style quotation/complement particle for these frames. Loop 5 treats quote openings as conservative clause seams and renders speech plus quoted content as adjacent clauses rather than inventing a relation.
- Gap harvesting had three concrete extraction flaws: an inline `SPEAKER: dialogue` line was wholly discarded, inline `[stage direction] narration` received no stage metadata, and phrase windows could cross ellipses/dashes or line boundaries. Repeated unknown onomatopoeia outside brackets also fell into the name/gap buckets.

## Loop 5 changes

- Added a bounded Loop 5 frame in both translators for reviewed bare fragments, repeated sounds, imperative wait/listen/stop/open/touch frames, missing modal predicates, stative “broken” partials, and the unsupported “alarm goes beep” relation.
- Preserved repeated roots exactly and removed browser-only fragment animacy particles. Reviewed dialogue `yes`, `no`, and `fine` now select `naxq`, `nguq`, and `stux` rather than lookup collisions.
- Normalized curly/ASCII quote openings, Unicode ellipsis, em/en dashes, and bracketed stage directions into aligned clause seams. The existing `Wait—what?` and `Hey, are you there?` contracts remain unchanged.
- Added 19 forward and one reverse Loop 5 shared fixtures across dialogue, imperative, quote, sound, sound-report, stage-direction, typography, known vocalization, and vocalization-gap families. Nine forward cases are marked stress cases.
- Expanded the paired Python/browser drift corpus from thirteen to 26 sentences. It now reports 25 exact matches, the unchanged approved `they` mismatch, and zero unexpected differences.
- Fixed the read-only gap harvester to retain inline speaker dialogue, annotate only inline stage spans, separate phrase windows at typographic punctuation/stage transitions/line boundaries, count repeated sounds, and recognize bounded repeated-consonant onomatopoeia.
- No root, English mapping, DB row, or generated dictionary changed, so dictionary sync was intentionally not run.

## Loop 5 release checklist

- [x] Inspect both clean worktrees, the Loop 4 handoff, translator code, shared fixtures, tests, grammar docs, and gap-harvester implementation before editing.
- [x] Run all 15 requested seeds through Python and the browser and verify every selected root through DB-aware `inspect`/`search` commands.
- [x] Mirror every translator behavior change in Python and browser code and cover it with shared fixtures plus focused runtime tests.
- [x] Add gap-tool regressions for repeated sounds, inline stage directions, inline/standalone speaker labels, and typographic punctuation.
- [x] Keep `ugh` as an honest vocalization gap and make no canon/generated-data edits.
- [x] Update both site changelogs and bump `translatorAssetVersion` (`20260710-hardening-loop5`).
- [x] Run and record the final full local gate after all documentation changes.

Final Loop 5 gate:

- `pytest -q`: 32 passed
- `python3 xenari_tool.py doctor`: status ok
- `python3 xenari_tool.py parity`: 96 forward and 27 reverse fixtures passed
- `python3 xenari_tool.py stats`: 9,334 roots; 11,051 English mappings; 83 categories
- `npm run test:xenari`: translator, 26-row drift, and page contracts passed; drift report has 25 matches, 1 recorded known mismatch, 0 unexpected
- `npm run build`: 16 pages built successfully
- `git diff --check`: clean in both repositories

Items carried to Loop 6:

- Keep the existing `they` Python/browser difference unchanged until grammar/canon establishes a default English ordinal reading.
- Fuzz nested/malformed quotes, unmatched brackets, speaker labels with parentheticals, punctuation-only input, and long repeated-sound runs; Loop 5 covers reviewed seams, not a general screenplay parser.
- Review additional imperative verbs one bounded argument frame at a time. Unreviewed English verb-first clauses should not be assumed to share the five Loop 5 command frames.
- Decide through canon curation whether recurring `ugh` deserves a root; do not substitute `ux`, `aza`, or another nearby vocalization automatically.
- Reverse translation still treats bare roots and imperative subjects heuristically and does not reconstruct quotation or stage-direction boundaries.
- Existing unresolved `when`/`who`, comparison-standard, stative condition, missing conditional predicate, and nested/object-gap relative issues remain in scope for the final safety/fuzz audit rather than being silently generalized here.

## Loop 6 findings

- Codex CLI was temporarily unavailable because the model usage window asked for a retry at 14:58 CEST, so the loop began with local fuzzing instead of idling.
- Punctuation-only and whitespace-only English input returned an empty translation string in both translators. This made the UI look broken instead of telling the user there was no content to translate.
- Unreviewed verb-first inputs like “Run!”, “Help me!”, and “Translate this!” were interpreted by the fallback parser as first-person statements. That was misleading because only the Loop 5 command verbs have reviewed imperative frames.
- Negated unreviewed commands like “Don’t run.” inherited yes/no question handling and could add `va` to a non-question command-shaped fragment.
- Screenplay labels with parentheticals, such as `MARA (O.S.):`, leaked into the clause text. Parenthetical and asterisk stage spans were not normalized as seams, so they could become fake objects or subjects.

## Loop 6 changes

- Added a shared no-content fallback: `[untranslated: no translatable content]`.
- Added speaker-label stripping before contraction/lowercase normalization in Python and browser code.
- Added parenthetical and asterisk stage spans to the existing bracketed stage-direction clause seams.
- Added a bounded Loop 6 safety frame that marks unreviewed subjectless commands as readable partials instead of inventing `ka neq`, while leaving the reviewed Loop 5 imperatives unchanged.
- Added shared Loop 6 fixtures for empty input, unreviewed imperatives, speaker labels, speaker plus stage directions, parenthetical stage directions, and asterisk sound spans.
- Expanded the Python/browser drift corpus from 26 to 37 sentences. It now reports 36 exact matches, the unchanged approved `they` mismatch, and zero unexpected differences.
- No root, English mapping, DB row, or generated dictionary changed, so dictionary sync was intentionally not run.

## Loop 6 release checklist

- [x] Start a Codex CLI Loop 6 attempt and record the usage-window block instead of pretending it ran.
- [x] Fuzz punctuation-only input, unreviewed commands, speaker labels, parenthetical stage directions, and asterisk sound spans locally.
- [x] Mirror every selected safety behavior in Python and browser code.
- [x] Add shared fixtures plus focused Python/browser regressions.
- [x] Leave new command verbs as honest partials until their object frames are reviewed.
- [x] Keep canon and generated dictionaries unchanged.

Final Loop 6 gate:

- `pytest -q`: 33 passed
- `python3 xenari_tool.py doctor`: status ok
- `python3 xenari_tool.py parity`: 107 forward and 27 reverse fixtures passed
- `python3 xenari_tool.py stats`: 9,334 roots; 11,051 English mappings; 83 categories
- `npm run test:xenari`: translator, 37-row drift, and page contracts passed; drift report has 36 matches, 1 recorded known mismatch, 0 unexpected
- `npm run build`: 16 pages built successfully
- `git diff --check`: clean in both repositories

## Loop 7 findings

- Local fuzzing after the Loop 6 deploy exposed another fallback-parser cluster: simple intransitives like “The door opens.” and “The alien runs quickly.” could still become fake object-first first-person clauses.
- Coordination without auxiliary verbs, such as “I run and she waits.”, was not split at the connector seam and could treat `and`/`xen` as a noun object.
- “Why run?” was a subjectless question, but the fallback parser rendered it as if the speaker were asking why they personally run.
- Python and browser disagreed on `dog` animacy for the safe intransitive path until the Python renderer accepted the reviewed subject animacy.

## Loop 7 changes

- Added bounded safe-intransitive handling for reviewed open/run/wait/stop/slam forms, including simple adverbs and reviewed `why did ...` questions.
- Added a narrow coordination seam for connector plus independent subject clauses, covering cases like “The door opens and the alien runs.” without splitting ordinary noun phrases.
- Added an honest subjectless-question partial for “Why run?”-style inputs.
- Passed reviewed subject animacy into the Python simple-frame renderer so animate nouns such as `dog` stay animate in both translators.
- Added eight Loop 7 shared fixtures and expanded the drift corpus from 37 to 45 sentences. It now reports 44 exact matches, the unchanged approved `they` mismatch, and zero unexpected differences.
- No root, English mapping, DB row, or generated dictionary changed.

Final Loop 7 gate:

- `pytest -q`: 34 passed
- `python3 xenari_tool.py parity`: 115 forward and 27 reverse fixtures passed
- `npm run test:xenari`: translator, 45-row drift, and page contracts passed; drift report has 44 matches, 1 recorded known mismatch, 0 unexpected
