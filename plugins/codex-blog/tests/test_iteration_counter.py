"""Retry-budget coherence for the article-first pipeline."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_core_checkpoint_budget_is_documented_as_three_total_attempts() -> None:
    contract = (ROOT / "skills" / "blog" / "references" / "blog-delivery-contract.md").read_text(encoding="utf-8")
    orchestrator = (ROOT / "skills" / "blog" / "SKILL.md").read_text(encoding="utf-8")
    writer = (ROOT / "agents" / "blog-writer.toml").read_text(encoding="utf-8")
    assert "up to three total attempts" in contract
    assert "resume up to three" in orchestrator
    assert "maximum of three core attempts" in writer


def test_downstream_budget_is_documented_as_two_total_attempts() -> None:
    contract = (ROOT / "skills" / "blog" / "references" / "blog-delivery-contract.md").read_text(encoding="utf-8")
    orchestrator = (ROOT / "skills" / "blog" / "SKILL.md").read_text(encoding="utf-8")
    assert "initial attempt plus one retry, two total" in contract
    assert "at most two total attempts" in orchestrator


def test_runtime_default_downstream_budget_is_two() -> None:
    runtime = (ROOT / "src" / "codex_blog" / "pipeline.py").read_text(encoding="utf-8")
    assert "attempts: int = 2" in runtime
    assert "skipped after {attempts} attempts" in runtime
