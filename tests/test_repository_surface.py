from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_repo.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"] is True


def test_plugin_creator_manifest_validation() -> None:
    validator = (
        Path.home()
        / ".codex"
        / "skills"
        / ".system"
        / "plugin-creator"
        / "scripts"
        / "validate_plugin.py"
    )
    if not validator.is_file():
        return
    result = subprocess.run(
        [sys.executable, str(validator), str(ROOT / "plugins" / "codex-blog")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_image_refresh_is_documented() -> None:
    commands = (ROOT / "docs" / "COMMANDS.md").read_text(encoding="utf-8")
    providers = (ROOT / "docs" / "PROVIDERS.md").read_text(encoding="utf-8")
    assert "image refresh" in commands
    assert "image refresh" in providers


def test_provider_and_privacy_contracts_match_runtime_boundaries() -> None:
    providers = (ROOT / "docs" / "PROVIDERS.md").read_text(encoding="utf-8")
    privacy = (ROOT / "PRIVACY.md").read_text(encoding="utf-8")

    assert "${CODEX_HOME}/codex-blog/config.json" in providers
    assert "project `.codex-blog/config.json` files are" in providers
    assert "--config" in providers
    assert "CODEX_BLOG_IMAGE_[A-Z0-9_]+" in providers
    assert "official OpenAI host" in providers
    assert "official Gemini host" in providers
    assert "google-api.json" in privacy
    assert "oauth-token.json" in privacy
    assert "`api_key`" in privacy
    assert "`ads_developer_token`" in privacy


def test_complete_third_party_licenses_ship_in_source_and_plugin() -> None:
    for name, marker in (
        ("Apache-2.0.txt", "Apache License\n                           Version 2.0"),
        ("CC-BY-4.0.txt", "Creative Commons Attribution 4.0 International Public License"),
    ):
        root_text = (ROOT / "LICENSES" / name).read_text(encoding="utf-8")
        plugin_text = (ROOT / "plugins" / "codex-blog" / "LICENSES" / name).read_text(
            encoding="utf-8"
        )
        assert marker in root_text
        assert plugin_text == root_text

    setup = (ROOT / "plugins" / "codex-blog" / "setup.py").read_text(encoding="utf-8")
    assert '"LICENSES"' in setup
