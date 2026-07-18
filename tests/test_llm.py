"""Focused Xenari behavior tests."""

import json
import subprocess
import sys

from xenari import Xenari

from .support import REPO

def test_llm_context_treats_model_as_semantic_translator_and_tool_as_linter():
    x = Xenari(REPO / "xenari.db", read_only=True)

    packet = x.llm_context("If you cannot translate it, fix it.", evidential="assumed")

    assert packet["schema"] == "xenari.llm_context.v1"
    assert packet["direction"] == "english_to_xenari"
    assert packet["architecture"]["llm_role"] == "semantic translator/interpreter"
    assert packet["architecture"]["tool_role"] == "canon linter and constraint checker"
    assert packet["architecture"]["tool_is_semantic_authority"] is False
    assert packet["candidate_contract"]["unsupported_bits"] == [
        "anything guessed, missing, or not canon"
    ]
    hints = {item["english"]: item["root"] for item in packet["lexicon_hints"]}
    assert hints["translate"] == "nrotm"
    assert hints["fix"] == "mlun"

def test_llm_candidate_linter_checks_hard_canon_constraints_only():
    x = Xenari(REPO / "xenari.db", read_only=True)

    valid = x.lint_xenari_candidate("ra mex ka neq ta zrent sa xa")
    assert valid["ok"] is True
    assert valid["unknown_tokens"] == []
    assert valid["frames"][0]["verb"] == "zrent"
    assert valid["tool_role"] == "hard canon linter only; not a semantic judge"

    fake_root = x.lint_xenari_candidate("ra blorq ka neq ta zrent sa xa")
    assert fake_root["ok"] is False
    assert fake_root["unknown_tokens"] == ["blorq"]
    assert any("unknown root or particle: blorq" in error for error in fake_root["errors"])

    malformed = x.lint_xenari_candidate("ra mex neq ta zrent sa xa")
    assert malformed["ok"] is False
    assert any("missing ka subject marker" in error for error in malformed["errors"])

    particle_as_verb = x.lint_xenari_candidate("ra mex ka neq ta ka sa xa")
    assert particle_as_verb["ok"] is False
    assert any("followed by particle ka" in error for error in particle_as_verb["errors"])

    noun_as_verb = x.lint_xenari_candidate("ka neq ta cruq sa xo")
    assert noun_as_verb["ok"] is False
    assert any("root cruq is not attested as a verb" in error for error in noun_as_verb["errors"])

    repeated_case = x.lint_xenari_candidate("ra mex ra leq ka neq ta zrent sa xo")
    assert repeated_case["ok"] is False
    assert any("repeated marker ra" in error for error in repeated_case["errors"])

    marker_without_verb = x.lint_xenari_candidate("ra mex ka neq")
    assert marker_without_verb["ok"] is False
    assert any("without verb marker ta" in error for error in marker_without_verb["errors"])

    duplicate_finite_grammar = x.lint_xenari_candidate("ra mex ka neq ta zrent sa ve xo xa")
    assert duplicate_finite_grammar["ok"] is False
    assert any("multiple tense/aspect roots" in error for error in duplicate_finite_grammar["errors"])
    assert any("multiple evidential roots" in error for error in duplicate_finite_grammar["errors"])

def test_llm_candidate_linter_understands_structured_clause_boundaries():
    x = Xenari(REPO / "xenari.db", read_only=True)

    candidates = (
        "pevoq ra vi qex ka neq ta toq sa xo ti ka neq ta zaqa ve xo",
        "ra nu zrump ka neq ta xleq lo xo frex ra mex ka neq ta pegzos",
        "ka vi habdazluc su zre ra nu zrump ta zont vi lo xo ti ta zaqa vi sa xo",
        "su cruv ka nu zrump ta xleq nu sa xo ti ka neq ta zaqa sa xo",
    )
    for candidate in candidates:
        lint = x.lint_xenari_candidate(candidate)
        assert lint["ok"] is True, lint["errors"]

    unbalanced = x.lint_xenari_candidate(
        "pevoq ra vi qex ka neq ta toq sa xo ka neq ta zaqa ve xo"
    )
    assert unbalanced["ok"] is False
    assert any("unbalanced structural boundaries" in error for error in unbalanced["errors"])

def test_llm_cli_context_and_lint_json_contracts():
    context = subprocess.run(
        [sys.executable, "xenari_tool.py", "llm-context", "I love you"],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    )
    context_payload = json.loads(context.stdout)
    assert context_payload["schema"] == "xenari.llm_context.v1"
    assert context_payload["deterministic_tool_output"] == "ra mex ka neq ta zrent sa xo"

    lint = subprocess.run(
        [sys.executable, "xenari_tool.py", "llm-lint", "ra mex ka neq ta zrent sa xa"],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    )
    lint_payload = json.loads(lint.stdout)
    assert lint_payload["schema"] == "xenari.llm_lint.v1"
    assert lint_payload["ok"] is True

    failed = subprocess.run(
        [sys.executable, "xenari_tool.py", "llm-lint", "ra blorq ka neq ta zrent sa xa"],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    assert failed.returncode == 1
    assert json.loads(failed.stdout)["unknown_tokens"] == ["blorq"]
