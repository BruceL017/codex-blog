"""Installer surface and ownership contract tests."""

from __future__ import annotations

from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
PROJECT = PLUGIN.parents[1]


def test_all_platform_wrappers_delegate_to_one_installer() -> None:
    for name in ("install.sh", "install.ps1", "uninstall.sh", "uninstall.ps1"):
        path = PROJECT / name
        assert path.is_file()
        assert "scripts/install.py" in path.read_text(encoding="utf-8")


def test_installer_validates_complete_plugin_payload() -> None:
    text = (PROJECT / "scripts" / "install.py").read_text(encoding="utf-8")
    for phrase in (
        ".codex-plugin",
        "plugin.json",
        "codex-blog",
        "AGENT_NAMES",
        "install-state.json",
        "marketplace",
    ):
        assert phrase in text


def test_installer_tracks_exact_six_toml_agents() -> None:
    installer = (PROJECT / "scripts" / "install.py").read_text(encoding="utf-8")
    agents = sorted((PLUGIN / "agents").glob("*.toml"))
    assert len(agents) == 6
    for path in agents:
        assert path.stem in installer


def test_uninstall_is_ownership_aware() -> None:
    text = (PROJECT / "scripts" / "install.py").read_text(encoding="utf-8")
    assert "owned" in text
    assert "unmanaged" in text
    assert "unlink" in text
    assert "install-state.json" in text
