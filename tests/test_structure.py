"""Package-layout and compatibility-boundary tests."""

from pathlib import Path

from .support import REPO


def test_src_package_and_legacy_entrypoint_share_the_same_facade():
    from xenari_tool import Xenari as LegacyXenari
    from xenari import Xenari as PackagedXenari

    assert LegacyXenari is PackagedXenari
    instance = PackagedXenari(read_only=True)
    assert instance.db.db_path.resolve() == (REPO / "xenari.db").resolve()


def test_repository_compatibility_surface_is_intentionally_minimal():
    compatibility_modules = {path.name for path in REPO.glob("xenari_*.py")}

    assert compatibility_modules == {
        "xenari_compat.py",
        "xenari_db.py",
        "xenari_tool.py",
    }


def test_site_root_is_configurable_without_host_specific_paths(monkeypatch, tmp_path):
    from xenari.paths import resolve_site_root

    configured = tmp_path / "site"
    monkeypatch.setenv("XENARI_SITE_ROOT", str(configured))
    assert resolve_site_root() == configured.resolve()
    assert resolve_site_root(Path("~/other-site")) == Path("~/other-site").expanduser().resolve()
