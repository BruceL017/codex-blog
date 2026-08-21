from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .article import ArticleReview, review_article, write_review, write_schema
from .frontmatter import read_markdown
from .links import check_links
from .models import BlogWriteRequest, RunManifest, StageResult
from .platforms import adapt_platform
from .resources import plugin_root
from .utils import (
    assert_no_symlink_ancestors,
    atomic_write_json,
    atomic_write_text,
    safe_json_load,
    safe_read_text,
    utc_now,
)

PLUGIN_ROOT = plugin_root()
DEFAULT_OUTPUT_ROOT = Path(".codex-blog") / "output"


class CoreArticleError(RuntimeError):
    def __init__(self, message: str, *, blocked: bool, attempts: int = 0) -> None:
        super().__init__(message)
        self.blocked = blocked
        self.attempts = attempts


def _manifest_path(run_dir: Path) -> Path:
    return run_dir / "run-manifest.json"


def _validated_run_dir(run_dir: Path) -> Path:
    absolute = run_dir.absolute()
    assert_no_symlink_ancestors(absolute.parent)
    if absolute.is_symlink() or not absolute.is_dir():
        raise ValueError(f"run directory must be a regular directory: {absolute}")
    return absolute


def _validate_manifest_paths(manifest: RunManifest, run_dir: Path) -> None:
    expected_output = _validated_run_dir(run_dir)
    declared_output = Path(manifest.output_dir)
    if not declared_output.is_absolute() or declared_output != expected_output:
        raise ValueError("manifest output_dir must exactly match the run directory")
    expected_article = expected_output / f"{manifest.slug}.md"
    expected_request = expected_output / "request.json"
    if Path(manifest.article) != expected_article:
        raise ValueError("manifest canonical article path must stay inside the run directory")
    if Path(manifest.request) != expected_request:
        raise ValueError("manifest request path must stay inside the run directory")
    for stage in manifest.stages.values():
        for artifact in stage.artifacts:
            path = Path(artifact)
            if not path.is_absolute() or path != expected_output / path.relative_to(expected_output):
                raise ValueError("manifest artifact path must stay inside the run directory")


def save_manifest(manifest: RunManifest) -> None:
    _validate_manifest_paths(manifest, Path(manifest.output_dir))
    manifest.updated_at = utc_now()
    atomic_write_json(_manifest_path(Path(manifest.output_dir)), manifest.to_dict())


def load_manifest(run_dir: Path) -> RunManifest:
    run_dir = _validated_run_dir(run_dir)
    value = safe_json_load(_manifest_path(run_dir))
    if not isinstance(value, dict):
        raise ValueError("run-manifest.json must contain an object")
    manifest = RunManifest.from_mapping(value)
    _validate_manifest_paths(manifest, run_dir)
    return manifest


def load_request(run_dir: Path) -> BlogWriteRequest:
    run_dir = _validated_run_dir(run_dir)
    value = safe_json_load(run_dir / "request.json")
    if not isinstance(value, dict):
        raise ValueError("request.json must contain an object")
    return BlogWriteRequest.from_mapping(value)


def create_run(request: BlogWriteRequest, output_root: Path = DEFAULT_OUTPUT_ROOT) -> tuple[Path, RunManifest]:
    output_root = output_root.absolute()
    assert_no_symlink_ancestors(output_root)
    if output_root.is_symlink():
        raise ValueError(f"refusing symlink output root: {output_root}")
    run_dir = output_root / request.slug
    run_dir.mkdir(parents=True, exist_ok=True)
    assert_no_symlink_ancestors(run_dir.parent)
    if run_dir.is_symlink():
        raise ValueError(f"refusing symlink run directory: {run_dir}")
    manifest_path = _manifest_path(run_dir)
    if manifest_path.exists():
        manifest = load_manifest(run_dir)
        existing_request = load_request(run_dir)
        if existing_request.to_dict() != request.to_dict():
            raise ValueError(
                f"run directory already contains a different normalized request: {run_dir}"
            )
        return run_dir, manifest
    manifest = RunManifest.create(request, run_dir)
    atomic_write_json(run_dir / "request.json", request.to_dict())
    save_manifest(manifest)
    return run_dir, manifest


def _copy_article(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve():
        return
    if source.is_symlink():
        raise ValueError(f"refusing symlink article source: {source}")
    if destination.is_symlink():
        raise ValueError(f"refusing symlink canonical article: {destination}")
    atomic_write_text(
        destination,
        safe_read_text(source, label="article source"),
    )


def _article_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _invalidate_article_dependents(manifest: RunManifest) -> None:
    for name, stage in manifest.stages.items():
        if name in {"core_article", "images"}:
            continue
        stage.status = "pending"
        stage.attempts = 0
        stage.artifacts = []
        stage.warning = ""
        stage.error = ""
    manifest.warnings = []


def _run_stage(
    manifest: RunManifest,
    name: str,
    action: Callable[[], list[Path]],
    *,
    attempts: int = 2,
    force: bool = False,
) -> None:
    result = manifest.stages.setdefault(name, StageResult(name))
    if not force:
        artifacts_exist = bool(result.artifacts) and all(
            Path(path).is_file() and not Path(path).is_symlink() for path in result.artifacts
        )
        if result.status == "complete" and artifacts_exist:
            return
        if result.status in {"degraded", "skipped"} and result.attempts >= attempts:
            return
    else:
        result.attempts = 0
    result.status = "pending"
    result.artifacts = []
    result.error = ""
    first_attempt = 1 if force else result.attempts + 1
    if first_attempt > attempts:
        result.status = "degraded"
        result.error = "artifact is missing after the allowed attempts were exhausted"
        save_manifest(manifest)
        return
    for attempt in range(first_attempt, attempts + 1):
        result.attempts = attempt
        try:
            artifacts = action()
            output_dir = Path(manifest.output_dir)
            for artifact in artifacts:
                if not artifact.is_absolute() or output_dir not in artifact.parents:
                    raise ValueError(f"stage artifact escaped the run directory: {artifact}")
            result.artifacts = [str(path) for path in artifacts]
            result.status = "complete"
            save_manifest(manifest)
            return
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            save_manifest(manifest)
    result.status = "degraded"
    warning = f"{name} skipped after {attempts} attempts: {result.error}"
    if warning not in manifest.warnings:
        manifest.warnings.append(warning)
    save_manifest(manifest)


def _render(run_dir: Path, article: Path, *, pdf: bool, hero: str | None = None) -> list[Path]:
    command = [
        sys.executable,
        str(PLUGIN_ROOT / "scripts" / "blog_render.py"),
        "--md",
        str(article),
        "--out-dir",
        str(run_dir),
        "--pdf-engine",
        "auto" if pdf else "none",
        "--json",
    ]
    if hero:
        command.extend(["--hero", hero])
    if pdf:
        command.extend(["--existing-html", str(run_dir / f"{article.stem}.html")])
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    payload: dict[str, str | None] = {}
    if result.stdout.strip():
        try:
            payload = json.loads(result.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            payload = {}
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "render failed")
    artifacts = [Path(value) for value in payload.values() if value]
    if not artifacts:
        raise RuntimeError("renderer reported no artifacts")
    return artifacts


def _seo_geo_report(article: Path, request: BlogWriteRequest, review: ArticleReview, destination: Path) -> list[Path]:
    fm, body = read_markdown(article)
    first_section = body[:1800].casefold()
    primary = request.primary_keyword.casefold()
    report = {
        "primary_keyword": request.primary_keyword,
        "keyword_in_title": primary in str(fm.get("title", "")).casefold(),
        "keyword_in_opening": primary in first_section,
        "keyword_in_slug": bool(request.slug),
        "heading_hierarchy": review.metrics.get("h1_count") == 1 and review.metrics.get("h2_count", 0) >= 2,
        "answer_first": bool(re.search(r"^##\s+.+\n\n?\S", body, re.MULTILINE)),
        "source_links": review.metrics.get("link_count", 0),
        "image_mode": request.image_mode,
        "visual_score": "not-applicable" if request.image_mode == "deferred" else "pending-image-check",
        "advisory_only": True,
    }
    atomic_write_json(destination, report)
    return [destination]


def _facts_links(article: Path, review: ArticleReview, destination: Path, *, external: bool) -> list[Path]:
    _, body = read_markdown(article)
    urls = list(dict.fromkeys(re.findall(r"https?://[^\s)>\]]+", body)))
    link_results = check_links(urls) if external else []
    report = {
        "numeric_claim_lines_without_url": review.metrics.get("numeric_claim_lines_without_url", 0),
        "external_check_enabled": external,
        "links": [item.to_dict() for item in link_results],
        "unreachable": [item.url for item in link_results if not item.ok],
        "policy": "Known false claims must be corrected or removed. Unverifiable claims must be qualitative or omitted.",
    }
    atomic_write_json(destination, report)
    if any(not item.ok for item in link_results):
        raise RuntimeError(f"{sum(not item.ok for item in link_results)} external link(s) could not be verified")
    return [destination]


def finalize_run(
    run_dir: Path,
    *,
    article_source: Path | None = None,
    project_root: Path | None = None,
    check_external_links: bool = True,
    claim_image_question: bool = False,
) -> RunManifest:
    manifest = load_manifest(run_dir)
    request = load_request(run_dir)
    if manifest.request_digest != request.digest():
        raise ValueError("request.json checksum does not match the run manifest")
    canonical = Path(manifest.article)
    if article_source:
        _copy_article(article_source, canonical)
    if canonical.is_symlink():
        raise CoreArticleError(
            f"canonical article must not be a symlink: {canonical}", blocked=True, attempts=0
        )
    if not canonical.is_file():
        raise CoreArticleError(
            f"canonical article is missing: {canonical}", blocked=False, attempts=0
        )
    review = review_article(canonical, request)
    core = manifest.stages.setdefault("core_article", StageResult("core_article"))
    if not review.complete:
        core.attempts = min(3, core.attempts + 1)
        exhausted = core.attempts >= 3
        core.status = "blocked" if exhausted else "pending"
        core.error = "; ".join(review.errors)
        manifest.status = "blocked" if exhausted else "awaiting_article"
        manifest.warnings.extend(
            warning for warning in review.warnings if warning not in manifest.warnings
        )
        save_manifest(manifest)
        write_review(run_dir / "review.md", review, {name: stage.to_dict() for name, stage in manifest.stages.items()})
        raise CoreArticleError(core.error, blocked=exhausted, attempts=core.attempts)
    digest = _article_digest(canonical)
    if manifest.article_digest and manifest.article_digest != digest:
        _invalidate_article_dependents(manifest)
    manifest.article_digest = digest
    if core.status != "complete":
        core.attempts = min(3, core.attempts + 1)
    else:
        core.attempts = max(core.attempts, 1)
    core.status = "complete"
    core.error = ""
    core.artifacts = [str(canonical)]
    manifest.status = "enhancing"
    manifest.warnings.extend(item for item in review.warnings if item not in manifest.warnings)
    save_manifest(manifest)

    _run_stage(manifest, "schema", lambda: [write_schema(canonical, request, run_dir / "schema.json")])
    _run_stage(manifest, "html", lambda: _render(run_dir, canonical, pdf=False))
    _run_stage(manifest, "pdf", lambda: [path for path in _render(run_dir, canonical, pdf=True) if path.suffix == ".pdf"] or (_ for _ in ()).throw(RuntimeError("PDF not produced")))
    _run_stage(
        manifest,
        "seo_geo",
        lambda: _seo_geo_report(canonical, request, review, run_dir / "seo-geo-report.json"),
    )
    _run_stage(
        manifest,
        "facts_links",
        lambda: _facts_links(canonical, review, run_dir / "facts-links-report.json", external=check_external_links),
    )
    root = project_root or Path.cwd()
    _run_stage(
        manifest,
        "platform",
        lambda: adapt_platform(canonical, root, run_dir),
    )
    if request.image_mode == "deferred":
        manifest.image_status = "not_requested"
        images = manifest.stages.setdefault("images", StageResult("images"))
        images.status = "skipped"
        images.warning = "Visual generation is deferred until the user explicitly opts in."
        if claim_image_question and manifest.image_decision == "not_asked":
            manifest.image_decision = "asked"
    failed = [
        stage
        for name, stage in manifest.stages.items()
        if name not in {"images", "report"} and stage.status in {"degraded", "skipped"}
    ]
    manifest.status = "complete_with_warnings" if failed or manifest.warnings else "complete"
    _run_stage(
        manifest,
        "report",
        lambda: _write_reports(run_dir, review, manifest),
    )
    failed = [
        stage
        for name, stage in manifest.stages.items()
        if name != "images" and stage.status in {"degraded", "skipped"}
    ]
    manifest.status = "complete_with_warnings" if failed or manifest.warnings else "complete"
    save_manifest(manifest)
    return manifest


def _write_reports(run_dir: Path, review: ArticleReview, manifest: RunManifest) -> list[Path]:
    review_path = run_dir / "review.md"
    preflight_path = run_dir / "preflight-report.json"
    stage_summary = {name: stage.to_dict() for name, stage in manifest.stages.items()}
    if stage_summary.get("report", {}).get("status") == "pending":
        stage_summary["report"]["status"] = "complete"
    write_review(review_path, review, stage_summary)
    atomic_write_json(
        preflight_path,
        {
            "schema_version": 1,
            "core_complete": review.complete,
            "delivery_blocked": not review.complete,
            "status": manifest.status,
            "stages": stage_summary,
            "warnings": manifest.warnings,
            "images": {
                "mode": manifest.image_mode,
                "status": manifest.image_status,
                "decision": manifest.image_decision,
                "prompt_required": manifest.image_decision == "not_asked",
            },
        },
    )
    return [review_path, preflight_path]
