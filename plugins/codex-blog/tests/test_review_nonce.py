"""Editorial review is advisory; article completeness is code-enforced."""

from __future__ import annotations

import json
import subprocess
import sys
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib
from pathlib import Path

from codex_blog.article import review_article
from codex_blog.models import BlogWriteRequest
from codex_blog.pipeline import create_run


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "article-first.md"


def _request() -> BlogWriteRequest:
    return BlogWriteRequest(
        topic="Article First SEO",
        primary_keyword="article first SEO",
        language="en",
        word_count=700,
    )


def test_article_preflight_requires_no_external_reviewer_nonce(tmp_path: Path) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    Path(manifest.article).write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "blog_preflight.py"), "--run", str(run_dir), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["core_complete"] is True
    assert not list(run_dir.glob("*nonce*"))


def test_review_score_cannot_become_a_hard_gate() -> None:
    with (ROOT / "agents" / "blog-reviewer.toml").open("rb") as handle:
        reviewer = tomllib.load(handle)["developer_instructions"]
    normalized = " ".join(reviewer.split())
    assert "Scores guide revisions; no score threshold blocks" in reviewer
    assert "Low score" in normalized and "are not core-blocking" in normalized


def test_placeholder_remains_a_real_core_blocker(tmp_path: Path) -> None:
    article = tmp_path / "article.md"
    article.write_text(FIXTURE.read_text(encoding="utf-8") + "\n[TODO: finish]\n", encoding="utf-8")
    review = review_article(article, _request())
    assert review.complete is False
    assert any("placeholder" in error.lower() for error in review.errors)


def test_complete_article_does_not_need_review_md(tmp_path: Path) -> None:
    article = tmp_path / "article.md"
    article.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    review = review_article(article, _request())
    assert review.complete is True
    assert not (tmp_path / "review.md").exists()
