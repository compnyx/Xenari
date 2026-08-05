# Xenari changelog

Xenari follows semantic versioning for its documented Python API, console
commands, packaged data schema, and shared translator fixtures.

## Unreleased

- Completed the common-English mapping review by resolving all 9,325 remaining
  untyped mappings: 8,468 received reviewed sense-level POS tags, 347 malformed
  or fragmentary mappings were replaced with whole concepts, and 510 invalid
  mappings were deleted. The atomic batch also added 341 deliberate mappings:
  two outputs required by split replacements, 133 reviewed runtime mappings,
  132 curated unique aliases for raw matching shortages, and 48 sense aliases
  required to preserve established default choices while giving every root a
  forward-owned reverse head, plus 25 aliases required by the pinned legacy POS
  selector and the narrower `living human` alias.
- The canon now contains 9,990 roots and 11,630 English mappings. Every mapping
  has an explicit part of speech, and all 9,888 mapped roots participate in the
  verified English → Xenari → English lexical reversibility contract.
- Promoted the shared Python/browser runtime contract to schema v4. Default
  lookup, POS-specific lookup, translation-role selection, and preferred
  reverse heads are now independent reviewed choices, so POS classifies a sense
  without accidentally changing canonical or grammatical priority. All 10,061
  canonical root/POS groups now also have a shared reverse-role surface; verb
  roles use reviewed lemmas or finite `be` phrases, while 853 reviewed plural
  noun/proper-noun heads make the explicit plural marker idempotent. The same
  contract now carries exact third-person and past phrases for all 2,388 verb
  roots, replacing divergent Python/browser heuristics and correcting 309 past
  forms plus three third-person forms against independently reviewed
  LemmInflect and UniMorph evidence.
- Reviewed all 1,028 structurally bijective, previously untyped mappings in
  nine legacy noun/adjective/verb category variants. Added 1,000 intentional
  sense-level annotations (516 nouns, 267 verbs, 189 adjectives, 23 adverbs,
  four numerals, and one particle) and recorded 28 exact semantic deferrals;
  this intermediate pass reduced the untyped queue from 10,325 to 9,325. The
  packaged v3 review fixture pins the selection hash, category/POS totals,
  overrides, and deferral reasons.
- Added an atomic mapping-level POS batch API with one pre-mutation backup,
  one transaction, exact row-count verification, and rollback on mismatch.
  Added 16 shared POS-specific forward preferences so POS classifies each
  canonical sense while Python and browser sentence translation deliberately
  retains the established verb root. This intermediate schema-v2 preference
  contract is superseded by the schema-v4 selection model above.
- Completed a mapping-level review of all 199 English senses in ten legacy
  POS-labelled categories. Added 140 safe sense annotations, retained 13
  established annotations, and recorded 46 exact deferrals where a bare gloss,
  homograph, or competing canonical root needed more context; this pass reduced
  the untyped queue from 10,465 to 10,325. Added 12 shared reverse-preferred
  headwords that are themselves POS-tagged and resolve back to the same root,
  keeping Python and browser reversals intentional instead of allowing
  shortest-alias drift.
- Approved 49 further unambiguous Ogden picturable nouns (`army`, `bird`,
  `boy`, `button`, `card`, `cart`, `carriage`, `cat`, `chain`, `chest`,
  `chin`, `church`, `circle`, `clock`, `coat`, `collar`, `comb`, `cord`,
  `cup`, `curtain`, `cushion`, `door`, `egg`, `engine`, `face`, `farm`,
  `feather`, `finger`, `fish`, `floor`, `fly`, `foot`, `fork`, `fowl`,
  `frame`, `garden`, `girl`, `glove`, `gun`, `hair`, `hammer`, `hand`,
  `head`, `heart`, `hook`, `house`, `knee`, `knife`, and `knot`) against
  explicit selected roots. Every approved sense is noun-tagged and has a
  forward/reverse sentence fixture; coverage is 161 approved / 689 pending.
  The paired browser translator now derives noun animacy from the same
  canonical root-meaning cues as Python.
- Approved 22 unambiguous concrete Ogden picturable nouns (`angle`, `arm`,
  `bag`, `ball`, `band`, `basin`, `bath`, `bed`, `bell`, `berry`, `blade`,
  `board`, `boat`, `bone`, `book`, `boot`, `bottle`, `box`, `brain`, `brake`,
  `branch`, and `bridge`) against explicit selected roots. Every approved
  sense is noun-tagged and has a forward/reverse sentence fixture; coverage is
  112 approved / 738 pending.
- Approved 19 unambiguous Ogden opposite-quality slots (`awake`, `bitter`,
  `blue`, `certain`, `cold`, `complete`, `cruel`, `dark`, `delicate`,
  `different`, `dirty`, `dry`, `false`, `foolish`, `green`, `last`, `late`,
  `left`, and `loud`) using only selected existing roots. Added the matching
  explicit adjective senses and sentence round-trips; coverage is 90 approved
  / 760 pending.
- Approved 18 clear Ogden quality slots (`able`, `angry`, `automatic`,
  `black`, `bright`, `brown`, `cheap`, `clean`, `clear`, `complex`, `fat`,
  `fertile`, `fixed`, `flat`, `free`, `grey`, `happy`, and `healthy`) against
  selected existing roots. Added 19 direct sense-level adjective annotations,
  including intentional US `gray` → `tre` aliasing. Each slot now has an
  exact English → Xenari → English fixture; coverage is 71 approved / 779
  pending.
- Made reviewed adjective senses drive both Python and browser quality frames
  instead of requiring a second static parser allowlist. Browser reverse
  selection now prefers an explicit POS-tagged headword over a legacy alias,
  and Python reverse restores adjective-before-noun English order. Added
  Python/browser regressions for black/gray copulas and a black-dog modifier
  phrase.
- Approved 20 concrete Ogden picturable-noun slots plus four reviewed quality
  slots (`good`, `bad`, `red`, `tall`) using only existing selected mappings.
  Added the 24 missing sense-level POS tags and full forward/reverse fixtures;
  coverage is now 53 approved / 797 pending. Existing noun animacy behavior is
  deliberately preserved rather than reclassified in this POS-only pass.
- Aligned the browser translator with canonical reviewed mappings: ordinary
  `come` now selects `cling`, direct POS-tagged nouns no longer inherit stale
  browser-only animacy guesses, `mse cruq` reverses as “much water”, and
  `vehya` has the explicit reverse headword `potato`. Added browser fixtures
  for every approved Ogden sentence so future Python/browser drift fails the
  release gate.
- Approved 19 additional Ogden Operations slots without inventing roots or
  changing grammar: `keep`, `seem`, reviewed temporal/subordinate connectors,
  content-question forms, temporal adverbs, and `please`/`yes`. Curated 12
  missing direct-map POS senses and locked every approved slot to a full
  forward/reverse fixture; coverage is now 29 approved / 821 pending.
- Added a source-pinned Ogden Basic English coverage gate: 850 source slots,
  852 accepted spelling forms, exact direct-map/POS verification, and
  sentence-level forward/reverse fixtures. The first ten high-frequency
  operation verbs are approved; the remaining 840 slots are explicitly queued
  for review, and `baseline --strict` is the eventual zero-pending gate.
- Removed legacy automatic English aliases inferred from every word in a root
  definition. New mappings now require an explicit English key, preventing
  compound-gloss fragments from silently entering the translator.
- Preserve plural subject agreement in reverse clauses and correctly render
  `has`, `have`, and `had` for possession predicates.
- Updated stale release tests to reflect the completed category and synonym
  curation instead of treating intentionally clean queues as failures.
- Corrected eight category clashes exposed by duplicate review and linked seven resulting exact-definition groups as reviewed synonyms. Fourteen remaining clashes are intentional sense distinctions and remain unlinked.
- Linked 43 reviewed exact same-category duplicate-definition groups with explicit `synonym` relations, preserving all roots, mappings, and register distinctions. Category-clash candidates remain unlinked for manual review.
- Completed the legacy Interstellar category cleanup: reviewed and categorized the remaining 64 entries across grammar, social, tools, nature, place/time, technology, qualities, and abstract domains. No roots or English mappings changed; no `Uncategorized` entries remain.
- Recategorized 47 unambiguous legacy Interstellar gap-fill entries: 40 action/motion roots plus clear social, computation, crime, and cognition entries. No roots or English mappings changed.
- Added `qrazhel` (“a mind that will not catch the thread”) and the English-to-Xenari mapping `retard` → `qrazhel`; preserve that mapping through copular reverse translation.
- Recategorized 50 reviewed legacy `Uncategorized` entries from the Interstellar gap-fill era across action, place, tool, quality, social, and nature domains; regenerated canon exports without adding vocabulary.
- Curated Wolverine screenplay harvest batch 18: finished remaining real single-token leftovers (successful, skinhead, sidesteps, shaved, raking, accelerating, voicing, toppling, submerging, trimmed, swatted) and mapped strong/shining/writing/waking/escaped/survived/swiveling/shoving onto existing roots.
- Curated Wolverine screenplay harvest hyphen batches 16-17: added real compound gaps (well-built, stainless-steel, night-vision, mini-fridge, armor-piercing, blood-soaked, t-shirt, and related forms); fixed bad collision maps on world-class/weight-bearing; stripped OCR/fragment junk roots (a-bear, checks-her, collapses-and, em-up) and bare number compounds.
- Curated Wolverine screenplay harvest batches 14-15: added the remaining clean single-token harvest gaps (~40+ roots and maps across chrome/carnage/berserker/bamboo/billboard and the final A-words), finishing the non-junk Wolverine lexical pass. Grammar particles, OCR noise, names, and hyphen-compounds intentionally left.
- Curated Wolverine screenplay harvest batch 13: added ~41 roots for remaining quality/action/social gaps (depleted, declawed, darkening, customized, cultivated, cubic, crowds, cropped, crisp, crap, cradle, covert, courtesan, coup, cornhusk, cordon, convulsions, convertible, contrary, contract, contorted, contemplating, containment, consume, congregate, confrontation, concussive, comrades, composure, completion, competitions, compare, comatose/coma, coil/coiling, coconuts, cocked, clotted, clone, clambering, circulation, circling/circled).
- Curated Wolverine screenplay harvest batch 12: added ~34 roots for remaining quality/object/action gaps (fade, eyepieces, eyeball, external, exterminators, extent, expert, experienced, exhibit, exerts, exertion, execution, evaporate, equipped, enormity, electrocuted, dungarees, dribbling/dribbles, drawl, draping, drainage, dizzy, divider(s), distinguish, distaste, dismissal, dismembered, dexterous, devoid, detectable, description, desaturated, derby).
- Curated Wolverine screenplay harvest batch 11: added ~43 roots for remaining combat/social/object gaps (hostility, hoosegow, honk, homestead, hewn, henchman, heightened, heartland, headgear, headbutt/headbutting, haze, hash, hardwood, handlebar, haloed, hairstyle, guzzles, gullet, grope, groggy, grease, grapefruits, grammar, gouges/gouged, gobble, gnashes, glisten, glimmer, gentlemen, genocide, genetic, gawkers, fugitive, frenetic, forklifts, foreman, forearms, footprints, foe, flatline, fillet, ferocity, fella).
- Curated Wolverine screenplay harvest batch 10: added ~42 roots for remaining body/object/quality gaps (observing, loveless, longneck, locate, liters, linoleum, lining, lifters, lidless, leftover, leers, leadership, latex, knob, knit(s), kneecap, kickstand, kettle, juice, jowls, jawline, jagged, jabbing, investigation/investigating, intestines, interloper, interlaced, intensity, insure/insurance, insolence, insertion, index, indestructible, indelible, imploded, imminent, hypothermia, hydrogen, hydrant, hustles).
- Curated Wolverine screenplay harvest batch 9: added ~49 roots for remaining creature/body/social/object gaps (sawdusted, pintails, pinpricks, pinching, pest, perforating, penitentiary, pelt(s), pellets, parried, parkas, panthers, optimist, operative, onslaught, onlookers, obeisance, nubile, notorious, nostrils, northward, nickname, niche(s), neutralizes, nervousness, nasal, myth, muscular, motorized, motivate, monocular, momentum, misinformed, minivan, mimic, midway, mewls/mewling, mercilessly, memo, meditative, meaty, maximum, matted, maple, mammoth, machined).
- Curated Wolverine screenplay harvest batch 8: added ~32 roots for remaining action/quality gaps (slaying, sideswipes, shirtless, shelving, shaking, serving, securing, scrutinizing, scraped, scrambled, scaled, savaged, robbed, retired, restored, requisition, replicated, rending, releasing, reholsters, reconstitute, recommend, realized, readjusts, protruding, product, preliminary, practiced, plants/plant, headfirst, underbody, sleeved).
- Curated Wolverine screenplay harvest batch 7: added ~43 roots for remaining combat/body/social gaps (snot, shards, severs/severing, seedy, seduction, seaside, scuffed, scowl, scorched, scoot, scimitars, schmuck, sausages, sardonic, salutes, ruptured, rotor, rogue, rodeo, retina, restraints, remorse, relish, regenerate/regeneration, redhead, readout, rampage, quilt, quarry, purrs, punks, punctured, pulverize, protege, prolonged, professor, primed, postcards, plaything, plasterboard, pitiless).
- Curated Wolverine screenplay harvest batch 6: added ~30 roots for remaining physical/action/quality gaps (stomp, stocky, sprawling, splotch, splinters, spill, spiderwebs, spawn, spasms, soot, snowfall, smirk, slender, slash/slashing, skillful, skewer, sideshow, sideburns, sickening, straightaway, synchronicity, synaptic, stubs, sport, somebody, sonny, uppermost, terrifies, tailslide, wads).
- Curated Wolverine screenplay harvest batch 5: added ~40 roots for remaining action/quality/creature gaps (evident, buck, batters, wordless, watery, viable, vandalism, unsheath(ing), unfastens, unclench, treetops, treason, travellers, traumatic, traumas, tramp, totters, tormentor, tolerance, tissue, tinted, throng, throes, terrorist, terminate, telepaths, telekinetic, tanned, surgical, stride, strategic, stupendous, wrinkles, wrestle, whirs, welts, watermelons, wasted, swagger, swipe, swivel).
- Curated Wolverine screenplay harvest batch 4: added 39 roots plus maps for clench, unmoving, and uncharted (gin, flannel, firelight, flutter, fetal, disoriented, devastation, convict, coconut, civilians, carnival, bookbag, biscuits, awed, amperage, amalgam, granite, grace, theater, murderers, meringues, vengeance, velocity, vertebrae, ventilation, uppercut, unmarked, unlit, unique, undersized, unblemished, tumult, tricky, vinyl, vipers, valve, vicinity, rinds, bub).
- Curated Wolverine screenplay harvest batch 3: added 29 roots plus plural/alias maps for remaining high-signal gaps (leaving, pork, lemur(s), gym, whistling, smiley, pounces, plexiglass, mug, flatbed, baobab, writhes, wired, weaponry, walnut, volts, vintage, unblinking, tribal, titanium, swollen, stasis, spruce, serrated, nowhere, manacles, liquor, inhuman, hypodermic); mapped lumberjacks, sentries, carved, and jukebox onto existing roots.
- Curated Wolverine screenplay harvest batch 2: added 28 roots covering mutant/adamantium action-and-setting vocab (beside, nothing, already, across, lumberjack, bartender, revolver, bloodied, fury, forearm, isolation, commando, clenched, bouncer, whiskey, shred, panther, gunner, thrum, pine, stainless, handkerchief, aide, carving, enhanced, factor, and related forms); mapped mutants→yuxsre and along→ludyuf.
- Fixed bad auto-maps from batch 1: removed who→bradra (sentry) and around→kruzca (halo) so grammar/content-question who and spatial around stay unpolluted.
- Curated the first Wolverine screenplay harvest batch: added roots for against, crowd, halo, feral, sentry, and aluminum; added singular/base mappings for target, toward, electric, uniform, atom, and adversary.

## 0.6.0 - 2026-07-22

- Add compositional content questions: `qan vi` for "who" and `qan qro` for "when".
- Support bounded subject-gap `who` questions and temporal questions across Python, browser, and reverse translation.
- Improve reverse question inversion and align the preferred reverse mapping for `window`.

## 0.5.0 - 2026-07-22

- Add reviewed finite causal and concessive subordination with
  `su troz ... ti ...` and `su truq ... ti ...`, accepting both initial and
  trailing English subordinate clauses.
- Preserve copular state predicates inside conditionals instead of degrading
  them to partial output.
- Preserve plural pronouns, nouns, and possessors during reverse translation.
- Keep Python, browser, shared fixtures, LLM linting, and public grammar
  references aligned on the expanded clause frames.

## 0.4.0 - 2026-07-21

- Expand the reviewed subjectless imperative grammar to run, hide, help,
  translate, and reverse-engineer commands, including objects, politeness,
  negation, and readable reverse translation.
- Keep Python, browser, shared fixtures, grammar references, and live examples
  aligned on the expanded `ko xo` command frame.

## 0.3.1 - 2026-07-21

- Add one machine-readable `check` command covering doctor, translator parity,
  generated dictionary freshness, and runtime-contract freshness.
- Raise the enforced coverage floor from 60% to 80% and test Python 3.13 in CI.
- Update official GitHub actions to their Node 24-backed major versions.

## 0.3.0 - 2026-07-21

- Recognize explicit infinitive English mappings such as `to arrive` as
  high-confidence verb senses during conservative POS curation.
- Make empty `speak` and `gloss` invocations fail with usage guidance instead
  of emitting misleading untranslated output.
- Make `info` return a nonzero status when any requested Xenari root is unknown,
  while still reporting every requested root for batch-friendly diagnostics.
- Add structured translation reports with complete/partial/unsupported status,
  explicit diagnostics, and JSON CLI output for forward and reverse workflows.
- Add bounded unknown-POS/proposal queues, duplicate candidate filters, and a
  representative local benchmark command for curator and performance work.
- Expand static typing to the public facade/components and add property checks
  for structured translation-report honesty.

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
