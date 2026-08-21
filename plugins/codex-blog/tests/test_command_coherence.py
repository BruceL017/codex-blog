"""Codex Skill and command-surface coherence."""

from __future__ import annotations

import re
from pathlib import Path


PLUGIN = Path(__file__).resolve().parent.parent
PROJECT = PLUGIN.parents[1]


def test_orchestrator_routes_every_user_facing_blog_skill() -> None:
    text = (PLUGIN / "skills" / "blog" / "SKILL.md").read_text(encoding="utf-8")
    routed = set(re.findall(r"^\|.*?\|\s*`\$(blog-[a-z0-9-]+)`", text, re.MULTILINE))
    installed = {
        path.name
        for path in (PLUGIN / "skills").iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    expected = installed - {"blog", "blog-chart"}
    assert routed == expected, (
        f"routing mismatch: missing={sorted(expected - routed)}, "
        f"extra={sorted(routed - expected)}"
    )


def test_command_reference_covers_stable_entrypoints_and_runtime_groups() -> None:
    text = (PROJECT / "docs" / "COMMANDS.md").read_text(encoding="utf-8")
    for phrase in (
        "$blog write",
        "$blog-write",
        "codex-blog prepare",
        "codex-blog finalize",
        "codex-blog adapter brief",
        "codex-blog adapter materials",
        "codex-blog image plan",
        "codex-blog image generate",
        "codex-blog brain add",
        "codex-blog doctor",
    ):
        assert phrase in text


def test_taxonomy_sync_is_a_non_publishing_handoff() -> None:
    text = (PLUGIN / "skills" / "blog-taxonomy" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "never sends a CMS request" in text
    assert "CMS_API_KEY" not in text
    assert "Push taxonomy to CMS" not in text
    assert "syncs taxonomy via authenticated API calls" not in text
