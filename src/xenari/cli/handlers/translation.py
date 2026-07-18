"""Translation and LLM-facing command handlers."""

import json
import sys

COMMANDS = frozenset({"compound", "speak", "gloss", "translate", "reverse", "llm-context", "llm-lint"})


def handle(args, x):
    """Execute a translation command."""
    if args.command == "compound":
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
    elif args.command == "llm-context":
        sent = " ".join(args.args)
        if not sent:
            print("Usage: llm-context <english-or-xenari>")
            sys.exit(1)
        print(json.dumps(x.llm_context(sent, args.tense, args.evidential), indent=2, ensure_ascii=False))
    elif args.command == "llm-lint":
        sent = " ".join(args.args)
        if not sent:
            print("Usage: llm-lint <xenari-candidate>")
            sys.exit(1)
        report = x.lint_xenari_candidate(sent)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if not report["ok"]:
            sys.exit(1)
