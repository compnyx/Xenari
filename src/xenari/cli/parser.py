"""Argument parser construction for the Xenari CLI."""

import argparse


COMMANDS = [
    "help", "lookup", "inspect", "info", "validate", "doctor", "workbench",
    "review", "gaps", "compound", "speak", "gloss", "translate", "reverse",
    "llm-context", "llm-lint", "export-js", "export-json", "export-md",
    "export", "stats", "audit", "lint", "curate", "meta", "sync", "add",
    "remove", "search", "near", "relations", "propose-root", "coin",
    "categories", "categorize", "map", "parity", "relate",
]


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
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("args", nargs="*")
    parser.add_argument("--tense", default="auto", choices=["auto", "past", "future", "habitual", "potential", "imperative"])
    parser.add_argument("--evidential", default="auto", choices=["auto", "witnessed", "inferred", "reported", "assumed", "mirative"])
    parser.add_argument("--category", default=None, help="category for add/coin, or source-category filter for categorize")
    parser.add_argument("--notes", default=None)
    parser.add_argument("--root", default=None, help="selected root for coin or categorize workflow")
    parser.add_argument("--placeholder", action="store_true", help="show only placeholder category curation")
    parser.add_argument("--phrases", action="store_true", help="show only phrase-like definition curation")
    parser.add_argument("--relations", action="store_true", help="show only relation candidate curation")
    parser.add_argument("--relation", default=None, help="curator-selected semantic relation type")
    parser.add_argument("--all", action="store_true", help="explicitly target every matching curation row")
    parser.add_argument("--include-ambiguous", action="store_true", help="allow ambiguous category proposals")
    parser.add_argument("--yes", action="store_true", help="confirm mutating DB operations")
    parser.add_argument("--dry-run", action="store_true", help="preview a mutating operation without writing")
    parser.add_argument("--site", action="store_true", help="sync exports into nyx-site dictionary paths too")
    parser.add_argument("--site-root", default=None, help="nyx-site checkout path (default: XENARI_SITE_ROOT or ~/nyx-site)")
    parser.add_argument("--limit", type=int, default=20, help="result limit for search/lint/propose commands")
    parser.add_argument("--output", default=None, help="optional output path for export")
    parser.add_argument("--check", action="store_true", help="validate generated export output without writing")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="output format for gaps")
    parser.add_argument("--phrase-min-count", type=int, default=2, help="minimum repeated count for phrase gap candidates")
    parser.add_argument("--max-phrase-words", type=int, default=5, help="maximum words per phrase gap candidate")
    return parser
