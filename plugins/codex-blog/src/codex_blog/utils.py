from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    pieces: list[str] = []
    separator = False
    for char in normalized:
        if char.isascii() and char.isalnum():
            pieces.append(char)
            separator = False
        elif char in {"-", "_", " ", "/"}:
            if pieces and not separator:
                pieces.append("-")
                separator = True
    slug = "".join(pieces).strip("-")
    if slug:
        return re.sub(r"-+", "-", slug)[:96].rstrip("-")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10]
    return f"article-{digest}"


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = str(value).strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def assert_no_symlink_ancestors(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            details = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(details.st_mode):
            raise ValueError(f"refusing symlink ancestor: {current}")


def atomic_write_text(path: Path, text: str, *, mode: int | None = None) -> None:
    assert_no_symlink_ancestors(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_no_symlink_ancestors(path.parent)
    if path.is_symlink():
        raise ValueError(f"refusing to overwrite symlink: {path}")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        if mode is not None:
            os.chmod(tmp_name, mode)
        assert_no_symlink_ancestors(path.parent)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_bytes(path: Path, data: bytes, *, mode: int | None = None) -> None:
    assert_no_symlink_ancestors(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_no_symlink_ancestors(path.parent)
    if path.is_symlink():
        raise ValueError(f"refusing to overwrite symlink: {path}")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        if mode is not None:
            os.chmod(tmp_name, mode)
        assert_no_symlink_ancestors(path.parent)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, value: Any, *, private: bool = False) -> None:
    atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        mode=0o600 if private else None,
    )


def safe_read_text(
    path: Path,
    *,
    max_bytes: int = 4 * 1024 * 1024,
    label: str = "text input",
) -> str:
    assert_no_symlink_ancestors(path.parent)
    if path.is_symlink():
        raise ValueError(f"refusing to follow symlink: {path}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if path.is_symlink():
            raise ValueError(f"refusing to follow symlink: {path}") from exc
        raise
    try:
        details = os.fstat(fd)
        if not stat.S_ISREG(details.st_mode):
            raise ValueError(f"{label} must be a regular file: {path}")
        if details.st_size > max_bytes:
            raise ValueError(f"{label} exceeds {max_bytes} bytes: {path}")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(fd, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
    finally:
        os.close(fd)
    if len(data) > max_bytes:
        raise ValueError(f"{label} exceeds {max_bytes} bytes: {path}")
    return data.decode("utf-8")


def safe_json_load(path: Path, *, max_bytes: int = 4 * 1024 * 1024) -> Any:
    return json.loads(
        safe_read_text(path, max_bytes=max_bytes, label="JSON input")
    )
