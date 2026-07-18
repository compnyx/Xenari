import json
import datetime
from pathlib import Path
from typing import List, Tuple

from ..paths import TRANSLATOR_FIXTURES


class HealthMixin:
    def info(self, root: str) -> str:
        return self.lexicon.get(root, "unknown root")

    def stats(self) -> str:
        """Expose the database's single canonical statistics summary."""
        return self.db.stats()

    def validate_roots(self, roots: List[str]) -> Tuple[bool, str]:
        """Validate one or more root forms and return (all_ok, report)."""
        if not roots:
            return False, "Usage: validate <root> [root...]"

        lines = []
        ok = True
        for root in roots:
            issues = self.db.validate_phonotactics(root)
            if issues:
                ok = False
                lines.append(f"{root}: INVALID")
                for issue in issues:
                    lines.append(f"  - {issue}")
            else:
                lines.append(f"{root}: ok")
        return ok, "\n".join(lines)

    def doctor(self) -> Tuple[bool, str]:
        """Run a compact health check for the canon DB and common tool behavior."""
        phrase_cases = {
            "I love you": "ra mex ka neq ta zrent sa xo",
            "you little bitch": "mex krengk frem",
            "I see the alien": "ra vi qex ka neq ta toq sa xo",
            "the alien sees me": "ra neq ka vi qex ta toq vi sa xo",
            "the alien is dangerous": "ra fatyih ka vi qex ta zux vi sa xo",
            "the hat is red": "ra rlis ka nu brid ta zux nu sa xo",
            "I approach the figure by the lake. The figure's hat blows off": (
                "ra vi loco na nu qlon ka neq ta frig sa xo. "
                "ra vi loco po brid ka vi cuq ta qruq vi sa xo"
            ),
        }
        lookup_cases = {
            "you": "mex",
            "me": "neq",
            "wrath": "nud",
            "perilous": "fatyih",
        }

        lines = ["Xenari doctor", self.db.stats(), ""]
        ok = True

        audit = self.db.audit(limit=3)
        for needle in (
            "Actionable exact duplicate groups: 0",
            "Stale/conflict/reanalysis marker rows: 0",
            "Phonotactic validator failures: 0",
        ):
            if needle not in audit:
                ok = False
                lines.append(f"FAIL audit: missing {needle}")
        if ok:
            lines.append("audit: ok")

        for english, expected in lookup_cases.items():
            root, _meaning = self.lookup(english)
            if root != expected:
                ok = False
                lines.append(f"FAIL lookup {english!r}: expected {expected}, got {root}")
        if all(self.lookup(english)[0] == expected for english, expected in lookup_cases.items()):
            lines.append("lookup: ok")

        for english, expected in phrase_cases.items():
            actual = self.speak(english, evidential="assumed")
            if actual != expected:
                ok = False
                lines.append(f"FAIL speak {english!r}:")
                lines.append(f"  expected: {expected}")
                lines.append(f"  actual:   {actual}")
        if all(self.speak(english, evidential="assumed") == expected for english, expected in phrase_cases.items()):
            lines.append("speak: ok")

        lines.append("")
        lines.append("status: ok" if ok else "status: FAIL")
        return ok, "\n".join(lines)

    def parity(self) -> Tuple[bool, str]:
        """Check the shared translator fixture contract against this Python tool."""
        fixture_path = TRANSLATOR_FIXTURES
        fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
        lines = ["Xenari translator parity", f"Fixtures: {fixture_path}"]
        ok = True

        forward_cases = fixtures.get("forward", [])
        reverse_cases = fixtures.get("reverse", [])
        for case in forward_cases:
            actual = self.speak(case["english"], evidential="assumed")
            if actual != case["xenari"]:
                ok = False
                lines.append(f"FAIL forward {case['english']!r}:")
                lines.append(f"  expected: {case['xenari']}")
                lines.append(f"  actual:   {actual}")
        for case in reverse_cases:
            actual = self.reverse(case["xenari"])
            if actual != case["english"]:
                ok = False
                lines.append(f"FAIL reverse {case['xenari']!r}:")
                lines.append(f"  expected: {case['english']}")
                lines.append(f"  actual:   {actual}")

        if ok:
            lines.append(f"forward: ok ({len(forward_cases)})")
            lines.append(f"reverse: ok ({len(reverse_cases)})")
        lines.append("status: ok" if ok else "status: FAIL")
        return ok, "\n".join(lines)

    def workbench(self, limit: int = 5) -> Tuple[bool, str]:
        """Agent-friendly snapshot for deciding what to do next."""
        ok, doctor_report = self.doctor()
        parity_ok, parity_report = self.parity()
        audit = self.db.audit(limit=0)
        lint = self.db.lint(limit=limit)
        lines = [
            "Xenari workbench",
            self.db.stats(),
            "",
            "Release gate:",
        ]
        for line in doctor_report.splitlines()[3:]:
            if line:
                lines.append(f"  {line}")
        lines.append(f"  translator parity: {'ok' if parity_ok else 'FAIL'}")
        lines.extend(["", "Audit counters:"])
        for line in audit.splitlines():
            if line.startswith((
                "Actionable exact duplicate groups:",
                "Stale/conflict/reanalysis marker rows:",
                "Phonotactic validator failures:",
                "Raw exact meaning duplicate groups:",
                "Raw headword duplicate groups:",
            )):
                lines.append(f"  {line}")
        lines.extend(["", "Lint preview:"])
        for line in lint.splitlines()[: max(8, limit + 8)]:
            lines.append(f"  {line}")
        lines.extend([
            "",
            "Useful next commands:",
            "  python3 xenari_tool.py search <english-or-root>",
            "  python3 xenari_tool.py near <meaning>",
            "  python3 xenari_tool.py curate --placeholder --limit 20",
            "  python3 xenari_tool.py curate --relations --limit 20",
            "  python3 xenari_tool.py categorize --root <root>",
            "  python3 xenari_tool.py coin <english> <meaning>",
            "  python3 xenari_tool.py add <english> <root> <meaning> --dry-run",
            "  python3 xenari_tool.py parity",
            "  python3 xenari_tool.py sync --site && pytest -q",
        ])
        return ok and parity_ok, "\n".join(lines)

    def review_report(self, limit: int = 10) -> Tuple[bool, str]:
        """Build a read-only Markdown review artifact for human/Codex follow-up."""
        doctor_ok, doctor_report = self.doctor()
        parity_ok, parity_report = self.parity()
        audit = self.db.audit(limit=limit)
        lint = self.db.lint(limit=limit)
        curation = self.db.curation_report(limit=limit)
        ok = doctor_ok and parity_ok
        generated = datetime.datetime.now().isoformat(timespec="seconds")

        lines = [
            "# Xenari QC Review Report",
            "",
            f"- Generated: `{generated}`",
            f"- Mode: read-only; no database writes",
            f"- Stats: `{self.db.stats()}`",
            f"- Doctor: `{'ok' if doctor_ok else 'FAIL'}`",
            f"- Translator parity: `{'ok' if parity_ok else 'FAIL'}`",
            "",
            "## Recommended Next Actions",
            "",
        ]
        if ok:
            lines.extend([
                "- Keep canon unchanged unless a human reviews a curation target.",
                "- Start with placeholder category proposals, then relation hypotheses.",
                "- Use preview commands first; write commands require `--yes` and create backups.",
            ])
        else:
            lines.extend([
                "- Fix failed doctor/parity checks before any curation writes.",
                "- Re-run `python3 xenari_tool.py doctor` and `python3 xenari_tool.py parity` after fixes.",
            ])

        sections = [
            ("Doctor", doctor_report),
            ("Translator Parity", parity_report),
            ("Audit", audit),
            ("Lint", lint),
            ("Curation Queue", curation),
        ]
        for title, body in sections:
            lines.extend([
                "",
                f"## {title}",
                "",
                "```text",
                body,
                "```",
            ])
        lines.extend([
            "",
            "## Safe Follow-up Commands",
            "",
            "```bash",
            "python3 xenari_tool.py curate --placeholder --limit 20",
            "python3 xenari_tool.py curate --relations --limit 20",
            "python3 xenari_tool.py categorize --root <root>",
            "python3 xenari_tool.py relate <root-a> <root-b> --relation <type> --dry-run",
            "python3 xenari_tool.py doctor",
            "pytest -q",
            "```",
        ])
        return ok, "\n".join(lines)
