from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .adapters import load_cluster_plan, normalize_request
from .images import create_image_plan, decline_images
from .pipeline import CoreArticleError, create_run, finalize_run, load_manifest
from .utils import (
    assert_no_symlink_ancestors,
    atomic_write_json,
    safe_json_load,
    slugify,
    utc_now,
)

MANIFEST_NAME = "cluster-run-manifest.json"
TERMINAL_ITEM_STATES = {"non_image_complete", "blocked", "failed"}
TERMINAL_STAGE_STATES = {"complete", "degraded", "skipped"}


def _plan_digest(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_plan(path: Path) -> dict[str, Any]:
    value = safe_json_load(path)
    if not isinstance(value, dict):
        raise ValueError("cluster plan must be a JSON object")
    if not isinstance(value.get("pillar"), dict):
        raise ValueError("canonical cluster plan must contain one pillar object")
    if not isinstance(value.get("clusters", []), list):
        raise ValueError("canonical cluster plan clusters must be an array")
    return value


def _node_ids(value: dict[str, Any]) -> list[tuple[str, str, str]]:
    nodes = [("pillar", "pillar", "")]
    for cluster_index, group in enumerate(value.get("clusters", [])):
        if not isinstance(group, dict):
            raise ValueError(f"cluster {cluster_index} must be an object")
        posts = group.get("posts", [])
        if not isinstance(posts, list):
            raise ValueError(f"cluster {cluster_index} posts must be an array")
        for post_index, post in enumerate(posts):
            if not isinstance(post, dict):
                raise ValueError(
                    f"cluster {cluster_index} post {post_index} must be an object"
                )
            nodes.append(
                (
                    f"cluster-{cluster_index}-post-{post_index}",
                    "spoke",
                    str(group.get("name", "")).strip(),
                )
            )
    return nodes


def _manifest_path(path: Path) -> Path:
    absolute = path.absolute()
    return absolute / MANIFEST_NAME if absolute.is_dir() else absolute


def _validate_manifest_paths(manifest: dict[str, Any], path: Path) -> None:
    batch_dir = path.parent.absolute()
    assert_no_symlink_ancestors(batch_dir)
    if batch_dir.is_symlink() or not batch_dir.is_dir():
        raise ValueError(f"cluster output directory must be a regular directory: {batch_dir}")
    if Path(str(manifest.get("output_dir", ""))) != batch_dir:
        raise ValueError("cluster manifest output_dir must exactly match its directory")
    if Path(str(manifest.get("plan", ""))) != batch_dir / "cluster-plan.json":
        raise ValueError("cluster manifest plan must stay inside its output directory")
    articles_root = batch_dir / "articles"
    assert_no_symlink_ancestors(articles_root)
    if articles_root.is_symlink() or not articles_root.is_dir():
        raise ValueError("cluster articles directory must be a regular directory")
    articles = manifest.get("articles", [])
    if not isinstance(articles, list) or not articles:
        raise ValueError("cluster manifest must contain at least one article")
    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()
    for item in articles:
        if not isinstance(item, dict):
            raise ValueError("cluster article entries must be objects")
        node_id = str(item.get("id", ""))
        slug = str(item.get("slug", ""))
        if not node_id or node_id in seen_ids:
            raise ValueError(f"cluster article ID is missing or duplicated: {node_id}")
        if not slug or slug != slugify(slug) or slug in seen_slugs:
            raise ValueError(f"cluster article slug is invalid or duplicated: {slug}")
        seen_ids.add(node_id)
        seen_slugs.add(slug)
        expected_run = articles_root / slug
        assert_no_symlink_ancestors(expected_run)
        expected_article = expected_run / f"{slug}.md"
        expected_request = expected_run / "request.json"
        if Path(str(item.get("run_dir", ""))) != expected_run:
            raise ValueError("cluster article run directory escaped the controlled batch path")
        if Path(str(item.get("article", ""))) != expected_article:
            raise ValueError("cluster article path escaped its controlled run directory")
        if Path(str(item.get("request", ""))) != expected_request:
            raise ValueError("cluster request path escaped its controlled run directory")
        if expected_run.is_symlink() or not expected_run.is_dir():
            raise ValueError(f"cluster article run directory is not regular: {expected_run}")


def _save_cluster_manifest(manifest: dict[str, Any]) -> None:
    path = Path(str(manifest["output_dir"])) / MANIFEST_NAME
    manifest["updated_at"] = utc_now()
    _validate_manifest_paths(manifest, path)
    atomic_write_json(path, manifest)


def load_cluster_manifest(path: Path) -> dict[str, Any]:
    manifest_path = _manifest_path(path)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError(f"cluster manifest must be a regular file: {manifest_path}")
    value = safe_json_load(manifest_path)
    if not isinstance(value, dict):
        raise ValueError("cluster manifest must contain an object")
    if int(value.get("schema_version", 0)) != 1:
        raise ValueError("unsupported cluster manifest schema_version")
    _validate_manifest_paths(value, manifest_path)
    snapshot = _read_plan(Path(str(value["plan"])))
    if str(value.get("plan_digest", "")) != _plan_digest(snapshot):
        raise ValueError("cluster plan snapshot checksum does not match the manifest")
    return value


def _sync_article(item: dict[str, Any]) -> None:
    run = load_manifest(Path(str(item["run_dir"])))
    core = run.stages.get("core_article")
    if item.get("status") == "failed" and int(item.get("finalize_attempts", 0)) >= 2:
        pass
    elif core and core.status == "complete":
        incomplete = [
            stage
            for name, stage in run.stages.items()
            if name != "images" and stage.status not in TERMINAL_STAGE_STATES
        ]
        item["status"] = "non_image_complete" if not incomplete else "ready_to_finalize"
        if not incomplete:
            item["error"] = ""
    elif core and core.status == "blocked":
        item["status"] = "blocked"
        item["error"] = core.error
    elif Path(str(item["article"])).is_file():
        item["status"] = "ready_to_finalize"
    else:
        item["status"] = "awaiting_article"
    run_image_status = run.image_status
    if run_image_status in {
        "planned",
        "complete",
        "degraded",
    } or item.get("image_status") not in {"planned", "degraded"}:
        item["image_status"] = run_image_status


def _sync_cluster(manifest: dict[str, Any]) -> None:
    for item in manifest["articles"]:
        try:
            _sync_article(item)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            if item.get("status") != "failed":
                item["status"] = "ready_to_finalize"
            item["error"] = f"child run unavailable: {type(exc).__name__}: {exc}"


def _all_terminal(manifest: dict[str, Any]) -> bool:
    return all(
        str(item.get("status", "")) in TERMINAL_ITEM_STATES
        for item in manifest["articles"]
    )


def _has_article_failures(manifest: dict[str, Any]) -> bool:
    return any(
        str(item.get("status", "")) in {"blocked", "failed"}
        for item in manifest["articles"]
    )


def _set_batch_status(manifest: dict[str, Any]) -> None:
    if not _all_terminal(manifest):
        manifest["status"] = "awaiting_articles"
    elif manifest["image_decision"] in {"hero", "full"}:
        successful = [
            item
            for item in manifest["articles"]
            if item["status"] == "non_image_complete"
        ]
        image_terminal = all(
            item["image_status"] in {"complete", "degraded"}
            for item in successful
        )
        image_degraded = any(
            item["image_status"] == "degraded" for item in successful
        )
        if image_terminal:
            manifest["status"] = (
                "complete_with_warnings"
                if _has_article_failures(manifest)
                or manifest["warnings"]
                or image_degraded
                else "complete"
            )
        else:
            manifest["status"] = "images_planned"
    elif _has_article_failures(manifest) or manifest["warnings"]:
        manifest["status"] = "complete_with_warnings"
    elif manifest["image_decision"] == "declined":
        manifest["status"] = "complete"
    else:
        manifest["status"] = "non_image_complete"


def prepare_cluster(
    plan_path: Path,
    output_root: Path,
    *,
    image_mode: str = "deferred",
    language: str = "",
    site_context: dict[str, str] | None = None,
    brand_voice: dict[str, str] | None = None,
) -> dict[str, Any]:
    if image_mode not in {"deferred", "hero", "full"}:
        raise ValueError("cluster image mode must be deferred, hero, or full")
    source_plan = _read_plan(plan_path)
    nodes = _node_ids(source_plan)
    seed = str(source_plan.get("seed_keyword", "")).strip()
    pillar = source_plan["pillar"]
    seed = seed or str(pillar.get("keyword", pillar.get("title", ""))).strip()
    if not seed:
        raise ValueError("cluster plan must provide seed_keyword or a pillar keyword")
    requested_language = language or str(source_plan.get("language", ""))
    prepared: list[tuple[str, str, str, Any]] = []
    slugs: set[str] = set()
    keywords: set[str] = set()
    for node_id, role, group in nodes:
        packet = load_cluster_plan(plan_path, post_id=node_id)
        request = normalize_request(
            explicit={"language": requested_language, "image_mode": "deferred"},
            cluster=packet,
            site_context=site_context or {},
            brand_voice=brand_voice or {},
        )
        keyword_key = request.primary_keyword.casefold()
        if not request.primary_keyword or keyword_key in keywords:
            raise ValueError(
                f"cluster primary keyword is missing or duplicated: {request.primary_keyword}"
            )
        if request.slug in slugs:
            raise ValueError(f"cluster slug is duplicated: {request.slug}")
        keywords.add(keyword_key)
        slugs.add(request.slug)
        prepared.append((node_id, role, group, request))
    root = output_root.absolute()
    assert_no_symlink_ancestors(root)
    root.mkdir(parents=True, exist_ok=True)
    assert_no_symlink_ancestors(root)
    batch_dir = root / "clusters" / slugify(seed)
    assert_no_symlink_ancestors(batch_dir)
    batch_dir.mkdir(parents=True, exist_ok=True)
    assert_no_symlink_ancestors(batch_dir)
    articles_root = batch_dir / "articles"
    assert_no_symlink_ancestors(articles_root)
    articles_root.mkdir(exist_ok=True)
    assert_no_symlink_ancestors(articles_root)
    digest = _plan_digest(source_plan)
    manifest_path = batch_dir / MANIFEST_NAME
    snapshot = batch_dir / "cluster-plan.json"
    if manifest_path.is_file():
        manifest = load_cluster_manifest(manifest_path)
        if manifest["plan_digest"] != digest:
            raise ValueError("existing cluster batch was created from a different plan")
        if manifest["image_mode"] != image_mode:
            raise ValueError("existing cluster batch uses a different image mode")
        _sync_cluster(manifest)
        _set_batch_status(manifest)
        _save_cluster_manifest(manifest)
        return manifest
    if manifest_path.is_symlink():
        raise ValueError(f"refusing symlink cluster manifest: {manifest_path}")
    if snapshot.is_file() and _plan_digest(_read_plan(snapshot)) != digest:
        raise ValueError("existing cluster plan snapshot differs from the requested plan")
    atomic_write_json(snapshot, source_plan)
    records: list[dict[str, Any]] = []
    for position, (node_id, role, group, request) in enumerate(prepared, 1):
        run_dir, run_manifest = create_run(request, articles_root)
        records.append(
            {
                "id": node_id,
                "role": role,
                "cluster": group,
                "position": position,
                "title": request.topic,
                "primary_keyword": request.primary_keyword,
                "slug": request.slug,
                "run_dir": str(run_dir),
                "article": run_manifest.article,
                "request": run_manifest.request,
                "status": "awaiting_article",
                "finalize_attempts": 0,
                "image_status": "not_requested",
                "image_attempts": 0,
                "error": "",
            }
        )
    timestamp = utc_now()
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "batch_id": slugify(seed),
        "seed_keyword": seed,
        "status": "awaiting_articles",
        "output_dir": str(batch_dir),
        "plan": str(snapshot),
        "plan_digest": digest,
        "image_mode": image_mode,
        "image_decision": "not_asked" if image_mode == "deferred" else image_mode,
        "articles": records,
        "warnings": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    _sync_cluster(manifest)
    _set_batch_status(manifest)
    _save_cluster_manifest(manifest)
    return manifest


def cluster_status(path: Path) -> dict[str, Any]:
    manifest = load_cluster_manifest(path)
    _sync_cluster(manifest)
    _set_batch_status(manifest)
    return manifest


def _plan_batch_images(manifest: dict[str, Any], scope: str) -> None:
    for item in manifest["articles"]:
        if (
            item["status"] != "non_image_complete"
            or item["image_status"] == "planned"
            or int(item.get("image_attempts", 0)) >= 2
        ):
            continue
        item["image_attempts"] = int(item.get("image_attempts", 0)) + 1
        try:
            create_image_plan(Path(item["run_dir"]), scope)
            item["image_status"] = "planned"
        except Exception as exc:
            item["image_status"] = "degraded"
            item["error"] = f"image planning failed: {type(exc).__name__}: {exc}"
            warning = f"{item['id']}: {item['error']}"
            if warning not in manifest["warnings"]:
                manifest["warnings"].append(warning)


def finalize_cluster(
    path: Path,
    *,
    project_root: Path | None = None,
    check_external_links: bool = True,
    image_mode: str | None = None,
) -> tuple[dict[str, Any], bool]:
    if image_mode is not None and image_mode not in {"hero", "full"}:
        raise ValueError("selected cluster image mode must be hero or full")
    manifest = load_cluster_manifest(path)
    if image_mode:
        manifest["image_mode"] = image_mode
        manifest["image_decision"] = image_mode
    _sync_cluster(manifest)
    for item in manifest["articles"]:
        if item["status"] in TERMINAL_ITEM_STATES:
            continue
        article = Path(item["article"])
        if article.is_symlink():
            raise ValueError(f"refusing symlink cluster article: {article}")
        if not article.is_file():
            item["status"] = "awaiting_article"
            item["error"] = "article is missing"
            continue
        try:
            finalize_run(
                Path(item["run_dir"]),
                project_root=(project_root or Path.cwd()).resolve(),
                check_external_links=check_external_links,
                claim_image_question=False,
            )
            item["finalize_attempts"] = int(item.get("finalize_attempts", 0)) + 1
            _sync_article(item)
        except CoreArticleError as exc:
            item["finalize_attempts"] = max(
                int(item.get("finalize_attempts", 0)), exc.attempts
            )
            item["status"] = "blocked" if exc.blocked else "ready_to_finalize"
            item["error"] = str(exc)
        except Exception as exc:
            attempts = int(item.get("finalize_attempts", 0)) + 1
            item["finalize_attempts"] = attempts
            item["status"] = "failed" if attempts >= 2 else "ready_to_finalize"
            item["error"] = f"{type(exc).__name__}: {exc}"
            warning = f"{item['id']} finalize attempt {attempts} failed: {item['error']}"
            if warning not in manifest["warnings"]:
                manifest["warnings"].append(warning)
    _sync_cluster(manifest)
    prompt_required = False
    if _all_terminal(manifest):
        if manifest["image_mode"] == "deferred":
            if manifest["image_decision"] == "not_asked":
                manifest["image_decision"] = "asked"
                prompt_required = True
        else:
            _plan_batch_images(manifest, str(manifest["image_mode"]))
    _set_batch_status(manifest)
    _save_cluster_manifest(manifest)
    return manifest, prompt_required


def decline_cluster_images(path: Path) -> dict[str, Any]:
    manifest = load_cluster_manifest(path)
    _sync_cluster(manifest)
    if not _all_terminal(manifest):
        raise ValueError("batch images may be declined only after every article is terminal")
    for item in manifest["articles"]:
        if item["status"] != "non_image_complete":
            continue
        try:
            decline_images(Path(item["run_dir"]))
            item["image_status"] = "not_requested"
        except Exception as exc:
            item["image_status"] = "degraded"
            item["error"] = f"image decline failed: {type(exc).__name__}: {exc}"
            warning = f"{item['id']}: {item['error']}"
            if warning not in manifest["warnings"]:
                manifest["warnings"].append(warning)
    manifest["image_mode"] = "deferred"
    manifest["image_decision"] = "declined"
    _set_batch_status(manifest)
    _save_cluster_manifest(manifest)
    return manifest
