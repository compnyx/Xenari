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

- `neq` = first person, I/me/we/us by context
- `mex` = second person, you
- `zeq` = third person, they/them by context

Correct:

```text
ra mex ka neq ta zrent sa xa
I love you.
```

Do not place animacy particles before pronouns, and do not add verb animacy
agreement when the subject is a pronoun.

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

## Translation Guidance

- Prefer the DB/tool for vocabulary lookup.
- Keep grammar particles exact.
- Do not invent roots when the DB lacks a word. Mark unknowns clearly.
- For narrative prose, `xo` is a reasonable default evidential unless the speaker
  directly witnesses the event.
- For direct personal statements, use `xa` when the speaker is reporting direct
  experience.

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
