from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "codex-blog"


def test_community_origin_license_and_boundaries_ship() -> None:
    license_name = "semantic-cluster-engine-MIT.txt"
    root_license = (ROOT / "LICENSES" / license_name).read_text(encoding="utf-8")
    plugin_license = (PLUGIN / "LICENSES" / license_name).read_text(encoding="utf-8")

    assert plugin_license == root_license
    assert "Copyright (c) 2026 fiya-chris-and-AI" in root_license
    assert "Permission is hereby granted" in root_license

    for base in (ROOT, PLUGIN):
        notice = (base / "NOTICE").read_text(encoding="utf-8")
        third_party = (base / "THIRD_PARTY.md").read_text(encoding="utf-8")
        assert license_name in notice
        assert "86ceb6ecf60b0b4f16d67dfa52b30a69ad57f14d" in third_party
        assert "Original repository license: none declared" in third_party
        assert "clean-room integration" in third_party


def test_image_prompt_reference_has_clean_provenance() -> None:
    reference = (
        PLUGIN / "skills" / "blog-image" / "references" / "prompt-engineering-blog.md"
    ).read_text(encoding="utf-8")

    assert "written independently for Codex Blog" in reference
    assert "Adapted from Banana Claude" not in reference
    assert "Ultimate Prompting Guide" not in reference
    assert "https://ai.google.dev/gemini-api/docs/image-generation" in reference
