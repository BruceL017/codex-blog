from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "blog-data" / "scripts"


def _load(name: str):
    if name == "youtube_search":
        package = types.ModuleType("googleapiclient")
        discovery = types.ModuleType("googleapiclient.discovery")
        discovery.build = lambda *_args, **_kwargs: None
        package.discovery = discovery
        sys.modules.setdefault("googleapiclient", package)
        sys.modules.setdefault("googleapiclient.discovery", discovery)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


@pytest.mark.parametrize(
    ("module_name", "call"),
    [
        (
            "pagespeed_check",
            lambda module, key: module.run_pagespeed(
                "https://example.com", api_key=key
            ),
        ),
        (
            "pagespeed_check",
            lambda module, key: module.query_crux("https://example.com", key),
        ),
        (
            "crux_history",
            lambda module, key: module.query_history("https://example.com", key),
        ),
    ],
)
def test_google_api_errors_never_serialize_query_keys(
    module_name: str, call, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load(module_name)
    secret = "google-api-key-must-not-leak"

    def fail(*_args, **_kwargs):
        raise module.requests.exceptions.RequestException(
            f"request failed for https://googleapis.example/v1?key={secret}"
        )

    monkeypatch.setattr(module, "request_with_retries", fail)

    result = call(module, secret)

    assert secret not in result["error"]
    assert "[REDACTED]" in result["error"]


def test_nlp_errors_never_serialize_query_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load("nlp_analyze")
    secret = "nlp-key-must-not-leak"

    def fail(*_args, **_kwargs):
        raise module.requests.exceptions.RequestException(
            f"failed https://language.googleapis.com/v2?key={secret}"
        )

    monkeypatch.setattr(module, "request_with_retries", fail)
    result = module.analyze_text("safe text", api_key=secret)

    assert secret not in result["error"]
    assert "[REDACTED]" in result["error"]


def test_youtube_api_errors_never_serialize_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load("youtube_search")
    secret = "youtube-key-must-not-leak"

    class Request:
        def execute(self):
            raise RuntimeError(
                f"failed https://youtube.googleapis.com/v3/search?key={secret}"
            )

    class Search:
        def list(self, **_kwargs):
            return Request()

    class Service:
        def search(self):
            return Search()

    monkeypatch.setattr(module, "_build_youtube_service", lambda _key=None: Service())
    result = module.search_videos("codex blog", api_key=secret)

    assert secret not in result["error"]
    assert "[REDACTED]" in result["error"]
