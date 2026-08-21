"""Release, licensing, documentation, and clean-room safeguards."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib
from pathlib import Path


PLUGIN = Path(__file__).resolve().parent.parent
PROJECT = PLUGIN.parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_repository_validator_passes_current_tree() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT / "scripts" / "validate_repo.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, payload["errors"]
    assert payload == {"ok": True, "version": "2.1.2", "skills": 33, "agents": 6, "errors": []}


def test_no_restricted_upstream_brain_tree_was_copied() -> None:
    brain_dirs = [path for path in PROJECT.rglob("brain") if path.is_dir()]
    assert brain_dirs == []
    upstream = (PROJECT / "UPSTREAM.md").read_text(encoding="utf-8")
    assert "brain/" in upstream and "restrict" in upstream.lower()
    clean_room = (PLUGIN / "skills" / "blog-brain" / "SKILL.md").read_text(encoding="utf-8")
    assert "clean-room" in clean_room


def test_marketplace_slug_and_repository_owner_are_current() -> None:
    readme = (PROJECT / "README.md").read_text(encoding="utf-8")
    marketplace = json.loads((PROJECT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    plugin = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert marketplace["name"] == "brucel017-codex-blog"
    assert "codex-blog@brucel017-codex-blog" in readme
    assert plugin["repository"] == "https://github.com/BruceL017/codex-blog"


def test_core_package_is_standard_library_only() -> None:
    pyproject = (PLUGIN / "pyproject.toml").read_text(encoding="utf-8")
    assert "dependencies = []" in pyproject
    assert "analysis = [" in pyproject and "render = [" in pyproject
    assert 'codex-blog = "codex_blog.cli:main"' in pyproject


def test_docs_have_no_active_powershell_pipe_to_execution() -> None:
    pattern = re.compile(r"(?:\birm\b|\bInvoke-RestMethod\b)[^\n]*\|\s*(?:iex|Invoke-Expression)\b", re.IGNORECASE)
    violations = [
        path.relative_to(PROJECT).as_posix()
        for path in PROJECT.rglob("*.md")
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert not violations


def test_editorial_guidance_has_no_hard_stat_or_faq_quota() -> None:
    stat_quota = re.compile(r"(?:at least|minimum)\s+(?:one|\d+)[^\n]*(?:\[STAT\]|statistic)", re.IGNORECASE)
    fixed_faq = re.compile(r"(?:FAQ|Q&A)[^\n]*\(\s*\d+(?:-\d+)?\s*(?:questions?|items?)", re.IGNORECASE)
    for path in (PLUGIN / "skills" / "blog" / "templates").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert not stat_quota.search(text), path.name
        assert not fixed_faq.search(text), path.name


def test_score_and_visuals_are_not_delivery_quotas() -> None:
    orchestrator = (PLUGIN / "skills" / "blog" / "SKILL.md").read_text(encoding="utf-8")
    with (PLUGIN / "agents" / "blog-reviewer.toml").open("rb") as handle:
        reviewer = tomllib.load(handle)["developer_instructions"]
    assert "scoring thresholds" in orchestrator and "prerequisites" in orchestrator
    assert "no score threshold blocks" in reviewer
    normalized = " ".join(reviewer.split())
    assert "Absence of visuals is not an issue" in normalized


def test_current_data_skill_and_ledger_ship_together() -> None:
    assert (PLUGIN / "data" / "google-updates.json").is_file()
    currentness = PLUGIN / "skills" / "blog-data" / "references" / "search-currentness.md"
    assert currentness.is_file()
    reference = currentness.read_text(encoding="utf-8")
    assert "data/google-updates.json" in reference


def test_custom_image_provider_docs_require_env_secrets() -> None:
    docs = (PROJECT / "docs" / "PROVIDERS.md").read_text(encoding="utf-8")
    security = (PROJECT / "SECURITY.md").read_text(encoding="utf-8")
    for phrase in ("openai-compatible", "gemini-compatible", "base_url", "api_key_env"):
        assert phrase in docs
    assert "environment-only" in security


def test_flow_prompt_attribution_is_preserved() -> None:
    paths = sorted((PLUGIN / "skills" / "blog-flow" / "references").rglob("*.md"))
    assert paths
    for path in paths:
        assert path.read_text(encoding="utf-8").startswith("<!-- (c) Daniel Agrici, FLOW")


def test_consistency_checker_reports_missing_markdown_target(tmp_path: Path) -> None:
    module = _load_module("codex_blog_consistency", PLUGIN / "scripts" / "consistency_check.py")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("[missing](missing.md)\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "orphan.py").write_text('"""fixture"""\n', encoding="utf-8")
    prompt = tmp_path / "skills" / "blog-flow" / "references" / "prompts" / "find" / "prompt.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("prompt\n", encoding="utf-8")
    result = module.check(tmp_path)
    assert result["status"] == "fail"
    assert any(item["kind"] == "missing_markdown_target" for item in result["errors"])


def test_private_email_is_absent_from_release_payload() -> None:
    private = ("bittaso" + "001@gmail.com").casefold()
    offenders = []
    for path in PROJECT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in {".md", ".py", ".json", ".toml", ".yml", ".yaml", ".cff", ".txt", ".sh", ".ps1"}:
            continue
        try:
            if private in path.read_text(encoding="utf-8").casefold():
                offenders.append(path.relative_to(PROJECT).as_posix())
        except UnicodeDecodeError:
            pass
    assert not offenders
