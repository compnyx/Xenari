#!/usr/bin/env python3
"""Command-line interface for the Xenari tool."""

import argparse
import sys
from pathlib import Path

from xenari_core import Xenari


def main():
    epilog = """Common flows:
  inspect:   stats | doctor | workbench | review --output xenari-qc.md | audit 20 | lint 20
  find:      inspect fatyih | lookup love | search dangerous | near "soft light" | relations fatyih
  translate: translate "I love you" | translate "ra mex ka neq ta zrent sa xa"
  coin:      coin glimmer "soft unsteady light" | coin glimmer "soft unsteady light" --root zakglu --yes
  curate:    categorize --root anhthu | relate ROOT_A ROOT_B --relation synonym
  mutate:    add/map/remove/categorize/relate preview by default; write only with --yes
  publish:   parity && sync --site && pytest -q
"""
    parser = argparse.ArgumentParser(
        description="Xenari Tool v4 — DB-powered, for Nyx",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    parser.add_argument("command", choices=[
        "help", "lookup", "inspect", "info", "validate", "doctor", "workbench",
        "review",
        "compound", "speak", "gloss", "translate", "reverse",
        "export-js", "export-json", "export-md",
        "export", "stats", "audit", "lint", "curate", "meta", "sync",
        "add", "remove", "search", "near", "relations", "propose-root", "coin",
        "categories", "categorize", "map", "parity", "relate",
    ])
    parser.add_argument("args", nargs="*")
    parser.add_argument("--tense", default="auto", choices=["auto", "past", "future", "habitual", "potential", "imperative"])
    parser.add_argument("--evidential", default="auto", choices=["auto", "witnessed", "inferred", "reported", "assumed", "mirative"])
    parser.add_argument(
        "--category",
        default=None,
        help="category for add/coin, or source-category filter for categorize",
    )
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
    parser.add_argument("--limit", type=int, default=20, help="result limit for search/lint/propose commands")
    parser.add_argument("--output", default=None, help="optional output path for export")
    args = parser.parse_args()

    x = Xenari()

    if args.command == "help":
        parser.print_help()
    elif args.command == "lookup":
        if not args.args:
            print("Usage: lookup <english word or phrase>")
            sys.exit(1)
        query = " ".join(args.args).strip()
        root, meaning = x.lookup(query)
        if root:
            print(f"{root} — {meaning}")
        elif len(args.args) > 1:
            found = False
            for word in args.args:
                root, meaning = x.lookup(word)
                if root:
                    found = True
                    print(f"{word}: {root} — {meaning}")
                else:
                    print(f"{word}: not found")
            if not found:
                sys.exit(1)
        else:
            print("not found")
            sys.exit(1)
    elif args.command == "inspect":
        if not args.args:
            print("Usage: inspect <english-or-root>")
            sys.exit(1)
        print(x.inspect_term(" ".join(args.args), limit=args.limit))
    elif args.command == "info":
        if not args.args:
            print("Usage: info <xenari-root>")
            sys.exit(1)
        for root in args.args:
            print(f"{root} — {x.info(root)}")
    elif args.command == "validate":
        ok, report = x.validate_roots(args.args)
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "doctor":
        ok, report = x.doctor()
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "parity":
        ok, report = x.parity()
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "workbench":
        ok, report = x.workbench(limit=args.limit)
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "review":
        ok, report = x.review_report(limit=args.limit)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(report, encoding="utf-8")
            print(f"wrote {output}")
        else:
            print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "compound":
        if not args.args:
            print("Usage: compound <word1> <word2> ...")
            sys.exit(1)
        print(x.compound(*args.args))
    elif args.command == "speak":
        sent = " ".join(args.args)
        print(x.speak(sent, args.tense, args.evidential))
    elif args.command == "gloss":
        sent = " ".join(args.args)
        print(x.gloss(sent, args.tense, args.evidential))
    elif args.command == "translate":
        sent = " ".join(args.args)
        if not sent:
            print("Usage: translate <english-or-xenari>")
            sys.exit(1)
        print(x.translate(sent, args.tense, args.evidential))
    elif args.command == "reverse":
        sent = " ".join(args.args)
        if not sent:
            print("Usage: reverse <xenari sentence>")
            sys.exit(1)
        print(x.reverse(sent))
    elif args.command == "export-js":
        print(x.export_js_dict())
    elif args.command == "export-json":
        print(x.db.export_json())
    elif args.command == "export-md":
        out = Path(args.args[0]) if args.args else Path("xenari-lexicon-export.md")
        x.db.export_markdown(out)
        print(f"Exported markdown lexicon to {out}")
    elif args.command == "export":
        if not args.args:
            print("Usage: export <json|js|md|site|repo> [output-path]")
            sys.exit(1)
        fmt = args.args[0]
        output = Path(args.output or args.args[1]) if args.output or len(args.args) > 1 else None
        try:
            print(x.export_format(fmt, output=output, include_site=args.site))
        except ValueError as exc:
            print(exc)
            sys.exit(1)
    elif args.command == "stats":
        print(x.db.stats())
    elif args.command == "meta":
        print(x.db.metadata_report())
    elif args.command == "audit":
        limit = 40
        if args.args:
            try:
                limit = int(args.args[0])
            except ValueError:
                print("Usage: audit [limit]")
                sys.exit(1)
        print(x.db.audit(limit=limit))
    elif args.command == "lint":
        limit = args.limit
        if args.args:
            try:
                limit = int(args.args[0])
            except ValueError:
                print("Usage: lint [limit]")
                sys.exit(1)
        print(x.db.lint(limit=limit))
    elif args.command == "curate":
        limit = args.limit
        if args.args:
            try:
                limit = int(args.args[0])
            except ValueError:
                print("Usage: curate [limit] [--placeholder|--phrases|--relations] [--limit N]")
                sys.exit(1)
        selected = args.placeholder or args.phrases or args.relations
        print(x.db.curation_report(
            limit=limit,
            placeholder=args.placeholder or not selected,
            phrases=args.phrases or not selected,
            relations=args.relations or not selected,
        ))
    elif args.command == "categorize":
        ok, report = x.db.categorize(
            root=args.root,
            category=args.category,
            yes=args.yes and not args.dry_run,
            all_rows=args.all,
            include_ambiguous=args.include_ambiguous,
            limit=args.limit,
        )
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "sync":
        print(x.sync_exports(include_site=args.site))
        ok, report = x.doctor()
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "categories":
        for name, count in x.db.categories():
            print(f"  {name}: {count}")
    elif args.command == "search":
        if not args.args:
            print("Usage: search <query>")
            sys.exit(1)
        results = x.db.search(" ".join(args.args), limit=args.limit)
        if not results:
            print("no results")
        for r in results:
            keys = r.get("english_keys", "") or ""
            print(f"  {r['root']} — {r['meaning']} [{r['category']}] score={r.get('score', 0)} {f'({keys})' if keys else ''}")
    elif args.command == "near":
        if not args.args:
            print("Usage: near <meaning/query>")
            sys.exit(1)
        results = x.db.near_meanings(" ".join(args.args), limit=args.limit)
        if not results:
            print("no near matches")
        for r in results:
            print(f"  {r['root']} — {r['meaning']} [{r['category']}] score={r.get('score', 0)}")
    elif args.command == "relations":
        if not args.args:
            print("Usage: relations <root>")
            sys.exit(1)
        ok, report = x.db.relations_report(args.args[0])
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "relate":
        if len(args.args) != 2 or not args.relation:
            print("Usage: relate <root-a> <root-b> --relation <type> [--notes NOTE] [--dry-run|--yes]")
            sys.exit(1)
        ok, report = x.db.relate(
            args.args[0],
            args.args[1],
            args.relation,
            notes=args.notes,
            yes=args.yes and not args.dry_run,
        )
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "propose-root":
        if not args.args:
            print("Usage: propose-root <english-key> [meaning...]")
            sys.exit(1)
        english = args.args[0]
        meaning = " ".join(args.args[1:]) if len(args.args) > 1 else english
        suggestions = x.db.propose_root(english, meaning, limit=args.limit)
        print(f"Root proposals for {english!r} — {meaning}")
        print(f"Category guess: {x.db._guess_category(english, meaning)}")
        near = x.db.near_meanings(english, limit=5)
        if near:
            print("Near existing meanings:")
            for r in near:
                print(f"  - {r['root']} — {r['meaning']} [{r['category']}] score={r.get('score', 0)}")
        print("Suggestions:")
        for item in suggestions:
            print(f"  - {item['root']} [{item['category']}] score={item.get('score', 0)}: {'; '.join(item['notes'])}")
    elif args.command == "coin":
        if not args.args:
            print("Usage: coin <english-key> [meaning...] [--root ROOT] [--dry-run|--yes]")
            sys.exit(1)
        english = args.args[0]
        meaning = " ".join(args.args[1:]) if len(args.args) > 1 else english
        ok, report = x.coin_root(
            english,
            meaning,
            root=args.root,
            category=args.category,
            limit=args.limit,
            dry_run=args.dry_run or not args.yes,
            yes=args.yes,
            include_site=args.site,
        )
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "remove":
        if not args.args:
            print("Usage: remove <root>")
            sys.exit(1)
        ok, report = x.db.describe_remove_root(args.args[0])
        print(report)
        if not ok:
            sys.exit(1)
        if args.dry_run or not args.yes:
            if not args.dry_run:
                print("Refusing to remove without --yes. Re-run with --yes after reading the preview.")
                sys.exit(1)
            sys.exit(0)
        x.db.remove_root(args.args[0])
    elif args.command == "map":
        if len(args.args) < 2:
            print("Usage: map <english-key> <root> [context note]")
            sys.exit(1)
        note = " ".join(args.args[2:]) if len(args.args) > 2 else None
        ok, report = x.db.describe_english_mapping(args.args[0], args.args[1], context_note=note)
        print(report)
        if not ok:
            sys.exit(1)
        if args.dry_run or not args.yes:
            if not args.dry_run:
                print("Refusing to map without --yes. Re-run with --yes after reading the preview.")
                sys.exit(1)
            sys.exit(0)
        x.db.add_english_mapping(args.args[0], args.args[1], context_note=note)
    elif args.command == "add":
        if len(args.args) < 2:
            print("Usage: add <english-word> <root> [meaning...]")
            print("Example: add hate blun \"to hate, detest, loathe\"")
            print("Optional: add ... --category \"Some Section (v0.8)\" ")
            sys.exit(1)
        english = args.args[0].lower().strip()
        root = args.args[1].strip()
        meaning = " ".join(args.args[2:]).strip() if len(args.args) > 2 else english
        cat = args.category or x.db._guess_category(english, meaning)
        dry_run = args.dry_run or not args.yes
        ok, msgs = x.db.add_root(english, root, meaning, category=cat, notes=args.notes, dry_run=dry_run)
        for m in msgs:
            print(m)
        if dry_run:
            if ok and not args.dry_run:
                print("Refusing to add without --yes. Re-run with --yes after reading the preview.")
                sys.exit(1)
            sys.exit(0 if ok else 1)
        if ok:
            x2 = Xenari()
            r = x2.lookup(english)
            print(f"Verified: {r[0]} — {r[1]}" if r else "WARNING: added but lookup failed (english key not auto-mapped)")


if __name__ == "__main__":
    main()
