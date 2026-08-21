from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

from .frontmatter import dump_markdown, read_markdown
from .links import request_bytes
from .models import RunManifest, StageResult
from .utils import (
    assert_no_symlink_ancestors,
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    safe_json_load,
    slugify,
)

MAX_IMAGE_BYTES = 24 * 1024 * 1024
KINDS = {"openai-compatible", "gemini-compatible"}


def image_config_path() -> Path:
    explicit = os.environ.get("CODEX_BLOG_IMAGE_CONFIG")
    if explicit:
        return Path(explicit).expanduser().absolute()
    data_dir = os.environ.get("CODEX_BLOG_DATA_DIR")
    if data_dir:
        return Path(data_dir).expanduser().absolute() / "config.json"
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    return codex_home.absolute() / "codex-blog" / "config.json"


def load_config(_project_root: Path, *, config_path: Path | None = None) -> dict[str, Any]:
    path = (config_path or image_config_path()).expanduser().absolute()
    if not path.is_file():
        return {"images": {"providers": []}}
    if path.is_symlink():
        raise ValueError(f"refusing symlink image provider config: {path}")
    value = safe_json_load(path, max_bytes=512 * 1024)
    if not isinstance(value, dict):
        raise ValueError("image provider config must contain an object")
    return value


def _provider_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("image provider base_url must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("credentials are forbidden in image provider URLs")
    if parsed.query or parsed.fragment:
        raise ValueError("image provider base_url must not contain a query or fragment")
    return value.rstrip("/")


def _request_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    raw, _response_headers = request_bytes(
        url,
        method="POST",
        body=body,
        headers={"Content-Type": "application/json", "Accept": "application/json", **headers},
        timeout=timeout,
        max_bytes=8 * 1024 * 1024,
    )
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("image provider response must be a JSON object")
    return value


def _download_same_origin(url: str, base_url: str, timeout: float) -> bytes:
    target = urllib.parse.urlparse(url)
    base = urllib.parse.urlparse(base_url)
    if (
        target.scheme not in {"http", "https"}
        or target.scheme != base.scheme
        or target.hostname != base.hostname
        or target.port != base.port
        or target.username
        or target.password
    ):
        raise ValueError("provider image URL must use the configured provider host; request base64 instead")
    data, _headers = request_bytes(
        url,
        method="GET",
        headers={"User-Agent": "codex-blog/2.1.2"},
        timeout=timeout,
        max_bytes=MAX_IMAGE_BYTES,
    )
    return data


def _decode_data(value: str) -> bytes:
    try:
        data = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise ValueError("provider returned invalid base64 image data") from exc
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("generated image is too large")
    return data


def _openai_generate(provider: dict[str, Any], prompt: str) -> tuple[bytes, str]:
    base_url = _provider_url(str(provider["base_url"]))
    endpoint = base_url if base_url.endswith("/images/generations") else f"{base_url}/images/generations"
    env_name = str(provider.get("api_key_env", "OPENAI_API_KEY"))
    _validate_image_credential_env(env_name, base_url, "openai-compatible")
    key = os.environ.get(env_name)
    if not key:
        raise RuntimeError(f"required environment variable is not set: {env_name}")
    timeout = float(provider.get("timeout_seconds", 90))
    payload = {
        "model": str(provider.get("model", "gpt-image-1")),
        "prompt": prompt,
        "size": str(provider.get("size", "1536x1024")),
        "n": 1,
        "response_format": "b64_json",
    }
    response = _request_json(endpoint, payload, {"Authorization": f"Bearer {key}"}, timeout)
    items = response.get("data")
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise ValueError("OpenAI-compatible response has no image data")
    item = items[0]
    if item.get("b64_json"):
        return _decode_data(str(item["b64_json"])), "image/png"
    if item.get("url"):
        return _download_same_origin(str(item["url"]), base_url, timeout), "image/png"
    raise ValueError("OpenAI-compatible response has neither b64_json nor url")


def _gemini_generate(provider: dict[str, Any], prompt: str) -> tuple[bytes, str]:
    base_url = _provider_url(str(provider["base_url"]))
    model = str(provider.get("model", "gemini-3.1-flash-image"))
    endpoint = base_url if ":generateContent" in base_url else f"{base_url}/models/{urllib.parse.quote(model, safe='-_.')}:generateContent"
    env_name = str(provider.get("api_key_env", "GEMINI_API_KEY"))
    _validate_image_credential_env(env_name, base_url, "gemini-compatible")
    key = os.environ.get(env_name)
    if not key:
        raise RuntimeError(f"required environment variable is not set: {env_name}")
    timeout = float(provider.get("timeout_seconds", 90))
    response = _request_json(
        endpoint,
        {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        },
        {"x-goog-api-key": key},
        timeout,
    )
    for candidate in response.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content", {})
        if not isinstance(content, dict):
            continue
        for part in content.get("parts", []):
            if not isinstance(part, dict):
                continue
            inline = part.get("inlineData", part.get("inline_data"))
            if isinstance(inline, dict) and inline.get("data"):
                return _decode_data(str(inline["data"])), str(inline.get("mimeType", inline.get("mime_type", "image/png")))
    raise ValueError("Gemini-compatible response has no inline image data")


def generate_with_provider(provider: dict[str, Any], prompt: str) -> tuple[bytes, str]:
    kind = str(provider.get("kind", ""))
    if kind not in KINDS:
        raise ValueError(f"unsupported image provider kind: {kind}")
    if kind == "openai-compatible":
        return _openai_generate(provider, prompt)
    return _gemini_generate(provider, prompt)


def _validate_image_credential_env(name: str, base_url: str, kind: str) -> None:
    hostname = (urllib.parse.urlparse(base_url).hostname or "").casefold()
    official = {
        "openai-compatible": ("OPENAI_API_KEY", {"api.openai.com"}),
        "gemini-compatible": (
            "GEMINI_API_KEY",
            {"generativelanguage.googleapis.com"},
        ),
    }
    official_env, official_hosts = official[kind]
    if name == official_env and hostname in official_hosts:
        return
    if re.fullmatch(r"CODEX_BLOG_IMAGE_[A-Z0-9_]+", name):
        return
    if name in {"OPENAI_API_KEY", "GEMINI_API_KEY"}:
        raise ValueError(
            "custom provider endpoints require a dedicated CODEX_BLOG_IMAGE_* credential"
        )
    raise ValueError(
        "api_key_env must name a dedicated image credential (OPENAI_API_KEY, "
        "GEMINI_API_KEY, or CODEX_BLOG_IMAGE_*)"
    )


def _extension(data: bytes, mime_type: str = "") -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    raise ValueError("unsupported generated image format")


def _dimensions(data: bytes) -> tuple[int | None, int | None]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data.startswith(b"\xff\xd8\xff"):
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue
            if offset + 2 > len(data):
                break
            length = int.from_bytes(data[offset : offset + 2], "big")
            if length < 2 or offset + length > len(data):
                break
            if marker in {
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            } and length >= 7:
                return (
                    int.from_bytes(data[offset + 5 : offset + 7], "big"),
                    int.from_bytes(data[offset + 3 : offset + 5], "big"),
                )
            offset += length
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP" and len(data) >= 30:
        if data[12:16] == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width, height
    return None, None


def _redact_error(error: Exception | str) -> str:
    text = str(error)
    text = re.sub(
        r"(?i)([?&](?:api[_-]?key|key|token|secret|access_token)=)[^&#\s]+",
        r"\1[REDACTED]",
        text,
    )
    text = re.sub(r"(?i)\b(?:bearer|basic)\s+\S+", "[REDACTED]", text)
    for name, value in os.environ.items():
        if not value or len(value) < 4:
            continue
        if name in {"OPENAI_API_KEY", "GEMINI_API_KEY"} or name.startswith(
            "CODEX_BLOG_IMAGE_"
        ):
            text = text.replace(value, "[REDACTED]")
    return text[:2_000]


def _require_non_image_complete(manifest: RunManifest) -> None:
    terminal = {"complete", "degraded", "skipped"}
    core = manifest.stages.get("core_article")
    incomplete = [
        name
        for name, stage in manifest.stages.items()
        if name != "images" and stage.status not in terminal
    ]
    if not core or core.status != "complete" or incomplete or manifest.status not in {
        "complete",
        "complete_with_warnings",
    }:
        raise ValueError(
            "image work may start only after the core article and all non-image stages are complete"
        )


def create_image_plan(run_dir: Path, scope: str) -> dict[str, Any]:
    from .pipeline import load_manifest, load_request, save_manifest

    if scope not in {"hero", "full"}:
        raise ValueError("image scope must be hero or full")
    manifest = load_manifest(run_dir)
    _require_non_image_complete(manifest)
    request = load_request(run_dir)
    _, body = read_markdown(Path(manifest.article))
    headings = [re.sub(r"^##\s+", "", line).strip() for line in body.splitlines() if line.startswith("## ")]
    items: list[dict[str, str]] = [
        {
            "id": "hero",
            "role": "hero",
            "prompt": f"Editorial blog hero for {request.topic}. Clear focal subject, wide 1200:630 composition, no text, no logos.",
            "alt": f"Editorial illustration for {request.primary_keyword or request.topic}",
        }
    ]
    if scope == "full":
        for index, heading in enumerate(headings[:3], 1):
            items.append(
                {
                    "id": f"inline-{index}",
                    "role": "inline",
                    "heading": heading,
                    "prompt": f"Editorial inline illustration explaining {heading} in an article about {request.topic}. No text, no logos.",
                    "alt": f"Illustration explaining {heading}",
                }
            )
    plan = {
        "schema_version": 1,
        "scope": scope,
        "provider_order": ["codex-native", "configured-api", "mcp"],
        "items": items,
    }
    atomic_write_json(run_dir / "image-plan.json", plan)
    request.image_mode = scope  # type: ignore[assignment]
    atomic_write_json(run_dir / "request.json", request.to_dict())
    manifest.image_mode = scope  # type: ignore[assignment]
    manifest.image_status = "planned"
    manifest.image_decision = scope  # type: ignore[assignment]
    manifest.request_digest = request.digest()
    images = manifest.stages.setdefault("images", StageResult("images"))
    images.status = "pending"
    images.warning = ""
    save_manifest(manifest)
    return plan


def decline_images(run_dir: Path) -> RunManifest:
    from .pipeline import load_manifest, save_manifest

    manifest = load_manifest(run_dir)
    _require_non_image_complete(manifest)
    manifest.image_decision = "declined"
    manifest.image_status = "not_requested"
    images = manifest.stages.setdefault("images", StageResult("images"))
    images.status = "skipped"
    images.warning = "The user declined optional image generation."
    save_manifest(manifest)
    return manifest


def _copy_valid_image(source: Path, destination_stem: Path) -> Path:
    assert_no_symlink_ancestors(source)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"image source must be a regular file: {source}")
    if source.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError("generated image is too large")
    data = source.read_bytes()
    suffix = _extension(data, source.suffix)
    destination = destination_stem.with_suffix(suffix)
    if destination.parent.is_symlink():
        raise ValueError(f"refusing symlink image directory: {destination.parent}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise ValueError(f"refusing to overwrite symlink: {destination}")
    atomic_write_bytes(destination, data)
    return destination


def attach_image(
    run_dir: Path,
    source: Path,
    role: str,
    *,
    heading: str = "",
    alt: str = "",
    provider: str = "external-attach",
    model: str = "",
    prompt: str = "",
) -> Path:
    from .pipeline import load_manifest, save_manifest

    if role not in {"hero", "inline"}:
        raise ValueError("image role must be hero or inline")
    manifest = load_manifest(run_dir)
    _require_non_image_complete(manifest)
    images_dir = run_dir / "images"
    if images_dir.is_symlink():
        raise ValueError(f"refusing symlink image directory: {images_dir}")
    existing = list(images_dir.glob("inline-*")) if images_dir.exists() else []
    item_id = "hero" if role == "hero" else f"inline-{len(existing) + 1}"
    stem = images_dir / item_id
    destination = _copy_valid_image(source, stem)
    article = Path(manifest.article)
    fm, body = read_markdown(article)
    relative = destination.relative_to(run_dir).as_posix()
    if role == "hero":
        fm["image"] = relative
        fm["og_image"] = relative
        fm["og_image_alt"] = alt or str(fm.get("title", manifest.topic))
    else:
        markdown = f"![{alt or heading or manifest.topic}]({relative})"
        if heading:
            pattern = re.compile(rf"(^##\s+{re.escape(heading)}\s*$)", re.MULTILINE)
            if pattern.search(body):
                body = pattern.sub(rf"\1\n\n{markdown}", body, count=1)
            else:
                body = body.rstrip() + "\n\n" + markdown + "\n"
        else:
            body = body.rstrip() + "\n\n" + markdown + "\n"
    atomic_write_text(article, dump_markdown(fm, body))
    manifest = load_manifest(run_dir)
    if not prompt:
        plan_path = run_dir / "image-plan.json"
        if plan_path.is_file():
            plan = safe_json_load(plan_path)
            if isinstance(plan, dict):
                planned = next(
                    (
                        item
                        for item in plan.get("items", [])
                        if isinstance(item, dict) and str(item.get("id")) == item_id
                    ),
                    {},
                )
                prompt = str(planned.get("prompt", ""))
                alt = alt or str(planned.get("alt", ""))
    data = destination.read_bytes()
    width, height = _dimensions(data)
    asset = {
        "id": item_id,
        "role": role,
        "path": relative,
        "provider": provider,
        "model": model,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if prompt
        else "",
        "width": width,
        "height": height,
        "alt": alt or heading or manifest.topic,
    }
    manifest.image_assets = [
        item for item in manifest.image_assets if item.get("id") != item_id
    ] + [asset]
    manifest.article_digest = hashlib.sha256(article.read_bytes()).hexdigest()
    images = manifest.stages.setdefault("images", StageResult("images"))
    if str(destination) not in images.artifacts:
        images.artifacts.append(str(destination))
    images.status = "pending"
    manifest.image_status = "planned"
    save_manifest(manifest)
    return destination


def _reset_stages(manifest: RunManifest, names: tuple[str, ...]) -> None:
    for name in names:
        stage = manifest.stages.setdefault(name, StageResult(name))
        stage.status = "pending"
        stage.attempts = 0
        stage.artifacts = []
        stage.warning = ""
        stage.error = ""


def _finish_status(manifest: RunManifest) -> None:
    degraded = any(
        stage.status in {"degraded", "skipped"}
        for name, stage in manifest.stages.items()
        if not (name == "images" and manifest.image_decision in {"not_asked", "asked", "declined"})
    )
    manifest.status = (
        "complete_with_warnings" if degraded or manifest.warnings else "complete"
    )


def refresh_image_outputs(
    run_dir: Path, project_root: Path | None = None
) -> RunManifest:
    from .article import review_article, write_schema
    from .pipeline import (
        _render,
        _run_stage,
        _write_reports,
        load_manifest,
        load_request,
        save_manifest,
    )
    from .platforms import adapt_platform

    manifest = load_manifest(run_dir)
    _require_non_image_complete(manifest)
    request = load_request(run_dir)
    images_dir = run_dir / "images"
    generated = sorted(path for path in images_dir.glob("*") if path.is_file()) if images_dir.is_dir() else []
    plan = safe_json_load(run_dir / "image-plan.json") if (run_dir / "image-plan.json").is_file() else {"items": []}
    expected = len(plan.get("items", [])) if isinstance(plan, dict) else 0
    images = manifest.stages.setdefault("images", StageResult("images"))
    images.artifacts = [str(path) for path in generated]
    if generated and (not expected or len(generated) >= expected):
        images.status = "complete"
        manifest.image_status = "complete"
    elif generated:
        images.status = "degraded"
        images.error = f"attached {len(generated)} of {expected} planned images"
        manifest.image_status = "degraded"
    else:
        images.status = "degraded"
        images.error = "no image files are attached"
        manifest.image_status = "degraded"
    images.attempts = max(1, min(2, images.attempts or 1))
    manifest.article_digest = hashlib.sha256(Path(manifest.article).read_bytes()).hexdigest()
    _reset_stages(manifest, ("schema", "html", "pdf", "platform", "report"))
    save_manifest(manifest)
    hero = next((path for path in generated if path.stem == "hero"), None)
    hero_reference = hero.relative_to(run_dir).as_posix() if hero else None
    _run_stage(manifest, "schema", lambda: [write_schema(Path(manifest.article), request, run_dir / "schema.json")])
    _run_stage(manifest, "html", lambda: _render(run_dir, Path(manifest.article), pdf=False, hero=hero_reference))

    def render_pdf() -> list[Path]:
        if manifest.stages["html"].status != "complete":
            raise RuntimeError("PDF refresh requires refreshed HTML")
        return [
            path
            for path in _render(
                run_dir, Path(manifest.article), pdf=True, hero=hero_reference
            )
            if path.suffix == ".pdf"
        ] or (_ for _ in ()).throw(RuntimeError("PDF not produced"))

    _run_stage(manifest, "pdf", render_pdf)
    _run_stage(
        manifest,
        "platform",
        lambda: adapt_platform(
            Path(manifest.article), project_root or Path.cwd(), run_dir
        ),
    )
    _finish_status(manifest)
    save_manifest(manifest)
    _run_stage(
        manifest,
        "report",
        lambda: _write_reports(
            run_dir,
            review_article(Path(manifest.article), request),
            manifest,
        ),
    )
    _finish_status(manifest)
    save_manifest(manifest)
    return manifest


def _record_image_failure(
    manifest: RunManifest, run_dir: Path, request: Any, message: str
) -> RunManifest:
    from .article import review_article
    from .pipeline import _run_stage, _write_reports, save_manifest

    images = manifest.stages.setdefault("images", StageResult("images"))
    images.status = "degraded"
    images.attempts = max(1, min(2, images.attempts or 1))
    images.error = _redact_error(message)
    manifest.image_status = "degraded"
    warning = images.error
    if warning not in manifest.warnings:
        manifest.warnings.append(warning)
    _reset_stages(manifest, ("report",))
    _finish_status(manifest)
    save_manifest(manifest)
    _run_stage(
        manifest,
        "report",
        lambda: _write_reports(
            run_dir,
            review_article(Path(manifest.article), request),
            manifest,
        ),
    )
    _finish_status(manifest)
    save_manifest(manifest)
    return manifest


def generate_configured_images(
    run_dir: Path, project_root: Path, *, config_path: Path | None = None
) -> RunManifest:
    from .pipeline import load_manifest, save_manifest

    manifest = load_manifest(run_dir)
    _require_non_image_complete(manifest)
    plan_path = run_dir / "image-plan.json"
    if not plan_path.is_file():
        raise ValueError("image plan is missing; run image plan first")
    plan = safe_json_load(plan_path)
    config = load_config(project_root, config_path=config_path)
    providers = config.get("images", {}).get("providers", []) if isinstance(config.get("images"), dict) else []
    providers = [dict(item) for item in providers if isinstance(item, dict) and item.get("kind") in KINDS]
    if not providers:
        from .pipeline import load_request

        return _record_image_failure(
            manifest,
            run_dir,
            load_request(run_dir),
            "no configured API image providers; try Codex native image generation or an MCP provider",
        )
    generated: list[Path] = []
    errors: list[str] = []
    for item in plan.get("items", []):
        if not isinstance(item, dict):
            continue
        item_id = slugify(str(item.get("id", "image")))
        existing = sorted((run_dir / "images").glob(f"{item_id}.*"))
        existing = [path for path in existing if path.is_file() and not path.is_symlink()]
        if existing:
            generated.append(existing[0])
            continue
        success: Path | None = None
        for provider in providers:
            provider_name = slugify(str(provider.get("name", provider.get("kind", "provider"))))
            for attempt in range(1, 3):
                try:
                    data, mime = generate_with_provider(provider, str(item.get("prompt", "")))
                    suffix = _extension(data, mime)
                    fd, temp_name = tempfile.mkstemp(
                        prefix=f".{item_id}-{provider_name}-",
                        suffix=suffix,
                        dir=run_dir,
                    )
                    temp = Path(temp_name)
                    try:
                        with os.fdopen(fd, "wb") as handle:
                            handle.write(data)
                        success = attach_image(
                            run_dir,
                            temp,
                            str(item.get("role", "inline")),
                            heading=str(item.get("heading", "")),
                            alt=str(item.get("alt", "")),
                            provider=str(
                                provider.get("name", provider.get("kind", "provider"))
                            ),
                            model=str(provider.get("model", "")),
                            prompt=str(item.get("prompt", "")),
                        )
                    finally:
                        temp.unlink(missing_ok=True)
                    break
                except Exception as exc:
                    errors.append(
                        _redact_error(
                            f"{item.get('id')} via {provider_name} attempt {attempt}: "
                            f"{type(exc).__name__}: {exc}"
                        )
                    )
            if success:
                break
        if success:
            generated.append(success)
    manifest = load_manifest(run_dir)
    images = manifest.stages.setdefault("images", StageResult("images"))
    images.attempts = 2 if errors else 1
    images.artifacts = [str(path) for path in generated]
    if len(generated) == len(plan.get("items", [])):
        images.status = "complete"
        manifest.image_status = "complete"
    else:
        images.status = "degraded"
        images.error = "; ".join(errors[-6:])
        manifest.image_status = "degraded"
        manifest.warnings.append(f"generated {len(generated)} of {len(plan.get('items', []))} requested images")
        manifest.status = "complete_with_warnings"
    save_manifest(manifest)
    return refresh_image_outputs(run_dir, project_root)
