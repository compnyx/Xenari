"""Focused Xenari behavior tests."""

import json
import subprocess
import sys

from xenari import Xenari
from xenari.services.gap import GapHarvester

from .support import REPO

def test_gap_harvest_captures_words_phrases_sounds_and_names(tmp_path):
    script = tmp_path / "script.txt"
    script.write_text(
        """INT. BLACK ROOM - NIGHT

NYX:
Hello Varek.

(FZZARR.)
LEE watches.
The rustglass elevator hums.
The rustglass elevator hums.
Her claws skittered across the floor.
""",
        encoding="utf-8",
    )
    x = Xenari(REPO / "xenari.db")
    harvester = GapHarvester(x)
    report = harvester.harvest_paths([script], phrase_min_count=2)
    buckets = report["buckets"]

    assert any(item["key"] == "fzzarr" for item in buckets["sound_effects"])
    assert any(item["key"] == "varek" for item in buckets["names_places"])
    assert any(item["key"] == "lee" for item in buckets["names_places"])
    assert any(item["key"] == "int" for item in buckets["script_format_markers"])
    assert any(item["key"] == "skittered" for item in buckets["lexical_gaps"])
    assert any(item["key"] == "the rustglass" for item in buckets["phrase_gaps"])
    assert not any(item["key"] == "int" for item in buckets["lexical_gaps"])
    assert not any(item["key"] == "lee" for item in buckets["lexical_gaps"])

    markdown = harvester.render_markdown(report, limit=5)
    assert "# Xenari Gap Harvest Report" in markdown
    assert "## Sound Effects" in markdown
    assert "## Phrase Gaps" in markdown
    assert "script.txt:" in markdown

def test_gap_harvest_normalizes_all_supported_apostrophes():
    x = Xenari(REPO / "xenari.db")
    harvester = GapHarvester(x)
    variants = ["I'm", "I’m", "I‘m", "Iʼm", "I＇m", "I`m"]

    reports = [
        harvester.harvest_documents([{"source": "dialogue", "text": variant}])
        for variant in variants
    ]

    bucket_keys = [
        {name: [item["key"] for item in entries] for name, entries in report["buckets"].items()}
        for report in reports
    ]
    assert all(keys == bucket_keys[0] for keys in bucket_keys[1:])
    assert bucket_keys[0]["covered_by_grammar"] == ["am"]

def test_gap_harvest_keeps_repeated_sounds_inline_speakers_and_stage_spans_separate():
    x = Xenari(REPO / "xenari.db")
    harvester = GapHarvester(x)
    report = harvester.harvest_documents([{
        "source": "dialogue",
        "text": "NYX: Ugh… KRRR KRRR.\nMARA:\n[FZZARR FZZARR] I run.\n",
    }], phrase_min_count=1, max_phrase_words=3)
    buckets = report["buckets"]

    ugh = next(item for item in buckets["vocalizations"] if item["key"] == "ugh")
    krrr = next(item for item in buckets["sound_effects"] if item["key"] == "krrr")
    fzzarr = next(item for item in buckets["sound_effects"] if item["key"] == "fzzarr")
    phrase_keys = {item["key"] for item in buckets["phrase_gaps"]}
    all_keys = {
        item["key"]
        for entries in buckets.values()
        for item in entries
    }

    assert ugh["count"] == 1
    assert ugh["contexts"][0]["speaker"] == "Nyx"
    assert krrr["count"] == 2
    assert krrr["contexts"][0]["speaker"] == "Nyx"
    assert fzzarr["count"] == 2
    assert fzzarr["contexts"][0]["speaker"] == "Mara"
    assert fzzarr["contexts"][0]["stage_direction"] is True
    assert "ugh krrr" not in phrase_keys
    assert "fzzarr i" not in phrase_keys
    assert "nyx" not in all_keys
    assert "mara" not in all_keys

def test_gaps_cli_writes_json_report(tmp_path):
    script = tmp_path / "script.txt"
    out = tmp_path / "gap-report.json"
    script.write_text("MARA:\nNnn. The rustglass door clicks.\nThe rustglass door clicks.\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "xenari_tool.py",
            "gaps",
            str(script),
            "--format",
            "json",
            "--output",
            str(out),
            "--phrase-min-count",
            "2",
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert f"wrote {out}" in result.stdout
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["documents"] == 1
    assert any(item["key"] == "nnn" for item in data["buckets"]["vocalizations"])
    assert any(item["key"] == "the rustglass" for item in data["buckets"]["phrase_gaps"])

def test_gap_harvest_preserves_uppercase_cues_and_expands_wont():
    x = Xenari(REPO / "xenari.db", read_only=True)
    harvester = GapHarvester(x)
    report = harvester.harvest_documents([{
        "source": "dialogue",
        "text": "BANG\nUGH\nHELP\nKRRR KRRR\nI won't go.",
    }])
    buckets = report["buckets"]
    sounds = {item["key"] for item in buckets["sound_effects"]}
    vocals = {item["key"] for item in buckets["vocalizations"]}
    all_keys = {item["key"] for entries in buckets.values() for item in entries}
    assert {"bang", "help", "krrr"} <= sounds
    assert "ugh" in vocals
    assert "wo" not in all_keys
    assert harvester._normalize_word("won't") == ["will", "not"]
