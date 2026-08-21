"""Codex plugin and local Marketplace manifest contracts."""

from __future__ import annotations

import json
from pathlib import Path


PLUGIN = Path(__file__).resolve().parent.parent
PROJECT = PLUGIN.parents[1]


def test_plugin_manifest_is_codex_native_and_registry_safe() -> None:
    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "codex-blog"
    assert manifest["version"] == "2.1.1"
    assert manifest["skills"] == "./skills/"
    assert 0 < len(manifest["description"]) <= 500
    assert not ({"mcpServers", "apps", "hooks"} & manifest.keys())


def test_marketplace_identity_and_source_are_stable() -> None:
    marketplace = json.loads((PROJECT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    assert marketplace["name"] == "brucel017-codex-blog"
    assert len(marketplace["plugins"]) == 1
    entry = marketplace["plugins"][0]
    assert entry["name"] == "codex-blog"
    assert entry["source"] == {"source": "local", "path": "./plugins/codex-blog"}
    assert entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_USE"}
