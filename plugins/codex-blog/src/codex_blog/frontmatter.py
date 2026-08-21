from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .utils import atomic_write_text, safe_read_text

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value.startswith(("'", '"')) and value.endswith(value[0]):
        return value[1:-1]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        if not body:
            return []
        return [_scalar(item) for item in body.split(",")]
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text
    block = match.group(1)
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None
    if yaml is not None:
        try:
            loaded = yaml.safe_load(block)
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid YAML frontmatter: {exc}") from exc
        data = loaded if isinstance(loaded, dict) else {}
    else:
        for opening, closing in (("[", "]"), ("{", "}")):
            if block.count(opening) != block.count(closing):
                raise ValueError(
                    f"invalid YAML frontmatter: unmatched {opening}{closing} delimiter"
                )
        anchors = set(re.findall(r"&([A-Za-z0-9_-]+)", block))
        aliases = set(re.findall(r"\*([A-Za-z0-9_-]+)", block))
        unknown_aliases = aliases - anchors
        if unknown_aliases:
            raise ValueError(
                "invalid YAML frontmatter: unknown alias "
                + ", ".join(sorted(unknown_aliases))
            )
        data: dict[str, Any] = {}
        current_list: str | None = None
        for raw_line in block.splitlines():
            if raw_line.startswith("  - ") and current_list:
                data.setdefault(current_list, []).append(_scalar(raw_line[4:]))
                continue
            if ":" not in raw_line or raw_line.startswith((" ", "\t")):
                current_list = None
                continue
            key, raw_value = raw_line.split(":", 1)
            key = key.strip()
            if not key:
                continue
            value = _scalar(raw_value)
            data[key] = value
            current_list = key if value == "" else None
            if current_list:
                data[key] = []
    return data, text[match.end() :]


def read_markdown(path: Path, *, max_bytes: int = 4 * 1024 * 1024) -> tuple[dict[str, Any], str]:
    return parse_frontmatter(
        safe_read_text(path, max_bytes=max_bytes, label="Markdown input")
    )


def _quote(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def dump_markdown(frontmatter: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        if value is None or value == "":
            continue
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {_quote(item)}" for item in value)
        else:
            lines.append(f"{key}: {_quote(value)}")
    lines.extend(["---", "", body.strip(), ""])
    return "\n".join(lines)


def write_markdown(path: Path, frontmatter: dict[str, Any], body: str) -> None:
    atomic_write_text(path, dump_markdown(frontmatter, body))
