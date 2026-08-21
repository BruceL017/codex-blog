#!/usr/bin/env python3
"""Validate release tag and archive boundaries."""

from __future__ import annotations

import argparse
import json
import re
import sys

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "codex-blog"


def _cff_version(path: Path) -> str:
    match = re.search(r'^version:\s*["\']?([^\s"\']+)', path.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="")
    args = parser.parse_args(argv)
    with (PLUGIN / "pyproject.toml").open("rb") as handle:
        version = str(tomllib.load(handle)["project"]["version"])
    manifest = json.loads(
        (PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    surfaces = {
        "pyproject": version,
        "plugin": str(manifest.get("version", "")),
        "root citation": _cff_version(ROOT / "CITATION.cff"),
        "plugin citation": _cff_version(PLUGIN / "CITATION.cff"),
    }
    errors = [f"{label}={value!r}" for label, value in surfaces.items() if value != version]
    if args.tag and args.tag != f"v{version}":
        errors.append(f"tag={args.tag!r}, expected 'v{version}'")
    restricted = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_dir() and path.name == "brain"
    ]
    if restricted:
        errors.append(f"restricted Brain path(s): {restricted}")
    if errors:
        print("Release check failed: " + "; ".join(errors), file=sys.stderr)
        return 1
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
