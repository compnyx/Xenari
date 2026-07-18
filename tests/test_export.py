"""Focused Xenari behavior tests."""

import json
import shutil
import subprocess

def test_unified_export_and_reverse_helpers(tmp_path, xenari):
    assert xenari.export_format("json").lstrip().startswith("[")
    assert xenari.export_json() == xenari.db.export_json()
    assert "const DICT" in xenari.export_format("js")

    out = tmp_path / "lexicon.md"
    assert "wrote" in xenari.export_format("md", output=out)
    assert out.exists()


def test_database_json_export_uses_bounded_queries(fresh_xenari):
    x = fresh_xenari
    statements = []
    x.db.conn.set_trace_callback(statements.append)

    exported = x.db.export_json()

    selects = [statement for statement in statements if statement.lstrip().upper().startswith("SELECT")]
    assert json.loads(exported)
    assert len(selects) == 2

def test_export_js_uses_json_escaping_and_is_valid_javascript(tmp_path, fresh_xenari):
    x = fresh_xenari
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
