from __future__ import annotations

import importlib.util
import json
import socket
import sys
import types
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA_SCRIPTS = ROOT / "skills" / "blog-data" / "scripts"


def _load_module(name: str, filename: str):
    path = DATA_SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    previous_requests = sys.modules.get("requests")
    if filename == "nlp_analyze.py":
        requests_stub = types.ModuleType("requests")
        requests_stub.exceptions = types.SimpleNamespace(RequestException=Exception)
        sys.modules["requests"] = requests_stub
    sys.path.insert(0, str(DATA_SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
        if filename == "nlp_analyze.py":
            if previous_requests is None:
                sys.modules.pop("requests", None)
            else:
                sys.modules["requests"] = previous_requests
    return module


@pytest.mark.parametrize(
    ("url", "kind"),
    [
        ("http://oauth2.googleapis.com/token", "token"),
        ("https://evil.example/token", "token"),
        ("https://oauth2.googleapis.com.evil.example/token", "token"),
        ("https://user@oauth2.googleapis.com/token", "token"),
        ("https://accounts.google.com:444/o/oauth2/auth", "authorization"),
        ("https://oauth2.googleapis.com/token", "authorization"),
    ],
)
def test_google_oauth_endpoint_rejects_unsafe_urls(url: str, kind: str) -> None:
    google_auth = _load_module(f"_test_google_auth_{kind}_{hash(url)}", "google_auth.py")

    with pytest.raises(ValueError):
        google_auth._google_oauth_url(url, kind)


def test_google_oauth_endpoint_accepts_only_expected_defaults() -> None:
    google_auth = _load_module("_test_google_auth_defaults", "google_auth.py")

    assert google_auth._google_oauth_url(None, "token") == "https://oauth2.googleapis.com/token"
    assert (
        google_auth._google_oauth_url(None, "authorization")
        == "https://accounts.google.com/o/oauth2/auth"
    )


def test_oauth_refresh_never_sends_secret_to_untrusted_token_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    google_auth = _load_module("_test_google_auth_refresh_host", "google_auth.py")
    calls: list[object] = []

    def record_urlopen(request, *args, **kwargs):
        calls.append(request)
        raise AssertionError("urlopen must not be called for an unsafe OAuth endpoint")

    monkeypatch.setattr(urllib.request, "urlopen", record_urlopen)
    result = google_auth._refresh_oauth_token(
        {
            "client_id": "client-id",
            "client_secret": "client-secret",
            "token_uri": "https://attacker.example/collect",
        },
        {"refresh_token": "refresh-secret"},
    )

    assert result is None
    assert calls == []


def test_oauth_token_exchange_disables_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    google_auth = _load_module("_test_google_auth_no_redirect", "google_auth.py")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"access_token": "access", "expires_in": 3600}).encode()

    class Opener:
        def __init__(self) -> None:
            self.calls: list[object] = []

        def open(self, request, timeout: int):
            self.calls.append(request)
            return Response()

    opener = Opener()

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("OAuth requests must use the no-redirect opener")

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: opener)
    monkeypatch.setattr(google_auth, "_save_oauth_token", lambda token: None)

    result = google_auth._refresh_oauth_token(
        {
            "client_id": "client-id",
            "client_secret": "client-secret",
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        {"refresh_token": "refresh-secret"},
    )

    assert result and result["access_token"] == "access"
    assert len(opener.calls) == 1


class _Response:
    def __init__(
        self,
        status: int,
        body: bytes = b"",
        headers: list[tuple[str, str]] | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self._headers = headers or []

    def getheaders(self) -> list[tuple[str, str]]:
        return self._headers

    def read(self, amount: int | None = None) -> bytes:
        if amount is None:
            result, self._body = self._body, b""
            return result
        result, self._body = self._body[:amount], self._body[amount:]
        return result


class _HTTPConnection:
    instances: list["_HTTPConnection"] = []
    responses: list[_Response] = []

    def __init__(self, host: str, port: int, timeout: object = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.request_args: tuple[object, ...] | None = None
        self.request_kwargs: dict[str, object] | None = None
        type(self).instances.append(self)

    def request(self, *args, **kwargs) -> None:
        self.request_args = args
        self.request_kwargs = kwargs

    def getresponse(self) -> _Response:
        return type(self).responses.pop(0)

    def close(self) -> None:
        return None


def _public_dns(host: str, port: int, **kwargs):
    address = "93.184.216.34" if host == "example.test" else host
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]


def test_nlp_fetch_pins_validated_ip_and_preserves_host_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nlp = _load_module("_test_nlp_dns_pin", "nlp_analyze.py")
    _HTTPConnection.instances = []
    _HTTPConnection.responses = [
        _Response(200, b"public article", [("Content-Type", "text/plain; charset=utf-8")])
    ]
    monkeypatch.setattr(nlp.socket, "getaddrinfo", _public_dns)
    monkeypatch.setattr(nlp.http.client, "HTTPConnection", _HTTPConnection)

    text = nlp._fetch_url_text("http://example.test/article")

    assert text == "public article"
    connection = _HTTPConnection.instances[0]
    assert connection.host == "93.184.216.34"
    assert connection.request_kwargs["headers"]["Host"] == "example.test"


def test_nlp_https_uses_pinned_ip_with_original_tls_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nlp = _load_module("_test_nlp_https_dns_pin", "nlp_analyze.py")

    class HTTPSConnection(_HTTPConnection):
        def __init__(self, hostname: str, address: str, port: int, timeout: float) -> None:
            self.hostname = hostname
            self.address = address
            super().__init__(address, port, timeout)

    HTTPSConnection.instances = []
    HTTPSConnection.responses = [_Response(200, b"secure article")]
    monkeypatch.setattr(nlp.socket, "getaddrinfo", _public_dns)
    monkeypatch.setattr(nlp, "_PinnedHTTPSConnection", HTTPSConnection)

    text = nlp._fetch_url_text("https://example.test/article")

    assert text == "secure article"
    connection = HTTPSConnection.instances[0]
    assert connection.hostname == "example.test"
    assert connection.address == "93.184.216.34"


def test_nlp_redirect_to_private_ip_is_rejected_before_second_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nlp = _load_module("_test_nlp_private_redirect", "nlp_analyze.py")
    _HTTPConnection.instances = []
    _HTTPConnection.responses = [
        _Response(302, headers=[("Location", "http://127.0.0.1/private")])
    ]
    monkeypatch.setattr(nlp.socket, "getaddrinfo", _public_dns)
    monkeypatch.setattr(nlp.http.client, "HTTPConnection", _HTTPConnection)

    with pytest.raises(ValueError, match="public|blocked"):
        nlp._fetch_url_text("http://example.test/start")

    assert len(_HTTPConnection.instances) == 1
