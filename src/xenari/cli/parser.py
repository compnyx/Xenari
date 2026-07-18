"""Argument parser construction for the Xenari CLI."""

import argparse
from typing import Iterable

from .._version import __version__

COMMANDS = [
    "help", "lookup", "inspect", "info", "validate", "doctor", "workbench",
    "review", "gaps", "compound", "speak", "gloss", "translate", "reverse",
    "llm-context", "llm-lint", "export-js", "export-json", "export-runtime", "export-md",
    "export", "stats", "audit", "lint", "curate", "meta", "sync", "add",
    "remove", "search", "near", "relations", "propose-root", "coin",
    "categories", "categorize", "duplicates", "map", "parity", "relate",
    "pos", "pos-set", "pos-backfill",
]

TENSES = ("auto", "past", "future", "habitual", "potential", "imperative")
EVIDENTIALS = ("auto", "witnessed", "inferred", "reported", "assumed", "mirative")


def _add_words(parser: argparse.ArgumentParser, metavar: str = "ARG") -> None:
    parser.add_argument("args", nargs="*", metavar=metavar)


def _add_limit(parser: argparse.ArgumentParser, *, default: int = 20) -> None:
    parser.add_argument("--limit", type=int, default=default, help="maximum result count")


def _add_translation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tense", default="auto", choices=TENSES)
    parser.add_argument("--evidential", default="auto", choices=EVIDENTIALS)


def _add_confirmation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--yes", action="store_true", help="confirm the database write")
    parser.add_argument("--dry-run", action="store_true", help="preview without writing")


def _add_site_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--site", action="store_true", help="include nyx-site dictionary paths")
    parser.add_argument(
        "--site-root",
        default=None,
        help="nyx-site checkout path (default: XENARI_SITE_ROOT or ~/nyx-site)",
    )


def _add_simple_commands(
    subparsers: argparse._SubParsersAction,
    commands: Iterable[tuple[str, str]],
) -> None:
    for name, help_text in commands:
        subparsers.add_parser(name, help=help_text)


def build_parser() -> argparse.ArgumentParser:
    epilog = """Common flows:
  inspect:   stats | doctor | workbench | review --output xenari-qc.md | audit 20 | lint 20
  harvest:   gaps script.txt other-script.md --output xenari-gap-harvest.md
  find:      inspect fatyih | lookup love | search dangerous | near "soft light" | relations fatyih
  translate: translate "I love you" | translate "ra mex ka neq ta zrent sa xa"
  llm:       llm-context "messy source" | llm-lint "ra mex ka neq ta zrent sa xa"
  coin:      coin glimmer "soft unsteady light" | coin glimmer "soft unsteady light" --root zakglu --yes
  curate:    categorize --root anhthu | relate ROOT_A ROOT_B --relation synonym
  mutate:    add/map/remove/categorize/relate preview by default; write only with --yes
  publish:   parity && sync --site && pytest -q
"""
    parser = argparse.ArgumentParser(
        description="Xenari — DB-powered conlang tooling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    subparsers.add_parser("help", help="show the complete command overview")

    lookup = subparsers.add_parser("lookup", help="look up an English word or phrase")
    _add_words(lookup, "WORD")

    inspect = subparsers.add_parser("inspect", help="inspect a root or English term")
    _add_words(inspect, "TERM")
    _add_limit(inspect)

    info = subparsers.add_parser("info", help="show meanings for Xenari roots")
    _add_words(info, "ROOT")

    validate = subparsers.add_parser("validate", help="validate Xenari root forms")
    _add_words(validate, "ROOT")

    _add_simple_commands(
        subparsers,
        (
            ("doctor", "run canon and translator health checks"),
            ("parity", "verify shared forward/reverse translation fixtures"),
            ("export-js", "print the browser dictionary as JavaScript"),
            ("stats", "show canonical database counts"),
            ("meta", "show database metadata"),
            ("categories", "list categories and root counts"),
        ),
    )

    workbench = subparsers.add_parser("workbench", help="show a compact maintenance snapshot")
    _add_limit(workbench, default=20)

    review = subparsers.add_parser("review", help="build a read-only QC report")
    _add_limit(review)
    review.add_argument("--output", default=None, help="optional report output path")

    gaps = subparsers.add_parser("gaps", help="harvest lexicon gaps from scripts")
    _add_words(gaps, "SCRIPT")
    _add_limit(gaps)
    gaps.add_argument("--output", default=None, help="optional report output path")
    gaps.add_argument("--format", choices=("markdown", "json"), default="markdown")
    gaps.add_argument("--phrase-min-count", type=int, default=2)
    gaps.add_argument("--max-phrase-words", type=int, default=5)

    compound = subparsers.add_parser("compound", help="build a right-headed compound")
    _add_words(compound, "WORD")

    translation_help = {
        "speak": "translate English to Xenari",
        "gloss": "show a structured Xenari gloss",
        "translate": "auto-detect and translate in either direction",
        "llm-context": "build a canon context packet for an LLM",
    }
    for name, help_text in translation_help.items():
        command = subparsers.add_parser(name, help=help_text)
        _add_words(command, "TEXT")
        _add_translation_options(command)

    for name, help_text in {
        "reverse": "translate Xenari to English",
        "llm-lint": "validate a model-proposed Xenari candidate",
    }.items():
        command = subparsers.add_parser(name, help=help_text)
        _add_words(command, "TEXT")

    export_json = subparsers.add_parser("export-json", help="print or verify the canonical JSON export")
    export_json.add_argument("--check", action="store_true", help="verify the generated repository export")

    export_runtime = subparsers.add_parser(
        "export-runtime",
        help="print or verify the shared Python/browser runtime contract",
    )
    export_runtime.add_argument(
        "--check",
        action="store_true",
        help="verify the checkout or packaged runtime contract",
    )
    export_runtime.add_argument("--output", default=None, help="optional output path")

    export_md = subparsers.add_parser("export-md", help="write a Markdown lexicon export")
    _add_words(export_md, "OUTPUT")

    export = subparsers.add_parser("export", help="use the unified export surface")
    _add_words(export, "FORMAT_OR_OUTPUT")
    export.add_argument("--output", default=None, help="optional output path")
    _add_site_options(export)

    audit = subparsers.add_parser("audit", help="audit canonical lexicon quality")
    _add_words(audit, "LIMIT")

    lint = subparsers.add_parser("lint", help="show lexicon lint findings")
    _add_words(lint, "LIMIT")
    _add_limit(lint)

    curate = subparsers.add_parser("curate", help="show curation queues")
    _add_words(curate, "LIMIT")
    _add_limit(curate)
    curate.add_argument("--placeholder", action="store_true")
    curate.add_argument("--phrases", action="store_true")
    curate.add_argument("--relations", action="store_true")

    duplicates = subparsers.add_parser(
        "duplicates",
        help="review duplicate-headword relation candidates without merging",
    )
    _add_limit(duplicates)
    duplicates.add_argument("--format", choices=("markdown", "json"), default="markdown")

    sync = subparsers.add_parser("sync", help="refresh generated dictionary exports")
    _add_site_options(sync)

    add = subparsers.add_parser("add", help="add a root and English mapping")
    _add_words(add, "VALUE")
    add.add_argument("--category", default=None)
    add.add_argument("--notes", default=None)
    add.add_argument("--part-of-speech", default=None)
    _add_confirmation_options(add)

    remove = subparsers.add_parser("remove", help="remove a root after preview")
    _add_words(remove, "ROOT")
    _add_confirmation_options(remove)

    search = subparsers.add_parser("search", help="search roots, meanings, and mappings")
    _add_words(search, "QUERY")
    _add_limit(search)

    near = subparsers.add_parser("near", help="find nearby meanings")
    _add_words(near, "QUERY")
    _add_limit(near)

    relations = subparsers.add_parser("relations", help="show semantic relations for a root")
    _add_words(relations, "ROOT")

    propose = subparsers.add_parser("propose-root", help="propose unused root forms")
    _add_words(propose, "VALUE")
    _add_limit(propose)

    coin = subparsers.add_parser("coin", help="preview or write a coined root")
    _add_words(coin, "VALUE")
    _add_limit(coin)
    coin.add_argument("--root", default=None)
    coin.add_argument("--category", default=None)
    _add_confirmation_options(coin)
    _add_site_options(coin)

    categorize = subparsers.add_parser("categorize", help="preview or write category proposals")
    categorize.add_argument("--root", default=None)
    categorize.add_argument("--category", default=None)
    categorize.add_argument("--all", action="store_true")
    categorize.add_argument("--include-ambiguous", action="store_true")
    _add_limit(categorize)
    _add_confirmation_options(categorize)

    mapping = subparsers.add_parser("map", help="add an English mapping")
    _add_words(mapping, "VALUE")
    mapping.add_argument("--part-of-speech", default=None)
    _add_confirmation_options(mapping)

    relate = subparsers.add_parser("relate", help="preview or write a semantic relation")
    _add_words(relate, "ROOT")
    relate.add_argument("--relation", default=None)
    relate.add_argument("--notes", default=None)
    _add_confirmation_options(relate)

    pos = subparsers.add_parser("pos", help="report or query sense-level part of speech")
    _add_words(pos, "PART_OF_SPEECH")
    _add_limit(pos)
    pos.add_argument("--format", choices=("text", "json"), default="text")

    pos_set = subparsers.add_parser(
        "pos-set", help="curate POS for one English-key/root sense"
    )
    _add_words(pos_set, "ENGLISH_ROOT_POS")
    _add_confirmation_options(pos_set)

    pos_backfill = subparsers.add_parser(
        "pos-backfill", help="preview or apply conservative sense-level POS proposals"
    )
    _add_confirmation_options(pos_backfill)

    return parser
