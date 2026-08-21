#!/usr/bin/env python3
"""Validate the public Codex Blog repository or standalone plugin payload."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSION = "2.1.1"
PLUGIN_NAME = "codex-blog"
MARKETPLACE_NAME = "brucel017-codex-blog"
REPOSITORY = "https://github.com/BruceL017/codex-blog"


def _read_json(path: Path, errors: list[dict[str, str]]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append({"kind": "invalid_json", "file": str(path), "detail": str(exc)})
        return {}
    if not isinstance(value, dict):
        errors.append({"kind": "invalid_json_type", "file": str(path)})
        return {}
    return value


def _plugin_root(root: Path) -> tuple[Path, Path | None]:
    root = root.resolve()
    nested = root / "plugins" / PLUGIN_NAME
    if (nested / ".codex-plugin" / "plugin.json").is_file():
        return nested, root
    return root, None


def validate(root: Path) -> dict:
    plugin, repository = _plugin_root(root)
    errors: list[dict[str, str]] = []
    required = (
        ".codex-plugin/plugin.json",
        "pyproject.toml",
        "LICENSE",
        "NOTICE",
        "README.md",
        "skills/blog/SKILL.md",
    )
    for relative in required:
        if not (plugin / relative).is_file():
            errors.append({"kind": "missing_surface", "file": relative})

    manifest = _read_json(plugin / ".codex-plugin" / "plugin.json", errors)
    expected_manifest = {
        "name": PLUGIN_NAME,
        "version": VERSION,
        "repository": REPOSITORY,
        "homepage": REPOSITORY,
    }
    for field, expected in expected_manifest.items():
        if manifest.get(field) != expected:
            errors.append(
                {
                    "kind": "invalid_plugin_identity",
                    "file": ".codex-plugin/plugin.json",
                    "detail": f"{field} must be {expected!r}",
                }
            )

    skills = sorted((plugin / "skills").glob("*/SKILL.md"))
    agents = sorted((plugin / "agents").glob("*.toml"))
    if len(skills) != 33:
        errors.append({"kind": "skill_count", "detail": f"expected 33, got {len(skills)}"})
    if len(agents) != 6:
        errors.append({"kind": "agent_count", "detail": f"expected 6, got {len(agents)}"})

    restricted = [
        path.relative_to(root.resolve()).as_posix()
        for path in root.resolve().rglob("brain")
        if path.is_dir()
    ]
    if restricted:
        errors.append({"kind": "restricted_brain", "detail": ", ".join(restricted)})

    forbidden_runtime = re.compile(r"(?:\.claude-plugin|\.claude/|CLAUDE_BLOG_)", re.IGNORECASE)
    for path in [plugin / "README.md", *skills]:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if forbidden_runtime.search(text):
            errors.append(
                {"kind": "claude_runtime_reference", "file": path.relative_to(plugin).as_posix()}
            )

    if repository is not None:
        marketplace = _read_json(repository / ".agents" / "plugins" / "marketplace.json", errors)
        if marketplace.get("name") != MARKETPLACE_NAME:
            errors.append(
                {
                    "kind": "invalid_marketplace",
                    "file": ".agents/plugins/marketplace.json",
                    "detail": f"name must be {MARKETPLACE_NAME!r}",
                }
            )
        if not (repository / "install.sh").is_file() or not (repository / "install.ps1").is_file():
            errors.append({"kind": "missing_installers", "file": str(repository)})

    return {
        "status": "pass" if not errors else "fail",
        "root": str(root.resolve()),
        "plugin": str(plugin),
        "version": VERSION,
        "skills": len(skills),
        "agents": len(agents),
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    report = validate(args.root)
    print(json.dumps(report, indent=None if args.compact else 2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
