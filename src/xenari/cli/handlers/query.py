"""Read-only lexicon query command handlers."""

import json
import sys

COMMANDS = frozenset(
    {"lookup", "inspect", "info", "validate", "categories", "search", "near", "relations", "pos"}
)


def handle(args, x):
    """Execute a lexicon query command."""
    if args.command == "lookup":
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
            row = x.db.lookup_root(root)
            # The historical facade normalizes its in-memory meanings to lower
            # case. Keep that public CLI behavior while avoiding the full load.
            meaning = row["meaning"].lower() if row else "unknown root"
            print(f"{root} — {meaning}")
    elif args.command == "validate":
        if not args.args:
            print("Usage: validate <root> [root...]")
            sys.exit(1)
        ok = True
        lines = []
        for root in args.args:
            issues = x.db.validate_phonotactics(root)
            if issues:
                ok = False
                lines.append(f"{root}: INVALID")
                lines.extend(f"  - {issue}" for issue in issues)
            else:
                lines.append(f"{root}: ok")
        print("\n".join(lines))
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
        for result in results:
            keys = result.get("english_keys", "") or ""
            print(
                f"  {result['root']} — {result['meaning']} [{result['category']}] "
                f"score={result.get('score', 0)} {f'({keys})' if keys else ''}"
            )
    elif args.command == "near":
        if not args.args:
            print("Usage: near <meaning/query>")
            sys.exit(1)
        results = x.db.near_meanings(" ".join(args.args), limit=args.limit)
        if not results:
            print("no near matches")
        for result in results:
            print(
                f"  {result['root']} — {result['meaning']} [{result['category']}] "
                f"score={result.get('score', 0)}"
            )
    elif args.command == "relations":
        if not args.args:
            print("Usage: relations <root>")
            sys.exit(1)
        ok, report = x.db.relations_report(args.args[0])
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "pos":
        if not args.args:
            report = x.db.part_of_speech_report()
            if args.format == "json":
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                print("Xenari sense-level part of speech")
                print(f"Annotated: {report['annotated']} / {report['total']}")
                print(f"Unknown: {report['unknown']}")
                for name, count in report["counts"].items():
                    print(f"  {name}: {count}")
            return
        try:
            rows = x.db.mappings_by_part_of_speech(args.args[0], limit=args.limit)
        except ValueError as exc:
            print(exc)
            sys.exit(1)
        if args.format == "json":
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            for row in rows:
                print(
                    f"{row['english_key']} -> {row['root']} "
                    f"[{row['part_of_speech']}]: {row['meaning']}"
                )
