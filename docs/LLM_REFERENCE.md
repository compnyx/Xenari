# Xenari LLM Reference

Use this file for grammar and common behavior. Use `../xenari.db` or
`../data/xenari-dict.json` for full vocabulary.

## Core Shape

Xenari is OSV by default:

```text
ra OBJECT ka SUBJECT ta VERB TENSE EVIDENTIAL
```

Example:

```text
ra mex ka neq ta zrent sa xa
I love you. / I directly witnessed that I love you.
```

Pronoun case is inferred by clause role when translating back to English:

```text
ra neq ka mex ta zrent sa xa
You love me.
```

Core particles:

- `ra` object or predicate marker
- `ka` subject marker
- `ta` verb marker
- `na` location marker
- `fa` goal/direction marker
- `mo` instrument marker
- `po` possession marker
- `vi` animate marker
- `nu` inanimate marker

## Pronouns

Pronouns already carry their own animacy. Do not add `vi` or `nu` before them.
When a pronoun is the subject, do not repeat animacy on the verb.

- `neq` = first person, I/me; add `ha` for we/us
- `mex` = second person, you
- `leq` = 3rd ordinal, present other: he/she/it/him/her by context
- `req` = 4th ordinal, absent known other: plural they/them/their/theirs defaults to `req ha`
- `seq` = 5th ordinal, unknown/foreign other
- `zeq` = 6th ordinal, singular indefinite/abstract other

English does not mark Xenari ordinal context. The translator's default for bare
English `they`, `them`, `their`, and `theirs` is the ordinary plural reading:
`req ha`. Do not silently choose singular/indefinite `zeq`; use it only when
that reading is explicit in the source context.

Correct:

```text
ra mex ka neq ta zrent sa xa
I love you.
```

Do not place animacy particles before pronouns, and do not add verb animacy
agreement when the subject is a pronoun.

## Numbers And Math

Xenari counts in base 6.

Digit roots:

- `nul` = 0
- `ca` = 1
- `vriq` = 2
- `prit` = 3
- `qang` = 4
- `cum` = 5

`fqam` is the one/single quantifier, not the numeral digit. Use `ca` for the
number 1 in math and positional base-6 forms.

Use `xang` as the productive base-6 place/group morpheme. A nonzero digit
followed by one `xang` marks sixes, two `xang` roots marks six-squared, and so
on. Omit zero digits.

```text
ca xang
6 / base-6 10

ca xang ca
7 / base-6 11

vriq xang
12 / base-6 20

cum xang cum
35 / base-6 55

ca xang xang
36 / base-6 100
```

Legacy roots for 7-12 remain dictionary aliases only: `zif`, `pev`, `besmun`,
`vipezuz`, `vnub`, and `cveqsrin`. Prefer productive base-6 composition in new
text.

Math particles:

- `plomt` = plus / add
- `krut` = minus / subtract
- `vrot` = times / grouped by / multiply
- `flopq` = divided by / split
- `zlem` = equals / same as
- `grak` = greater than / more than
- `vlox` = less than / fewer than
- `nok` = fraction / ratio / part of

Math expressions are written as number, operator, number:

```text
vriq plomt prit
2 plus 3

ca xang flopq vriq
6 divided by 2
```

## Animacy

Animacy marks current agency/state, not permanent essence.

- `vi` = animate, agentive, active, alive, running, or person-like in context
- `nu` = inanimate, inert, passive, object-like, stored, or inactive in context

Examples:

```text
ka vi qex
the alien / an animate alien

ka nu vlaq
the file / an inert stored file
```

## Tense And Evidentiality

Finite verbs take tense, then evidential.

Tense:

- `sa` present
- `lo` past
- `ve` future
- `du` habitual
- `pe` potential
- `ko` imperative

Evidential:

- `xa` witnessed/direct
- `xe` inferred
- `xi` reported/hearsay
- `xo` assumed/default narration
- `zu` surprising/mirative

Example:

```text
ra vi qex ka neq ta toq sa xa
I see the alien.
```

Gratitude can take a causal clause with `troz`:

```text
gral troz ra zra ka mex ta pyoquqab lo xo
thanks for solving that. / literally: thanks because you solved that.
```

## Copula / Predicate Clauses

Predicates use `ra` like objects.

```text
ra fatyih ka vi qex ta zux vi sa xo
The alien is dangerous.
```

## Possession

Use `po` between possessed thing and possessor.

```text
ra vi loco po brid ka vi cuq ta qruq vi sa xo
The wind blows the figure's hat away.
```

Pronoun possessors render as English possessive pronouns:

```text
ra neq po brid ka vi cuq ta qruq vi sa xo
The wind blows my hat away.
```

## Connectors And Clause Particles

- `kex` = but / contrastive
- `xen` = and
- `noq` = or
- `truq` = concessive, even though / despite
- `su` ... `ti` = subordinate clause frame

## Translation Guidance

- Prefer the DB/tool for vocabulary lookup.
- Keep grammar particles exact.
- Do not invent roots when the DB lacks a word. Mark unknowns clearly.
- Treat an LLM as the semantic translator/interpreter, not the DB tool.
- Treat the DB tool as a canon linter: it can reject fake roots, unknown
  particles, and malformed clause frames, but it is not the final judge of
  intended meaning.
- If the LLM and deterministic translator disagree, surface the disagreement
  instead of trusting the deterministic parser blindly.
- For narrative prose, `xo` is a reasonable default evidential unless the speaker
  directly witnesses the event.
- For direct personal statements, use `xa` when the speaker is reporting direct
  experience.

## LLM Sidecar Contract

Use `python3 xenari_tool.py llm-context <text>` to build a compact prompt packet
for an LLM sidecar. The packet includes direction, lexicon/token hints, core
grammar constraints, and the deterministic tool's current output as a reference
only.

An LLM translation candidate should return:

- `candidate_translation`: proposed English or Xenari output
- `literal_gloss`: literal structure, especially for Xenari
- `roots_used`: roots and DB meanings the candidate depends on
- `grammar_frame`: brief particle/clause parse
- `confidence`: low, medium, or high
- `unsupported_bits`: guessed, missing, or non-canon pieces

Use `python3 xenari_tool.py llm-lint <xenari>` on proposed Xenari. Passing lint
means only that the candidate uses known roots/particles and a plausible hard
frame. It does not prove that the sentence means the English source.

## Full Lexicon

Full vocabulary lives outside this reference:

- SQLite: `../xenari.db`
- JSON: `../data/xenari-dict.json`
- CLI search: `python3 ../xenari_tool.py search <query>`
- CLI reverse check: `python3 ../xenari_tool.py reverse <xenari sentence>`
- New root planning: `python3 ../xenari_tool.py coin <english> <meaning>`
- Category curation: `python3 ../xenari_tool.py curate --placeholder --limit 20`
- Definition curation: `python3 ../xenari_tool.py curate --phrases --limit 20`
- Relation curation: `python3 ../xenari_tool.py curate --relations --limit 20`
- Category cleanup preview: `python3 ../xenari_tool.py categorize --root <root>`
- Relation lookup: `python3 ../xenari_tool.py relations <root>`

`curate` output is heuristic. Category confidence/reasons and relation labels
are review signals, not canon facts. `categorize` and `relate` do not write by
default; inspect the affected roots and use `--yes` only for a curator-approved
change. Category-wide or all-row cleanup requires explicit targeting, and
ambiguous category proposals require `--include-ambiguous`.
