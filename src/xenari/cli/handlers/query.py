"""Read-only lexicon query command handlers."""

import sys


COMMANDS = frozenset({"lookup", "inspect", "info", "validate", "categories", "search", "near", "relations"})


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
            print(f"{root} — {x.info(root)}")
    elif args.command == "validate":
        ok, report = x.validate_roots(args.args)
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
