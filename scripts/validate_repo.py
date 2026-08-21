#!/usr/bin/env python3
"""Release-gate validation for the Codex Blog Marketplace repository."""

from __future__ import annotations

import json
import re

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "codex-blog"
VERSION = "2.1.2"
MARKETPLACE = "brucel017-codex-blog"
SKILLS = {
    "blog",
    "blog-analyze",
    "blog-audit",
    "blog-brain",
    "blog-brand",
    "blog-brief",
    "blog-calendar",
    "blog-cannibalization",
    "blog-chart",
    "blog-cluster",
    "blog-data",
    "blog-decay",
    "blog-discourse",
    "blog-factcheck",
    "blog-flow",
    "blog-geo",
    "blog-image",
    "blog-locale-audit",
    "blog-localize",
    "blog-multilingual",
    "blog-narration",
    "blog-outline",
    "blog-persona",
    "blog-repurpose",
    "blog-rewrite",
    "blog-schema",
    "blog-seo-check",
    "blog-sources",
    "blog-strategy",
    "blog-style",
    "blog-taxonomy",
    "blog-translate",
    "blog-write",
}
AGENTS = {
    "blog-brain-curator",
    "blog-researcher",
    "blog-reviewer",
    "blog-seo",
    "blog-translator",
    "blog-writer",
}
REQUIRED_ROOT = {
    "README.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "PRIVACY.md",
    "THIRD_PARTY.md",
    "UPSTREAM.md",
    "LICENSE",
    "NOTICE",
    "CITATION.cff",
    "install.sh",
    "install.ps1",
    "uninstall.sh",
    "uninstall.ps1",
}
REQUIRED_DOCS = {
    "ARCHITECTURE.md",
    "COMMANDS.md",
    "DATA-CONTRACTS.md",
    "INSTALLATION.md",
    "PROVIDERS.md",
    "README.zh-CN.md",
    "RELEASE_CHECKLIST.md",
    "SKILLS.md",
    "TEMPLATES.md",
    "TROUBLESHOOTING.md",
}
REQUIRED_PLUGIN = {
    "MANIFEST.in",
    "THIRD_PARTY.md",
    "UPSTREAM.md",
    "setup.py",
    "requirements-analysis.txt",
    "requirements-dev.txt",
    "requirements-render.txt",
    "requirements.txt",
    "requirements.lock",
}
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
PRIVATE_EMAIL = ("bittaso" + "001@gmail.com").casefold()
TEXT_SUFFIXES = {
    ".cff",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def _frontmatter(path: Path) -> dict[str, str]:
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("missing YAML frontmatter")
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("JSON root must be an object")
    return value


def _version_from_cff(path: Path) -> str:
    match = re.search(r'^version:\s*["\']?([^\s"\']+)', path.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else ""


def _check_inventory(errors: list[str]) -> None:
    skills = {
        path.name
        for path in (PLUGIN / "skills").iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    agents = {path.stem for path in (PLUGIN / "agents").glob("*.toml")}
    if skills != SKILLS:
        errors.append(f"Skills: missing={sorted(SKILLS - skills)} extra={sorted(skills - SKILLS)}")
    if agents != AGENTS:
        errors.append(f"Agents: missing={sorted(AGENTS - agents)} extra={sorted(agents - AGENTS)}")
    agent_sources = {path.stem for path in (PLUGIN / "agents-src").glob("*.md")}
    if agent_sources != AGENTS:
        errors.append(
            f"Agent sources: missing={sorted(AGENTS - agent_sources)} "
            f"extra={sorted(agent_sources - AGENTS)}"
        )

    for name in sorted(SKILLS):
        path = PLUGIN / "skills" / name / "SKILL.md"
        try:
            meta = _frontmatter(path)
            if meta.get("name") != name:
                errors.append(f"{path.relative_to(ROOT)}: frontmatter name is {meta.get('name')!r}")
            if not meta.get("description"):
                errors.append(f"{path.relative_to(ROOT)}: description is required")
            if "[TODO:" in path.read_text(encoding="utf-8"):
                errors.append(f"{path.relative_to(ROOT)}: TODO placeholder is forbidden")
        except (OSError, ValueError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")

    for name in sorted(AGENTS):
        path = PLUGIN / "agents" / f"{name}.toml"
        try:
            with path.open("rb") as handle:
                agent = tomllib.load(handle)
            if agent.get("name") not in {None, name}:
                errors.append(f"{path.relative_to(ROOT)}: name is {agent.get('name')!r}")
            for key in ("description", "developer_instructions"):
                if not agent.get(key):
                    errors.append(f"{path.relative_to(ROOT)}: {key} is required")
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")


def _check_manifests(errors: list[str]) -> None:
    try:
        marketplace = _json(ROOT / ".agents" / "plugins" / "marketplace.json")
        plugin = _json(PLUGIN / ".codex-plugin" / "plugin.json")
        with (PLUGIN / "pyproject.toml").open("rb") as handle:
            pyproject = tomllib.load(handle)
        if marketplace.get("name") != MARKETPLACE:
            errors.append(f"marketplace name must be {MARKETPLACE}")
        entries = marketplace.get("plugins", [])
        entry = entries[0] if isinstance(entries, list) and entries else {}
        if entry.get("name") != "codex-blog":
            errors.append("marketplace plugin name must be codex-blog")
        if entry.get("source") != {"source": "local", "path": "./plugins/codex-blog"}:
            errors.append("marketplace source must be ./plugins/codex-blog")
        policy = entry.get("policy", {})
        if policy != {"installation": "AVAILABLE", "authentication": "ON_USE"}:
            errors.append("marketplace policy must be AVAILABLE/ON_USE")
        if plugin.get("name") != "codex-blog" or plugin.get("version") != VERSION:
            errors.append("plugin identity/version is invalid")
        if plugin.get("skills") != "./skills/":
            errors.append("plugin skills path must be ./skills/")
        if "mcpServers" in plugin or "apps" in plugin or "hooks" in plugin:
            errors.append("plugin declares an unbundled MCP, App, or hook component")
        project = pyproject.get("project", {})
        if project.get("name") != "codex-blog" or project.get("version") != VERSION:
            errors.append("pyproject identity/version is invalid")
        if project.get("scripts", {}).get("codex-blog") != "codex_blog.cli:main":
            errors.append("pyproject console entrypoint must be codex_blog.cli:main")
        if project.get("dependencies"):
            errors.append("core package must remain standard-library only")
        dev_dependencies = project.get("optional-dependencies", {}).get("dev", [])
        if not any(str(item).startswith("Pillow>=11.3,<13") for item in dev_dependencies):
            errors.append("development dependencies must include bounded Pillow for image tests")
        lock = PLUGIN / "requirements.lock"
        if not lock.is_file():
            errors.append("requirements.lock is missing")
        elif any(
            line.strip() and not line.lstrip().startswith("#")
            for line in lock.read_text(encoding="utf-8").splitlines()
        ):
            errors.append("core requirements.lock must not contain third-party distributions")
        if (PLUGIN / "pyproject.upstream.toml").exists():
            errors.append("stale pyproject.upstream.toml must not ship")
        setup_text = (PLUGIN / "setup.py").read_text(encoding="utf-8")
        manifest_text = (PLUGIN / "MANIFEST.in").read_text(encoding="utf-8")
        for directory in ("LICENSES", "agents-src", "agents", "schemas", "scripts", "skills"):
            if f'"{directory}"' not in setup_text or f"graft {directory}" not in manifest_text:
                errors.append(f"standalone package omits runtime resource directory: {directory}")
    except (OSError, TypeError, ValueError, IndexError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"manifest parse failure: {exc}")


def _check_versions_and_docs(errors: list[str]) -> None:
    for name in sorted(REQUIRED_ROOT):
        if not (ROOT / name).is_file():
            errors.append(f"missing root file: {name}")
    for name in sorted(REQUIRED_DOCS):
        if not (ROOT / "docs" / name).is_file():
            errors.append(f"missing documentation: docs/{name}")
    for name in sorted(REQUIRED_PLUGIN):
        if not (PLUGIN / name).is_file():
            errors.append(f"missing plugin packaging file: plugins/codex-blog/{name}")
    versions = {
        "root CITATION.cff": _version_from_cff(ROOT / "CITATION.cff"),
        "plugin CITATION.cff": _version_from_cff(PLUGIN / "CITATION.cff"),
    }
    init_text = (PLUGIN / "src" / "codex_blog" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)', init_text, re.MULTILINE)
    versions["codex_blog.__version__"] = match.group(1) if match else ""
    for label, value in versions.items():
        if value != VERSION:
            errors.append(f"{label} is {value!r}, expected {VERSION}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for phrase in (
        "33 Skills",
        "6 TOML",
        "complete SEO Markdown",
        "deferred",
        "Codex SEO",
        "extract-seo-materials",
    ):
        if phrase not in readme:
            errors.append(f"README is missing required concept: {phrase}")


def _check_licenses_and_boundaries(errors: list[str]) -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    third_party = (ROOT / "THIRD_PARTY.md").read_text(encoding="utf-8")
    upstream = (ROOT / "UPSTREAM.md").read_text(encoding="utf-8")
    plugin_notice = (PLUGIN / "NOTICE").read_text(encoding="utf-8")
    license_files = (
        "Apache-2.0.txt",
        "CC-BY-4.0.txt",
        "semantic-cluster-engine-MIT.txt",
    )
    for name in license_files:
        root_license = ROOT / "LICENSES" / name
        plugin_license = PLUGIN / "LICENSES" / name
        if not root_license.is_file() or not plugin_license.is_file():
            errors.append(f"missing bundled third-party license: {name}")
        elif root_license.read_bytes() != plugin_license.read_bytes():
            errors.append(f"root/plugin third-party license differs: {name}")
    for required in ("AgriciDaniel", "BruceL017"):
        if required not in license_text:
            errors.append(f"LICENSE is missing {required} copyright")
    for required in ("impeccable", "last30days-skill", "FLOW", "CC BY 4.0"):
        if required not in notice or required not in third_party:
            errors.append(f"third-party attribution is incomplete for {required}")
        if required not in plugin_notice:
            errors.append(f"standalone plugin NOTICE is incomplete for {required}")
    if "restrict" not in upstream.lower() or "brain/" not in upstream:
        errors.append("UPSTREAM.md must document the restricted Brain exclusion")
    restricted_dirs = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_dir() and path.name == "brain"
    ]
    if restricted_dirs:
        errors.append(f"restricted upstream Brain directories are present: {restricted_dirs}")

    flow_root = PLUGIN / "skills" / "blog-flow" / "references"
    for path in flow_root.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("<!-- (c) Daniel Agrici, FLOW"):
            errors.append(f"{path.relative_to(ROOT)}: missing FLOW CC BY header")


def _check_hygiene(errors: list[str]) -> None:
    forbidden_runtime = re.compile(
        r"(?:\.claude-plugin|\.claude/|CLAUDE_SKILL_DIR)", re.IGNORECASE
    )
    for base in (PLUGIN / "skills", PLUGIN / "agents"):
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "[TODO:" in text:
                errors.append(f"{path.relative_to(ROOT)}: TODO placeholder is forbidden")
            if forbidden_runtime.search(text):
                errors.append(f"{path.relative_to(ROOT)}: forbidden Claude runtime path")

    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"LICENSE", "NOTICE"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if PRIVATE_EMAIL in text.casefold():
            errors.append(f"{path.relative_to(ROOT)}: private email is forbidden")

    for path in (
        PLUGIN / "bin" / "codex-blog",
        ROOT / "scripts" / "install.py",
        ROOT / "scripts" / "validate_repo.py",
    ):
        if not path.is_file():
            errors.append(f"missing executable surface: {path.relative_to(ROOT)}")


def main() -> int:
    errors: list[str] = []
    try:
        _check_inventory(errors)
        _check_manifests(errors)
        _check_versions_and_docs(errors)
        _check_licenses_and_boundaries(errors)
        _check_hygiene(errors)
    except (OSError, ValueError) as exc:
        errors.append(f"validation aborted: {exc}")
    payload = {
        "ok": not errors,
        "version": VERSION,
        "skills": len(SKILLS),
        "agents": len(AGENTS),
        "errors": errors,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
