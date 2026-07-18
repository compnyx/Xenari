#!/usr/bin/env python3
"""Command-line interface for the Xenari tool."""

from pathlib import Path

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


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    write_commands = {"add", "remove", "map", "categorize", "relate", "coin", "sync"}
    x = Xenari(
        read_only=args.command not in write_commands,
        site_root=Path(args.site_root).expanduser() if args.site_root else None,
    )

    if args.command == "help":
        parser.print_help()
        return

    COMMAND_HANDLERS[args.command](args, x)


if __name__ == "__main__":
    main()
