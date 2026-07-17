"""Focused Xenari behavior tests."""

from .support import *

def test_unified_export_and_reverse_helpers(tmp_path):
    x = Xenari(REPO / "xenari.db")

    assert x.export_format("json").lstrip().startswith("[")
    assert "const DICT" in x.export_format("js")

    out = tmp_path / "lexicon.md"
    assert "wrote" in x.export_format("md", output=out)
    assert out.exists()

def test_export_js_uses_json_escaping_and_is_valid_javascript(tmp_path):
    x = Xenari(REPO / "xenari.db", read_only=True)
    x.english_to_root['feed"'] = "zrent"
    x.lexicon["zrent"] = 'to love "without loss"\nwith care'
    exported = x.export_js_dict()
    payload = exported.removeprefix("const DICT = ").removesuffix(";")
    assert json.loads(payload)['feed"']['gloss'] == 'to love "without loss"\nwith care'

    output = tmp_path / "xenari-export.js"
    output.write_text(exported, encoding="utf-8")
    node = shutil.which("node")
    if node:
        result = subprocess.run([node, "--check", str(output)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
