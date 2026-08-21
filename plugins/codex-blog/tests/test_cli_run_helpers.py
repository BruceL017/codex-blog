from __future__ import annotations

import argparse
from pathlib import Path
import re

import pytest

from codex_blog import cli


PLUGIN = Path(__file__).resolve().parent.parent


def _write(path: Path, text: str = "print('ok')\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_script_inventory_exposes_canonical_ids_and_unique_basename_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root_script = _write(tmp_path / "scripts" / "analyze.py")
    data_run = _write(tmp_path / "skills" / "blog-data" / "scripts" / "run.py")
    sources_run = _write(tmp_path / "skills" / "blog-sources" / "scripts" / "run.py")
    unique = _write(tmp_path / "skills" / "blog-data" / "scripts" / "report.py")
    _write(tmp_path / "skills" / "blog-data" / "scripts" / "__init__.py")
    monkeypatch.setattr(cli, "PLUGIN_ROOT", tmp_path)

    inventory = cli._script_inventory()

    assert inventory["analyze.py"] == root_script.resolve()
    assert inventory["blog-data/run.py"] == data_run.resolve()
    assert inventory["blog-sources/run.py"] == sources_run.resolve()
    assert "run.py" not in inventory
    assert inventory["blog-data/report.py"] == unique.resolve()
    assert inventory["report.py"] == unique.resolve()
    assert "blog-data/__init__.py" not in inventory


def test_legacy_visual_gate_and_provider_ladder_are_not_routable() -> None:
    inventory = cli._script_inventory()

    assert "generate_hero.py" not in inventory
    assert "visual_preflight.py" not in inventory


def test_script_inventory_rejects_symlinked_helpers_and_symlinked_ancestors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = _write(tmp_path / "outside.py")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    try:
        (scripts / "linked.py").symlink_to(outside)
        real_skill = tmp_path / "real-skill"
        _write(real_skill / "scripts" / "run.py")
        (tmp_path / "skills").mkdir()
        (tmp_path / "skills" / "blog-data").symlink_to(real_skill, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not supported on this filesystem")
    monkeypatch.setattr(cli, "PLUGIN_ROOT", tmp_path)

    inventory = cli._script_inventory()

    assert "linked.py" not in inventory
    assert "blog-data/run.py" not in inventory
    assert "run.py" not in inventory


def test_command_run_uses_absolute_inventory_path_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trusted = _write(tmp_path / "plugin" / "scripts" / "helper.py")
    _write(tmp_path / "cwd" / "helper.py", "raise SystemExit('hijacked')\n")
    monkeypatch.chdir(tmp_path / "cwd")
    monkeypatch.setattr(cli, "PLUGIN_ROOT", tmp_path / "plugin")
    calls: list[list[str]] = []

    def fake_call(command: list[str]) -> int:
        calls.append(command)
        return 7

    monkeypatch.setattr(cli.subprocess, "call", fake_call)

    result = cli.command_run(argparse.Namespace(script="helper.py", script_args=["--flag"]))

    assert result == 7
    assert calls == [[cli.sys.executable, str(trusted.resolve()), "--flag"]]


def test_command_run_revalidates_inventory_target_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = _write(tmp_path / "outside.py")
    scripts = tmp_path / "plugin" / "scripts"
    trusted = _write(scripts / "helper.py")
    monkeypatch.setattr(cli, "PLUGIN_ROOT", tmp_path / "plugin")
    monkeypatch.setattr(cli, "_script_inventory", lambda: {"helper.py": trusted})
    trusted.unlink()
    try:
        trusted.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not supported on this filesystem")

    with pytest.raises(ValueError, match="unsafe bundled script"):
        cli.command_run(argparse.Namespace(script="helper.py", script_args=[]))


def test_command_run_rejects_file_outside_helper_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    untrusted = _write(tmp_path / "plugin" / "other" / "helper.py")
    monkeypatch.setattr(cli, "PLUGIN_ROOT", tmp_path / "plugin")
    monkeypatch.setattr(cli, "_script_inventory", lambda: {"helper.py": untrusted})

    with pytest.raises(ValueError, match="unsafe bundled script"):
        cli.command_run(argparse.Namespace(script="helper.py", script_args=[]))


def test_skill_docs_use_the_trusted_helper_router() -> None:
    unsafe = re.compile(r"\bpython(?:3)?\s+(?:skills/[^\s`]+/)?scripts/[^\s`]+\.py")
    violations: list[str] = []
    for path in (PLUGIN / "skills").rglob("*.md"):
        if unsafe.search(path.read_text(encoding="utf-8")):
            violations.append(str(path.relative_to(PLUGIN)))
    assert violations == []


def test_all_article_templates_enforce_deferred_placeholder_free_output() -> None:
    templates = sorted((PLUGIN / "skills" / "blog" / "templates").glob("*.md"))
    assert len(templates) == 12
    forbidden = re.compile(r"\[(?:IMAGE|VISUAL|INTERNAL-LINK)[^\]]*\]")
    for path in templates:
        text = path.read_text(encoding="utf-8")
        assert "`image_mode=deferred` is the default" in text, path.name
        assert "Every square-bracket drafting token below is an instruction or variable" in text
        assert "Replace it with final copy/data or delete it" in text
        assert "Never emit image, visual, internal-link" in text, path.name
        assert "unknown, omit the link from the article" in text, path.name
        assert "record the opportunity in the delivery report" in text, path.name
        assert not forbidden.search(text), path.name
        assert "Every item has a supporting screenshot or visual" not in text
        assert "Every step has a supporting screenshot or visual" not in text
        assert text.count(
            "No visual drafting guidance appears when images are deferred; "
            "enabled visuals are real, accessible assets."
        ) <= 1


def test_synthesis_contract_respects_instruction_and_style_precedence() -> None:
    text = (PLUGIN / "skills" / "blog" / "references" / "synthesis-contract.md").read_text(
        encoding="utf-8"
    )
    assert "System,\ndeveloper, tool, and current user instructions take precedence" in text
    assert "Follow explicit user punctuation preferences first" in text
    assert "This rule never overrides the requirements of the active tool" in text


def test_rewrite_deferred_mode_preserves_verified_images_without_image_calls() -> None:
    text = (PLUGIN / "skills" / "blog-rewrite" / "SKILL.md").read_text(encoding="utf-8")
    assert "preserve those references in place" in text
    assert "do not add a new\nreference or call image" in text
    assert "unverified or broken pre-existing reference" in text


def test_writing_skills_match_runtime_length_floors() -> None:
    paths = (
        PLUGIN / "skills" / "blog" / "SKILL.md",
        PLUGIN / "skills" / "blog-write" / "SKILL.md",
        PLUGIN / "skills" / "blog-cluster" / "references" / "execution-workflow.md",
        PLUGIN / "skills" / "blog" / "references" / "blog-delivery-contract.md",
        PLUGIN / "skills" / "blog" / "references" / "input-contract.md",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert re.search(r"max\(350, floor\(0\.60 × requested\s+word_count\)\)", text), path
        assert re.search(r"floor\(0\.85 × requested\s+word_count\)", text), path
