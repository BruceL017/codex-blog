from __future__ import annotations

import http.client
import ipaddress
import socket
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass


@dataclass(slots=True)
class LinkResult:
    url: str
    ok: bool
    status: int | None = None
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return {"url": self.url, "ok": self.ok, "status": self.status, "error": self.error}


def _resolved_public_addresses(hostname: str) -> list[str]:
    try:
        records = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    if not records:
        return []
    addresses: list[str] = []
    for record in records:
        address = ipaddress.ip_address(record[4][0])
        if not address.is_global:
            return []
        normalized = str(address)
        if normalized not in addresses:
            addresses.append(normalized)
    return addresses


def _public_addresses(hostname: str) -> bool:
    return bool(_resolved_public_addresses(hostname))


def _parse_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only absolute HTTP(S) URLs are supported")
    if parsed.username or parsed.password:
        raise ValueError("credentials in URLs are forbidden")
    return parsed


def _validated_target(url: str) -> tuple[urllib.parse.ParseResult, list[str]]:
    parsed = _parse_url(url)
    addresses = _resolved_public_addresses(str(parsed.hostname))
    if not addresses:
        raise ValueError("host does not resolve exclusively to public addresses")
    return parsed, addresses


def _validate_url(url: str) -> urllib.parse.ParseResult:
    return _validated_target(url)[0]


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname: str, address: str, port: int, timeout: float) -> None:
        super().__init__(hostname, port=port, timeout=timeout)
        self._pinned_address = address

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._pinned_address, self.port), self.timeout, self.source_address
        )
        if self._tunnel_host:
            self._tunnel()
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


def _request_once(
    url: str,
    method: str,
    headers: dict[str, str],
    timeout: float,
    *,
    parsed: urllib.parse.ParseResult | None = None,
    addresses: list[str] | None = None,
) -> tuple[int, dict[str, str]]:
    if parsed is None or addresses is None:
        parsed, addresses = _validated_target(url)
    raw_hostname = str(parsed.hostname)
    hostname = (
        raw_hostname
        if ":" in raw_hostname
        else raw_hostname.encode("idna").decode("ascii")
    )
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    target = parsed.path or "/"
    if parsed.params:
        target += f";{parsed.params}"
    if parsed.query:
        target += f"?{parsed.query}"
    default_port = 443 if parsed.scheme == "https" else 80
    host_label = f"[{hostname}]" if ":" in hostname else hostname
    host_header = host_label if port == default_port else f"{host_label}:{port}"
    last_error: Exception | None = None
    for address in addresses:
        connection: http.client.HTTPConnection
        if parsed.scheme == "https":
            connection = _PinnedHTTPSConnection(hostname, address, port, timeout)
        else:
            connection = http.client.HTTPConnection(address, port=port, timeout=timeout)
        try:
            connection.request(method, target, headers={"Host": host_header, **headers})
            response = connection.getresponse()
            status = int(response.status)
            response_headers = {key.lower(): value for key, value in response.getheaders()}
            response.read(1024 if method == "GET" else 0)
            return status, response_headers
        except (OSError, http.client.HTTPException) as exc:
            last_error = exc
        finally:
            connection.close()
    if last_error:
        raise last_error
    raise OSError("no validated address was reachable")


def request_bytes(
    url: str,
    *,
    method: str,
    headers: dict[str, str],
    timeout: float,
    body: bytes | None = None,
    max_bytes: int,
) -> tuple[bytes, dict[str, str]]:
    """Fetch one public URL without redirects while pinning validated DNS."""
    parsed, addresses = _validated_target(url)
    raw_hostname = str(parsed.hostname)
    hostname = raw_hostname if ":" in raw_hostname else raw_hostname.encode("idna").decode("ascii")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    target = parsed.path or "/"
    if parsed.params:
        target += f";{parsed.params}"
    if parsed.query:
        target += f"?{parsed.query}"
    default_port = 443 if parsed.scheme == "https" else 80
    host_label = f"[{hostname}]" if ":" in hostname else hostname
    host_header = host_label if port == default_port else f"{host_label}:{port}"
    last_error: Exception | None = None
    for address in addresses:
        connection: http.client.HTTPConnection
        if parsed.scheme == "https":
            connection = _PinnedHTTPSConnection(hostname, address, port, timeout)
        else:
            connection = http.client.HTTPConnection(address, port=port, timeout=timeout)
        try:
            connection.request(method, target, body=body, headers={"Host": host_header, **headers})
            response = connection.getresponse()
            status = int(response.status)
            response_headers = {key.lower(): value for key, value in response.getheaders()}
            if 300 <= status < 400:
                raise ValueError("redirects are forbidden for credentialed provider requests")
            if not 200 <= status < 300:
                response.read(1024)
                raise RuntimeError(f"provider returned HTTP {status}")
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError(f"response exceeds {max_bytes} bytes")
            return data, response_headers
        except (OSError, http.client.HTTPException) as exc:
            last_error = exc
        finally:
            connection.close()
    if last_error:
        raise last_error
    raise OSError("no validated address was reachable")


def check_link(url: str, *, timeout: float = 4.0) -> LinkResult:
    try:
        current_parsed, current_addresses = _validated_target(url)
    except ValueError as exc:
        return LinkResult(url, False, error=str(exc))
    headers = {"User-Agent": "codex-blog/2.1.1 link-check", "Accept": "text/html,*/*;q=0.1"}
    for method in ("HEAD", "GET"):
        request_headers = dict(headers)
        if method == "GET":
            request_headers["Range"] = "bytes=0-1023"
        current = url
        for redirect_count in range(4):
            try:
                status, response_headers = _request_once(
                    current,
                    method,
                    request_headers,
                    timeout,
                    parsed=current_parsed,
                    addresses=current_addresses,
                )
                if 300 <= status < 400 and response_headers.get("location"):
                    if redirect_count == 3:
                        return LinkResult(url, False, status=status, error="too many redirects")
                    current = urllib.parse.urljoin(current, response_headers["location"])
                    try:
                        current_parsed, current_addresses = _validated_target(current)
                    except ValueError as redirect_error:
                        return LinkResult(
                            url,
                            False,
                            status=status,
                            error=f"unsafe redirect: {redirect_error}",
                        )
                    continue
                if method == "HEAD" and status in {403, 405, 501}:
                    break
                return LinkResult(
                    url,
                    200 <= status < 400 or status in {403, 405},
                    status=status,
                    error="" if status < 400 else f"HTTP {status}",
                )
            except (ValueError, TimeoutError, OSError, http.client.HTTPException) as exc:
                if method == "HEAD":
                    break
                return LinkResult(url, False, error=str(exc))
    return LinkResult(url, False, error="link check failed")


def check_links(urls: list[str], *, timeout: float = 4.0, limit: int = 24) -> list[LinkResult]:
    targets = list(dict.fromkeys(urls))[:limit]
    if not targets:
        return []
    results: dict[str, LinkResult] = {}
    with ThreadPoolExecutor(max_workers=min(6, len(targets))) as pool:
        futures = {pool.submit(check_link, url, timeout=timeout): url for url in targets}
        for future in as_completed(futures):
            url = futures[future]
            try:
                results[url] = future.result()
            except Exception as exc:  # pragma: no cover - defensive executor boundary
                results[url] = LinkResult(url, False, error=str(exc))
    return [results[url] for url in targets]
