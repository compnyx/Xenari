import json
from pathlib import Path
from typing import Optional


class ExportMixin:
    def export_js_dict(self) -> str:
        """Export a clean JS dict for the site translator."""
        data = {
            eng: {"root": root, "gloss": self.lexicon.get(root, "")}
            for eng, root in sorted(self.english_to_root.items())
        }
        # JSON is valid JavaScript object syntax and escapes every user/data
        # supplied string (including quote-bearing English keys and glosses).
        return "const DICT = " + json.dumps(data, indent=2, ensure_ascii=False) + ";"

    def export_json(self) -> str:
        """Export as JSON for external use."""
        data = {}
        for eng, root in sorted(self.english_to_root.items()):
            data[eng] = {"root": root, "gloss": self.lexicon.get(root, "")}
        return json.dumps(data, indent=2, ensure_ascii=False)

    def export_format(self, fmt: str, output: Optional[Path] = None, include_site: bool = False) -> str:
        """Unified export surface for generated dictionary artifacts."""
        fmt = fmt.lower().strip()
        if fmt in {"json", "dict"}:
            text = self.db.export_json()
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(text, encoding="utf-8")
                return f"wrote {output}"
            return text
        if fmt in {"js", "browser"}:
            text = self.export_js_dict()
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(text, encoding="utf-8")
                return f"wrote {output}"
            return text
        if fmt in {"md", "markdown"}:
            out = output or Path("xenari-lexicon-export.md")
            self.db.export_markdown(out)
            return f"wrote {out}"
        if fmt == "site":
            return self.sync_exports(include_site=True)
        if fmt == "repo":
            return self.sync_exports(include_site=False)
        raise ValueError(f"unknown export format: {fmt}")
