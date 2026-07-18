"""Maintenance, reporting, and export command handlers."""

import json
import sys
from pathlib import Path

from ...paths import generated_dictionary_path
from ...services.gap import GapHarvester


COMMANDS = frozenset(
    {
        "doctor",
        "parity",
        "workbench",
        "review",
        "gaps",
        "export-js",
        "export-json",
        "export-md",
        "export",
        "stats",
        "meta",
        "audit",
        "lint",
        "sync",
    }
)


def handle(args, x):
    """Execute a maintenance, reporting, or export command."""
    if args.command == "doctor":
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
    elif args.command == "gaps":
        if not args.args:
            print("Usage: gaps <script-file> [more-script-files...] [--output report.md] [--format markdown|json]")
            sys.exit(1)
        paths = [Path(value) for value in args.args]
        missing = [str(path) for path in paths if not path.exists()]
        if missing:
            print("missing input file(s): " + ", ".join(missing))
            sys.exit(1)
        harvester = GapHarvester(x)
        report = harvester.harvest_paths(
            paths,
            phrase_min_count=max(args.phrase_min_count, 1),
            max_phrase_words=max(args.max_phrase_words, 2),
        )
        rendered = (
            harvester.render_json(report)
            if args.format == "json"
            else harvester.render_markdown(report, limit=args.limit)
        )
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
            print(f"wrote {output}")
        else:
            print(rendered, end="")
    elif args.command == "export-js":
        print(x.export_js_dict())
    elif args.command == "export-json":
        exported = x.db.export_json()
        if args.check:
            try:
                parsed = json.loads(exported)
                checked = generated_dictionary_path().read_text(encoding="utf-8")
                if json.loads(checked) != parsed:
                    raise ValueError("data/xenari-dict.json is out of date")
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                print(f"export-json: failed: {exc}")
                sys.exit(1)
            print("export-json: ok")
        else:
            print(exported)
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
        except (RuntimeError, ValueError) as exc:
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
    elif args.command == "sync":
        try:
            print(x.sync_exports(include_site=args.site))
        except RuntimeError as exc:
            print(f"sync: failed: {exc}")
            sys.exit(1)
        ok, report = x.doctor()
        print(report)
        if not ok:
            sys.exit(1)
