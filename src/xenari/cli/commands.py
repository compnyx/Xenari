#!/usr/bin/env python3
"""Command-line interface for the Xenari tool."""

import sys
from pathlib import Path

from ..db import XenariDB
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

DB_MUTATION_COMMANDS = frozenset(
    {"add", "remove", "map", "categorize", "relate", "coin", "pos-set", "pos-backfill"}
)

# These commands use only the canonical sqlite API.  Keeping them off the full
# facade avoids building the 9k-entry in-memory translation indexes for simple
# database queries, reports, previews, and mutations.
DB_ONLY_COMMANDS = frozenset(
    {
        "info",
        "validate",
        "categories",
        "search",
        "near",
        "relations",
        "export-json",
        "export-runtime",
        "export-md",
        "stats",
        "meta",
        "audit",
        "lint",
        "curate",
        "duplicates",
        "categorize",
        "relate",
        "propose-root",
        "remove",
        "map",
        "add",
        "pos",
        "pos-set",
        "pos-backfill",
    }
)
DB_ONLY_EXPORT_FORMATS = frozenset({"json", "dict", "md", "markdown"})


class DatabaseRuntime:
    """Minimal handler context for commands that need only sqlite canon data."""

    def __init__(self, *, read_only: bool):
        self.db = XenariDB(read_only=read_only)

    def close(self) -> None:
        self.db.close()


def _requires_db_write(args) -> bool:
    """Return whether this invocation can actually mutate the canon DB."""
    return (
        args.command in DB_MUTATION_COMMANDS
        and args.yes
        and not args.dry_run
    )


def _uses_database_runtime(args) -> bool:
    """Return whether an invocation is fully served by :class:`XenariDB`."""
    if args.command in DB_ONLY_COMMANDS:
        return True
    return (
        args.command == "export"
        and bool(args.args)
        and args.args[0].lower().strip() in DB_ONLY_EXPORT_FORMATS
    )


def _open_runtime(args):
    """Open the smallest runtime that satisfies the selected command."""
    read_only = not _requires_db_write(args)
    if _uses_database_runtime(args):
        return DatabaseRuntime(read_only=read_only)

    # Import lazily so DB-only commands do not import or initialize translator
    # machinery at all.
    from ..facade import Xenari

    return Xenari(
        read_only=read_only,
        site_root=Path(args.site_root).expanduser()
        if getattr(args, "site_root", None)
        else None,
    )


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "help":
        parser.print_help()
        return

    try:
        x = _open_runtime(args)
    except RuntimeError as exc:
        print(f"xenari: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    try:
        COMMAND_HANDLERS[args.command](args, x)
    finally:
        x.close()


if __name__ == "__main__":
    main()
