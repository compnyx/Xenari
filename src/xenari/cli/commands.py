#!/usr/bin/env python3
"""Command-line interface for the Xenari tool."""

from pathlib import Path
import sys

from ..facade import Xenari
from .handlers import (
    CURATION_COMMANDS,
    MAINTENANCE_COMMANDS,
    QUERY_COMMANDS,
    TRANSLATION_COMMANDS,
    handle_curation,
    handle_maintenance,
    handle_query,
    handle_translation,
)
from .parser import build_parser


COMMAND_HANDLERS = {
    **dict.fromkeys(QUERY_COMMANDS, handle_query),
    **dict.fromkeys(TRANSLATION_COMMANDS, handle_translation),
    **dict.fromkeys(CURATION_COMMANDS, handle_curation),
    **dict.fromkeys(MAINTENANCE_COMMANDS, handle_maintenance),
}

DB_MUTATION_COMMANDS = frozenset({"add", "remove", "map", "categorize", "relate", "coin"})


def _requires_db_write(args) -> bool:
    """Return whether this invocation can actually mutate the canon DB."""
    return (
        args.command in DB_MUTATION_COMMANDS
        and args.yes
        and not args.dry_run
    )


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "help":
        parser.print_help()
        return

    try:
        x = Xenari(
            read_only=not _requires_db_write(args),
            site_root=Path(args.site_root).expanduser() if args.site_root else None,
        )
    except RuntimeError as exc:
        print(f"xenari: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    try:
        COMMAND_HANDLERS[args.command](args, x)
    finally:
        x.close()


if __name__ == "__main__":
    main()
