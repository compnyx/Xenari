"""Public version contract checks."""

import re

from xenari import __version__

from .support import REPO


def test_public_version_is_semantic_and_changelog_has_release():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)

    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## {__version__} -" in changelog


def test_release_workflow_requires_matching_version_tag():
    workflow = (REPO / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert "GITHUB_REF_NAME" in workflow
    assert "src/xenari/_version.py" in workflow


def test_cli_reports_package_version_without_opening_canon(run_cli):
    result = run_cli("--version", check=True)
    assert result.stdout.strip().endswith(__version__)
