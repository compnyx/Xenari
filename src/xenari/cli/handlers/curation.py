"""Curation and lexicon mutation command handlers."""

import json
import sys

from ...db import normalize_part_of_speech

COMMANDS = frozenset(
    {
        "curate", "duplicates", "categorize", "relate", "propose-root", "coin",
        "remove", "map", "add", "pos-set", "pos-backfill",
    }
)


def _duplicate_payload(candidates):
    """Convert sqlite-backed candidate rows into a stable JSON shape."""
    return [
        {
            "head": candidate["head"],
            "kind": candidate["kind"],
            "confidence": candidate["confidence"],
            "reason": candidate["reason"],
            "suggested_relation": candidate["relation"],
            "rows": [dict(row) for row in candidate["rows"]],
        }
        for candidate in candidates
    ]


def _render_duplicates(candidates, *, total):
    lines = [
        "# Xenari Duplicate-Headword Review",
        "",
        "Human review only. No roots were merged and no relations were written.",
        "",
        f"Unlinked candidate groups: {total}",
    ]
    if not candidates:
        lines.extend(["", "none"])
        return "\n".join(lines)
    for candidate in candidates:
        lines.extend(
            [
                "",
                f"## {candidate['head']}",
                "",
                f"- Classification: {candidate['kind']}",
                f"- Confidence: {candidate['confidence']}",
                f"- Reason: {candidate['reason']}",
                f"- Suggested relation: {candidate['relation'] or 'none; review manually'}",
                "- Entries:",
            ]
        )
        for row in candidate["rows"]:
            lines.append(f"  - `{row['root']}` [{row['category']}]: {row['meaning']}")
    return "\n".join(lines)


def handle(args, x):
    """Execute a curation or mutation command."""
    if args.command == "curate":
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
    elif args.command == "duplicates":
        all_candidates = x.db.relation_candidates()
        visible = all_candidates[: max(args.limit, 0)]
        if args.format == "json":
            print(
                json.dumps(
                    {
                        "count": len(all_candidates),
                        "write_performed": False,
                        "candidates": _duplicate_payload(visible),
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print(_render_duplicates(visible, total=len(all_candidates)))
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
            for result in near:
                print(
                    f"  - {result['root']} — {result['meaning']} [{result['category']}] "
                    f"score={result.get('score', 0)}"
                )
        print("Suggestions:")
        for item in suggestions:
            print(
                f"  - {item['root']} [{item['category']}] score={item.get('score', 0)}: "
                f"{'; '.join(item['notes'])}"
            )
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
        if not x.db.remove_root(args.args[0]):
            sys.exit(1)
    elif args.command == "map":
        if len(args.args) < 2:
            print("Usage: map <english-key> <root> [context note]")
            sys.exit(1)
        note = " ".join(args.args[2:]) if len(args.args) > 2 else None
        ok, report = x.db.describe_english_mapping(
            args.args[0],
            args.args[1],
            context_note=note,
            part_of_speech=args.part_of_speech,
        )
        print(report)
        if not ok:
            sys.exit(1)
        if args.dry_run or not args.yes:
            if not args.dry_run:
                print("Refusing to map without --yes. Re-run with --yes after reading the preview.")
                sys.exit(1)
            sys.exit(0)
        if not x.db.add_english_mapping(
            args.args[0],
            args.args[1],
            context_note=note,
            part_of_speech=args.part_of_speech,
        ):
            sys.exit(1)
    elif args.command == "add":
        if len(args.args) < 2:
            print("Usage: add <english-word> <root> [meaning...]")
            print("Example: add hate blun \"to hate, detest, loathe\"")
            print("Optional: add ... --category \"Some Section (v0.8)\" ")
            sys.exit(1)
        english = args.args[0].lower().strip()
        root = args.args[1].strip()
        meaning = " ".join(args.args[2:]).strip() if len(args.args) > 2 else english
        category = args.category or x.db._guess_category(english, meaning)
        dry_run = args.dry_run or not args.yes
        ok, messages = x.db.add_root(
            english,
            root,
            meaning,
            category=category,
            notes=args.notes,
            dry_run=dry_run,
            part_of_speech=args.part_of_speech,
        )
        for message in messages:
            print(message)
        if dry_run:
            if ok and not args.dry_run:
                print("Refusing to add without --yes. Re-run with --yes after reading the preview.")
                sys.exit(1)
            sys.exit(0 if ok else 1)
        if ok:
            verification = x.db.lookup(english)
            if verification:
                verification = (verification[0], verification[1].lower())
            print(
                f"Verified: {verification[0]} — {verification[1]}"
                if verification
                else "WARNING: added but lookup failed (english key not auto-mapped)"
            )
        else:
            sys.exit(1)
    elif args.command == "pos-set":
        if len(args.args) != 3:
            print("Usage: pos-set <english-key> <root> <part-of-speech|unknown> [--dry-run|--yes]")
            sys.exit(1)
        english_key, root, part_of_speech = args.args
        try:
            normalized = normalize_part_of_speech(part_of_speech)
        except ValueError as exc:
            print(exc)
            sys.exit(1)
        mapping = x.db.conn.execute(
            """SELECT 1 FROM english_map e JOIN roots r ON r.id = e.root_id
               WHERE e.english_key = ? AND r.root = ?""",
            (english_key.lower().strip(), root),
        ).fetchone()
        if mapping is None:
            print(f"Unknown mapping: {english_key} -> {root}")
            sys.exit(1)
        print(
            f"POS preview: {english_key.lower().strip()} -> {root} = "
            f"{normalized or 'unknown'}"
        )
        if args.dry_run:
            return
        if not args.yes:
            print("Refusing to update without --yes. Re-run with --yes after reading the preview.")
            sys.exit(1)
        if not x.db.set_mapping_part_of_speech(english_key, root, normalized):
            sys.exit(1)
        print("Part of speech updated.")
    elif args.command == "pos-backfill":
        preview = x.db.backfill_parts_of_speech(apply=False)
        print(
            f"POS backfill preview: {preview['proposal_count']} sense(s) "
            f"{preview['proposed_counts']}"
        )
        if args.dry_run:
            return
        if not args.yes:
            print("Refusing to backfill without --yes. Re-run with --yes after reading the preview.")
            sys.exit(1)
        result = x.db.backfill_parts_of_speech(apply=True)
        print(
            f"Applied {result['proposal_count']} POS proposal(s); "
            f"annotated={result['coverage']['annotated']}"
        )
