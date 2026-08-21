"""Behavioral coverage for the Codex-native runtime contracts."""

from __future__ import annotations

import base64
import hashlib
import json
import socket
from pathlib import Path

import pytest

from codex_blog import images, links
from codex_blog.article import review_article
from codex_blog.cli import main as cli_main
from codex_blog.images import create_image_plan, generate_configured_images
from codex_blog.models import BlogWriteRequest
from codex_blog.pipeline import CoreArticleError, create_run, finalize_run, load_manifest


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "article-first.md"


def _request() -> BlogWriteRequest:
    return BlogWriteRequest(
        topic="Article First SEO",
        primary_keyword="article first SEO",
        language="en",
        word_count=700,
    )


def test_thin_outline_cannot_pass_as_a_complete_core_article(tmp_path: Path) -> None:
    article = tmp_path / "thin.md"
    article.write_text(
        """---
title: Article First SEO
description: A nominal description
slug: article-first-seo
primary_keyword: article first SEO
---
# Article First SEO

Short opening.

## First section

Barely any substance.

## Conclusion

Still not a complete article.
""",
        encoding="utf-8",
    )

    result = review_article(article, _request())
    assert result.complete is False
    assert any("minimum complete-article floor" in error for error in result.errors)


@pytest.mark.parametrize(
    "placeholder",
    [
        "[ANSWER-FIRST]",
        "[INFO-GAIN: original analysis]",
        "[INTERNAL-LINK to related tutorial]",
        "[Brief description of the result]",
        "- [ ] Replace this checklist item",
        "[N] practical steps",
    ],
)
def test_template_placeholders_cannot_pass_the_core_gate(
    tmp_path: Path, placeholder: str
) -> None:
    article = tmp_path / "placeholder.md"
    article.write_text(
        FIXTURE.read_text(encoding="utf-8") + f"\n\n{placeholder}\n",
        encoding="utf-8",
    )

    result = review_article(article, _request())

    assert result.complete is False
    assert any("placeholder" in error for error in result.errors)


def test_code_and_human_citations_are_not_mistaken_for_placeholders(
    tmp_path: Path,
) -> None:
    article = tmp_path / "brackets.md"
    article.write_text(
        FIXTURE.read_text(encoding="utf-8")
        + "\n\nUse `items[index]` and this shell check:\n\n"
        + "```sh\nif [ -f article.md ]; then echo ready; fi\n```\n\n"
        + "```md\n![example](https://example.test/image.png)\n<img src=\"example.png\">\n```\n\n"
        + "The editorial model follows prior synthesis work [Smith, 2024].\n",
        encoding="utf-8",
    )

    result = review_article(article, _request())

    assert result.complete, result.errors


@pytest.mark.parametrize(
    ("language", "heading", "unit"),
    [
        ("ru", "Итоги", "Надёжный процесс сохраняет статью прежде любых дополнительных шагов. "),
        ("ar", "الخطوات التالية", "تحفظ العملية الموثوقة المقالة قبل أي خطوة إضافية. "),
        ("th", "ขั้นตอนถัดไป", "กระบวนการที่เชื่อถือได้จะบันทึกบทความก่อนขั้นตอนเสริมทั้งหมด"),
    ],
)
def test_complete_non_latin_articles_use_script_independent_units(
    tmp_path: Path, language: str, heading: str, unit: str
) -> None:
    request = BlogWriteRequest(
        topic="Article First SEO",
        primary_keyword="Article First SEO",
        language=language,
        word_count=350,
    )
    article = tmp_path / f"article-{language}.md"
    body = unit * 45
    article.write_text(
        "---\n"
        "title: Article First SEO\n"
        "description: Complete localized article\n"
        "slug: article-first-seo\n"
        "primary_keyword: Article First SEO\n"
        "---\n"
        "# Article First SEO\n\n"
        f"{body}\n\n"
        f"## {heading} 1\n\n{body}\n\n"
        f"## {heading}\n\n{body}\n",
        encoding="utf-8",
    )

    result = review_article(article, request)

    assert result.complete, result.errors


def test_supported_language_article_without_a_closing_section_is_incomplete(
    tmp_path: Path,
) -> None:
    article = tmp_path / "no-conclusion.md"
    text = FIXTURE.read_text(encoding="utf-8").replace(
        "## Conclusion", "## Additional implementation details"
    )
    article.write_text(text, encoding="utf-8")

    result = review_article(article, _request())

    assert result.complete is False
    assert any("closing section" in error for error in result.errors)


def test_malformed_yaml_counts_as_a_recoverable_core_attempt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    Path(manifest.article).write_text(
        "---\ntitle: [unterminated\ndescription: broken\n---\n# Draft\n",
        encoding="utf-8",
    )

    code = cli_main(
        [
            "finalize",
            "--run",
            str(run_dir),
            "--project-root",
            str(tmp_path),
            "--skip-external-links",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["blocked"] is False
    assert payload["core_attempts"] == 1
    assert "invalid YAML frontmatter" in payload["error"]


def test_core_article_remains_recoverable_twice_then_blocks_on_third_attempt(tmp_path: Path) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    article = Path(manifest.article)
    article.write_text("---\ntitle: Incomplete\n---\n# Incomplete\n", encoding="utf-8")

    for attempt in (1, 2):
        with pytest.raises(CoreArticleError) as caught:
            finalize_run(run_dir, project_root=tmp_path, check_external_links=False)
        assert caught.value.blocked is False
        assert caught.value.attempts == attempt
        current = load_manifest(run_dir)
        assert current.status == "awaiting_article"
        assert current.stages["core_article"].status == "pending"

    with pytest.raises(CoreArticleError) as caught:
        finalize_run(run_dir, project_root=tmp_path, check_external_links=False)
    assert caught.value.blocked is True
    assert caught.value.attempts == 3
    current = load_manifest(run_dir)
    assert current.status == "blocked"
    assert current.stages["core_article"].attempts == 3


def test_core_article_can_recover_on_third_attempt(tmp_path: Path) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    article = Path(manifest.article)
    article.write_text("# Incomplete\n", encoding="utf-8")
    for _ in range(2):
        with pytest.raises(CoreArticleError):
            finalize_run(run_dir, project_root=tmp_path, check_external_links=False)
    article.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    result = finalize_run(run_dir, project_root=tmp_path, check_external_links=False)
    assert result.stages["core_article"].status == "complete"
    assert result.stages["core_article"].attempts == 3
    assert result.status in {"complete", "complete_with_warnings"}


def test_changed_article_invalidates_and_refreshes_downstream_outputs(tmp_path: Path) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    article = Path(manifest.article)
    original = FIXTURE.read_text(encoding="utf-8")
    article.write_text(original, encoding="utf-8")
    first = finalize_run(run_dir, project_root=tmp_path, check_external_links=False)
    first_digest = first.article_digest

    changed = original.replace(
        "Learn how an article-first SEO workflow protects core content while optional production steps run independently.",
        "A refreshed description for the article-first SEO publishing workflow.",
    ).replace(
        "Teams can apply the same principle",
        "This refreshed edition is now visible in rendered output. Teams can apply the same principle",
    )
    article.write_text(changed, encoding="utf-8")
    second = finalize_run(run_dir, project_root=tmp_path, check_external_links=False)

    assert second.article_digest != first_digest
    assert second.stages["schema"].attempts == 1
    assert "A refreshed description" in (run_dir / "schema.json").read_text(encoding="utf-8")
    assert "This refreshed edition" in (run_dir / f"{_request().slug}.html").read_text(encoding="utf-8")


def test_report_failure_is_bounded_and_never_blocks_the_article(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    Path(manifest.article).write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(
        "codex_blog.pipeline._write_reports",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("report unavailable")),
    )

    result = finalize_run(run_dir, project_root=tmp_path, check_external_links=False)

    assert result.stages["core_article"].status == "complete"
    assert result.stages["report"].status == "degraded"
    assert result.stages["report"].attempts == 2
    assert result.status == "complete_with_warnings"


def test_cli_image_question_does_not_retry_the_report_stage_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    Path(manifest.article).write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    calls = 0

    def broken_report(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("report unavailable")

    monkeypatch.setattr("codex_blog.pipeline._write_reports", broken_report)
    assert cli_main(
        ["finalize", "--run", str(run_dir), "--project-root", str(tmp_path), "--skip-external-links"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["image_prompt_required"] is True
    assert calls == 2
    assert load_manifest(run_dir).stages["report"].attempts == 2


def test_manifest_schema_has_distinct_core_and_downstream_attempt_caps() -> None:
    schema = json.loads((ROOT / "schemas" / "run-manifest.schema.json").read_text(encoding="utf-8"))
    assert schema["$defs"]["coreStage"]["properties"]["attempts"]["maximum"] == 3
    assert schema["$defs"]["downstreamStage"]["properties"]["attempts"]["maximum"] == 2
    assert "image_decision" in schema["required"]
    assert "article_digest" in schema["required"]
    for field in ("request_digest", "language", "template", "provenance", "conflicts"):
        assert field in schema["required"]
    assert schema["properties"]["image_decision"]["enum"] == [
        "not_asked",
        "asked",
        "declined",
        "hero",
        "full",
    ]


def test_finalize_emits_the_deferred_image_question_exactly_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    Path(manifest.article).write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    assert cli_main(
        ["finalize", "--run", str(run_dir), "--project-root", str(tmp_path), "--skip-external-links"]
    ) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["image_prompt_required"] is True
    assert first["image_prompt"] == "The article and non-image outputs are complete. Generate images now?"
    assert load_manifest(run_dir).image_decision == "asked"

    assert cli_main(
        ["finalize", "--run", str(run_dir), "--project-root", str(tmp_path), "--skip-external-links"]
    ) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["image_prompt_required"] is False
    assert second["image_prompt"] is None


def test_openai_compatible_provider_uses_custom_endpoint_and_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("CODEX_BLOG_IMAGE_TEST_TOKEN", "secret-value")

    def fake_request(url, payload, headers, timeout):
        captured.update(url=url, payload=payload, headers=headers, timeout=timeout)
        return {"data": [{"b64_json": base64.b64encode(b"\x89PNG\r\n\x1a\nimage").decode()}]}

    monkeypatch.setattr(images, "_request_json", fake_request)
    data, mime = images.generate_with_provider(
        {
            "kind": "openai-compatible",
            "base_url": "https://images.example.test/custom/v1",
            "model": "custom-image-model",
            "api_key_env": "CODEX_BLOG_IMAGE_TEST_TOKEN",
            "timeout_seconds": 12,
        },
        "test prompt",
    )
    assert captured["url"] == "https://images.example.test/custom/v1/images/generations"
    assert captured["headers"] == {"Authorization": "Bearer secret-value"}
    assert captured["payload"]["model"] == "custom-image-model"  # type: ignore[index]
    assert data.startswith(b"\x89PNG") and mime == "image/png"


def test_gemini_compatible_provider_uses_custom_endpoint_and_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("CODEX_BLOG_IMAGE_GEMINI_TOKEN", "gemini-secret")

    def fake_request(url, payload, headers, timeout):
        captured.update(url=url, payload=payload, headers=headers, timeout=timeout)
        return {
            "candidates": [
                {"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(b"\x89PNG\r\n\x1a\nimage").decode()}}]}}
            ]
        }

    monkeypatch.setattr(images, "_request_json", fake_request)
    data, mime = images.generate_with_provider(
        {
            "kind": "gemini-compatible",
            "base_url": "https://gemini.example.test/v1beta",
            "model": "custom-gemini-image",
            "api_key_env": "CODEX_BLOG_IMAGE_GEMINI_TOKEN",
        },
        "test prompt",
    )
    assert captured["url"] == "https://gemini.example.test/v1beta/models/custom-gemini-image:generateContent"
    assert captured["headers"] == {"x-goog-api-key": "gemini-secret"}
    assert data.startswith(b"\x89PNG") and mime == "image/png"


def test_configured_provider_retries_twice_then_falls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    Path(manifest.article).write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    finalize_run(run_dir, project_root=tmp_path, check_external_links=False)
    create_image_plan(run_dir, "hero")
    config = tmp_path / ".codex-blog" / "config.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps({"images": {"providers": [
            {"kind": "openai-compatible", "name": "first", "base_url": "https://first.test/v1"},
            {"kind": "gemini-compatible", "name": "second", "base_url": "https://second.test/v1"},
        ]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_BLOG_IMAGE_CONFIG", str(config))
    calls: list[str] = []

    def fake_generate(provider, prompt):
        calls.append(provider["name"])
        if provider["name"] == "first":
            raise RuntimeError("first unavailable")
        return b"\x89PNG\r\n\x1a\nimage", "image/png"

    monkeypatch.setattr(images, "generate_with_provider", fake_generate)
    monkeypatch.setattr(
        "codex_blog.pipeline._render",
        lambda run, article, *, pdf, hero=None: [run / ("article.pdf" if pdf else "article.html")],
    )
    result = generate_configured_images(run_dir, tmp_path)
    assert calls == ["first", "first", "second"]
    assert result.stages["images"].status == "complete"
    assert result.stages["images"].attempts == 2


def test_project_image_config_cannot_select_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_config = tmp_path / ".codex-blog" / "config.json"
    project_config.parent.mkdir()
    project_config.write_text(
        json.dumps(
            {
                "images": {
                    "providers": [
                        {
                            "kind": "openai-compatible",
                            "base_url": "https://attacker.example/v1",
                            "api_key_env": "GH_TOKEN",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.delenv("CODEX_BLOG_IMAGE_CONFIG", raising=False)

    assert images.load_config(tmp_path) == {"images": {"providers": []}}


def test_provider_rejects_non_image_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "must-not-leak")
    called = False

    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("network must not be opened")

    monkeypatch.setattr(images, "_request_json", forbidden)
    with pytest.raises(ValueError, match="dedicated image credential"):
        images.generate_with_provider(
            {
                "kind": "openai-compatible",
                "base_url": "https://images.example.test/v1",
                "api_key_env": "GH_TOKEN",
            },
            "test prompt",
        )
    assert called is False


def test_custom_provider_cannot_receive_an_official_default_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "official-secret")
    called = False

    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("network must not be opened")

    monkeypatch.setattr(images, "_request_json", forbidden)
    with pytest.raises(ValueError, match="custom provider endpoints require"):
        images.generate_with_provider(
            {
                "kind": "openai-compatible",
                "base_url": "https://attacker.example/v1",
            },
            "test prompt",
        )
    assert called is False


def test_provider_http_and_private_network_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        images._provider_url("http://images.example.test/v1")

    monkeypatch.setattr(
        links.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("169.254.169.254", 443))
        ],
    )
    with pytest.raises(ValueError, match="public addresses"):
        images._request_json("https://metadata.example.test/v1", {}, {}, 1)


@pytest.mark.parametrize(
    "url",
    [
        "https://images.example.test/v1?token=must-not-persist",
        "https://images.example.test/v1#secret-fragment",
    ],
)
def test_provider_base_url_rejects_query_and_fragment(url: str) -> None:
    with pytest.raises(ValueError, match="query or fragment"):
        images._provider_url(url)


def test_image_plan_waits_for_all_non_image_stages(tmp_path: Path) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    Path(manifest.article).write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="non-image stages"):
        create_image_plan(run_dir, "hero")


def test_image_attachment_requires_real_magic_and_safe_parent(tmp_path: Path) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    Path(manifest.article).write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    finalize_run(run_dir, project_root=tmp_path, check_external_links=False)
    create_image_plan(run_dir, "hero")
    fake = tmp_path / "fake.png"
    fake.write_bytes(b"not actually an image")

    with pytest.raises(ValueError, match="unsupported generated image format"):
        images.attach_image(run_dir, fake, "hero")

    actual_source = tmp_path / "actual-source"
    actual_source.mkdir()
    (actual_source / "linked.png").write_bytes(b"\x89PNG\r\n\x1a\nsynthetic")
    linked_source = tmp_path / "linked-source"
    try:
        linked_source.symlink_to(actual_source, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(ValueError, match="symlink ancestor"):
        images.attach_image(run_dir, linked_source / "linked.png", "hero")

    outside = tmp_path / "outside-images"
    outside.mkdir()
    image_dir = run_dir / "images"
    image_dir.symlink_to(outside, target_is_directory=True)
    real = tmp_path / "real.png"
    real.write_bytes(b"\x89PNG\r\n\x1a\nsynthetic")
    with pytest.raises(ValueError, match="symlink"):
        images.attach_image(run_dir, real, "hero")


def test_image_attach_updates_digest_and_records_safe_metadata(tmp_path: Path) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    article = Path(manifest.article)
    article.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    finalize_run(run_dir, project_root=tmp_path, check_external_links=False)
    create_image_plan(run_dir, "hero")
    source = tmp_path / "hero.png"
    source.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + (1200).to_bytes(4, "big")
        + (630).to_bytes(4, "big")
        + b"synthetic"
    )

    images.attach_image(
        run_dir,
        source,
        "hero",
        alt="Article-first workflow",
        provider="codex-native",
        model="native",
        prompt="Create an editorial workflow hero",
    )
    updated = load_manifest(run_dir)

    assert updated.article_digest == hashlib.sha256(article.read_bytes()).hexdigest()
    assert updated.image_assets == [
        {
            "id": "hero",
            "role": "hero",
            "path": "images/hero.png",
            "provider": "codex-native",
            "model": "native",
            "prompt_sha256": hashlib.sha256(
                b"Create an editorial workflow hero"
            ).hexdigest(),
            "width": 1200,
            "height": 630,
            "alt": "Article-first workflow",
        }
    ]


def test_missing_configured_provider_degrades_images_without_losing_article(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir, manifest = create_run(_request(), tmp_path / "output")
    article = Path(manifest.article)
    article.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    finalize_run(run_dir, project_root=tmp_path, check_external_links=False)
    create_image_plan(run_dir, "hero")
    monkeypatch.setenv("CODEX_BLOG_IMAGE_CONFIG", str(tmp_path / "missing.json"))

    result = generate_configured_images(run_dir, tmp_path)

    assert article.is_file()
    assert result.stages["core_article"].status == "complete"
    assert result.stages["images"].status == "degraded"
    assert result.stages["images"].attempts == 1
    assert result.image_status == "degraded"
    assert result.status == "complete_with_warnings"
    assert "no configured API image providers" in result.stages["images"].error


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "http://user:pass@example.com/",
    "javascript:alert(1)",
    "http://127.0.0.1/private",
    "http://169.254.169.254/latest/meta-data",
])
def test_link_checker_rejects_unsafe_urls_without_network(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(links.socket, "getaddrinfo", lambda *_a, **_kw: [(2, 1, 6, "", ("127.0.0.1", 0))])
    called = False

    def forbidden_connection(*_a, **_kw):
        nonlocal called
        called = True
        raise AssertionError("network must not be opened")

    monkeypatch.setattr(links.http.client, "HTTPConnection", forbidden_connection)
    result = links.check_link(url)
    assert result.ok is False
    assert called is False


def test_link_checker_pins_validated_dns_during_open(monkeypatch: pytest.MonkeyPatch) -> None:
    public = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 80))]
    private = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("169.254.169.254", 80))]
    dns_calls = 0

    def rebinding_getaddrinfo(host, port, *args, **kwargs):
        nonlocal dns_calls
        dns_calls += 1
        return public if dns_calls == 1 else private

    connected: list[str] = []

    class Response:
        status = 200
        def getheaders(self):
            return []
        def read(self, limit=0):
            return b""

    class Connection:
        def __init__(self, address, port=None, timeout=None):
            connected.append(address)
        def request(self, method, target, headers=None):
            return None
        def getresponse(self):
            return Response()
        def close(self):
            return None

    monkeypatch.setattr(links.socket, "getaddrinfo", rebinding_getaddrinfo)
    monkeypatch.setattr(links.http.client, "HTTPConnection", Connection)
    status, _headers = links._request_once("http://rebind.example/path", "HEAD", {}, 1)
    assert status == 200
    assert connected == ["93.184.216.34"]
    assert links.socket.getaddrinfo is rebinding_getaddrinfo


def test_provider_image_download_rejects_cross_origin_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("network must not be opened")

    monkeypatch.setattr(images, "request_bytes", forbidden)
    with pytest.raises(ValueError, match="configured provider host"):
        images._download_same_origin(
            "https://cdn.example.test/image.png",
            "https://api.example.test/v1",
            1,
        )
    assert called is False


def test_create_run_refuses_symlink_output_directory(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    (output / _request().slug).symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        create_run(_request(), output)


def test_create_run_refuses_a_symlinked_output_ancestor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    try:
        (project / ".codex-blog").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    monkeypatch.chdir(project)

    with pytest.raises(ValueError, match="symlink ancestor"):
        create_run(_request())

    assert list(outside.iterdir()) == []


def test_cli_init_refuses_a_symlinked_project_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    try:
        (project / ".codex-blog").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    assert cli_main(["init", "--project-root", str(project)]) == 1
    assert "symlink ancestor" in capsys.readouterr().err
    assert list(outside.iterdir()) == []


def test_manifest_paths_cannot_escape_the_run_directory(tmp_path: Path) -> None:
    run_dir, _manifest = create_run(_request(), tmp_path / "output")
    manifest_path = run_dir / "run-manifest.json"
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    value["article"] = str(tmp_path / "outside.md")
    manifest_path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="canonical article path"):
        load_manifest(run_dir)


def test_adapters_are_file_only_and_do_not_import_external_skills() -> None:
    source = (ROOT / "src" / "codex_blog" / "adapters.py").read_text(encoding="utf-8")
    assert "codex_seo" not in source
    assert "extract_seo_materials" not in source
    contract = (ROOT / "skills" / "blog" / "references" / "input-contract.md").read_text(encoding="utf-8")
    assert "never import another Skill's source" in contract
