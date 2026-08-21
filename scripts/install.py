#!/usr/bin/env python3
"""Ownership-aware Codex Blog installer and uninstaller."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = "brucel017-codex-blog"
PLUGIN_NAME = "codex-blog"
PLUGIN_ID = f"{PLUGIN_NAME}@{MARKETPLACE}"
AGENT_NAMES = {
    "blog-brain-curator",
    "blog-researcher",
    "blog-reviewer",
    "blog-seo",
    "blog-translator",
    "blog-writer",
}


def _codex_home() -> Path:
    raw = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    if not raw.is_absolute() or ".." in raw.parts:
        raise RuntimeError("CODEX_HOME must be an absolute path without '..'")
    path = Path(os.path.abspath(raw))
    _assert_no_symlinks(path)
    return path


def _state_path() -> Path:
    return _codex_home() / "codex-blog" / "install-state.json"


def _assert_no_symlinks(path: Path) -> None:
    """Reject a path when it or any existing ancestor is a symlink."""
    path = Path(os.path.abspath(path))
    for candidate in (path, *path.parents):
        try:
            mode = os.lstat(candidate).st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise RuntimeError(f"refusing symlinked path or ancestor: {candidate}")


def _ensure_directory(path: Path, mode: int = 0o755) -> None:
    """Create a directory tree while refusing symlink traversal."""
    path = Path(os.path.abspath(path))
    _assert_no_symlinks(path)
    missing: list[Path] = []
    candidate = path
    while True:
        try:
            current_mode = os.lstat(candidate).st_mode
        except FileNotFoundError:
            missing.append(candidate)
            if candidate.parent == candidate:
                break
            candidate = candidate.parent
            continue
        if not stat.S_ISDIR(current_mode):
            raise RuntimeError(f"expected directory path: {candidate}")
        break
    for directory in reversed(missing):
        os.mkdir(directory, mode)
        _assert_no_symlinks(directory)


def _regular_file_exists(path: Path) -> bool:
    _assert_no_symlinks(path)
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(mode):
        raise RuntimeError(f"expected regular file path: {path}")
    return True


def _read_bytes(path: Path) -> bytes:
    _assert_no_symlinks(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise RuntimeError(f"expected regular file path: {path}")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(fd)


def _read_text(path: Path) -> str:
    return _read_bytes(path).decode("utf-8")


def _atomic_write(path: Path, data: bytes, *, mode: int) -> None:
    """Replace one regular file atomically without following symlinks."""
    _assert_no_symlinks(path)
    _ensure_directory(path.parent)
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temporary, flags, mode)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _assert_no_symlinks(path)
        os.replace(temporary, path)
    finally:
        os.close(fd)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _managed_path(path_value: object, kind: str) -> Path:
    raw = Path(str(path_value)).expanduser()
    if not raw.is_absolute() or ".." in raw.parts:
        raise RuntimeError(f"unexpected {kind} path outside CODEX_HOME: {path_value}")
    path = Path(os.path.abspath(raw))
    home = _codex_home()
    if kind == "Agent":
        expected = {home / "agents" / f"{name}.toml" for name in AGENT_NAMES}
    elif kind == "launcher":
        name = "codex-blog.cmd" if os.name == "nt" else "codex-blog"
        expected = {home / "bin" / name}
    else:  # pragma: no cover - only fixed installer resource kinds call this helper
        raise RuntimeError(f"unknown managed resource kind: {kind}")
    if path not in expected:
        raise RuntimeError(f"unexpected {kind} path outside CODEX_HOME: {path}")
    _assert_no_symlinks(path)
    return path


def _run(*argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = list(argv)
    executable = shutil.which(command[0])
    if executable:
        command[0] = executable
    if os.name == "nt" and executable and Path(executable).suffix.lower() in {".bat", ".cmd"}:
        result = subprocess.run(
            subprocess.list2cmdline(command),
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    else:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", check=False
        )
    if check and result.returncode:
        message = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"{' '.join(argv[:3])}: {message}")
    return result


def _json_command(*argv: str) -> Any:
    result = _run(*argv)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{' '.join(argv[:3])} returned invalid JSON") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(_read_bytes(path)).hexdigest()


def _load_state() -> dict[str, Any]:
    path = _state_path()
    if not _regular_file_exists(path):
        return {}
    try:
        value = json.loads(_read_text(path))
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _version(plugin_root: Path) -> str:
    manifest = json.loads(
        (plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    return str(manifest["version"])


def _rows(payload: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        value = payload.get(key, [])
    else:
        value = payload
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _marketplaces() -> list[dict[str, Any]]:
    return _rows(_json_command("codex", "plugin", "marketplace", "list", "--json"), "marketplaces")


def _installed_plugins() -> list[dict[str, Any]]:
    return _rows(_json_command("codex", "plugin", "list", "--json"), "installed")


def _plugin_path() -> Path:
    for plugin in _installed_plugins():
        if plugin.get("pluginId") != PLUGIN_ID:
            continue
        raw_path = plugin.get("source", {}).get("path")
        if raw_path:
            path = Path(str(raw_path)).expanduser().resolve()
            if (path / ".codex-plugin" / "plugin.json").is_file():
                return path
    raise RuntimeError(f"Codex did not report an installed {PLUGIN_ID} source path")


def _validate_payload(plugin_root: Path) -> None:
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"plugin manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("name") != PLUGIN_NAME or manifest.get("version") != "2.1.1":
        raise RuntimeError("plugin identity/version is invalid")
    agents = {path.stem for path in (plugin_root / "agents").glob("*.toml")}
    if agents != AGENT_NAMES:
        raise RuntimeError(
            f"expected Agents {sorted(AGENT_NAMES)}, got {sorted(agents)}"
        )
    launcher = plugin_root / "bin" / "codex-blog"
    if not launcher.is_file():
        raise RuntimeError(f"plugin launcher is missing: {launcher}")


def _confirm_overwrite(path: Path, yes: bool, kind: str) -> None:
    if yes:
        return
    if not sys.stdin.isatty():
        raise RuntimeError(f"refusing to overwrite unmanaged {kind} {path}; rerun with --yes")
    try:
        answer = input(
            f"{kind} {path.name} exists and is not an unchanged Codex Blog file. "
            "Replace it? [y/N] "
        )
    except EOFError:
        answer = ""
    if answer.strip().lower() not in {"y", "yes"}:
        raise RuntimeError(f"installation cancelled to preserve {path}")


def _install_marketplace(
    previous: dict[str, Any],
    existing: dict[str, Any] | None,
    plugin_existing: bool,
) -> bool:
    if existing:
        current_root = Path(str(existing.get("root", ""))).expanduser().resolve()
        if current_root == REPO_ROOT:
            return bool(previous.get("marketplace_owned"))
        if previous.get("marketplace") != MARKETPLACE or not previous.get("marketplace_owned"):
            raise RuntimeError(
                f"marketplace {MARKETPLACE} already points to {current_root}; "
                "remove or rename it explicitly"
            )
        if plugin_existing:
            _run("codex", "plugin", "remove", PLUGIN_ID, "--json")
        _run("codex", "plugin", "marketplace", "remove", MARKETPLACE, "--json")
    _run("codex", "plugin", "marketplace", "add", str(REPO_ROOT), "--json")
    return True


def _install_plugin(
    previous: dict[str, Any], *, was_installed: bool
) -> tuple[Path, bool]:
    existing = next((row for row in _installed_plugins() if row.get("pluginId") == PLUGIN_ID), None)
    if existing:
        _run("codex", "plugin", "remove", PLUGIN_ID, "--json")
    _run("codex", "plugin", "add", PLUGIN_ID, "--json")
    owned = bool(previous.get("plugin_owned")) or not was_installed
    return _plugin_path(), owned


def _copy_agent(
    source: Path, destination: Path, previous: dict[str, Any] | None, yes: bool
) -> dict[str, Any]:
    destination = _managed_path(destination, "Agent")
    existed = _regular_file_exists(destination)
    same = existed and _sha256(destination) == _sha256(source)
    managed_unchanged = bool(
        previous
        and previous.get("owned")
        and previous.get("sha256") == (_sha256(destination) if existed else "")
    )
    if existed and not same and not managed_unchanged:
        _confirm_overwrite(destination, yes, "Agent")
    owned = bool(previous and previous.get("owned")) or not existed or not same
    if not same:
        _atomic_write(destination, source.read_bytes(), mode=0o644)
    return {"path": str(destination), "sha256": _sha256(destination), "owned": owned}


def _install_agents(plugin_root: Path, previous: dict[str, Any], yes: bool) -> list[dict[str, Any]]:
    source_dir = plugin_root / "agents"
    destination_dir = _codex_home() / "agents"
    _ensure_directory(destination_dir)
    old = {str(row.get("path")): row for row in previous.get("agents", [])}
    installed: list[dict[str, Any]] = []
    for name in sorted(AGENT_NAMES):
        source = source_dir / f"{name}.toml"
        destination = destination_dir / source.name
        installed.append(_copy_agent(source, destination, old.get(str(destination)), yes))
    return installed


def _preflight_conflicts(
    plugin_root: Path, previous: dict[str, Any], yes: bool
) -> None:
    """Resolve known file conflicts before making Codex CLI changes."""
    old = {str(row.get("path")): row for row in previous.get("agents", [])}
    for name in sorted(AGENT_NAMES):
        source = plugin_root / "agents" / f"{name}.toml"
        destination = _codex_home() / "agents" / source.name
        destination = _managed_path(destination, "Agent")
        if not _regular_file_exists(destination) or _sha256(destination) == _sha256(source):
            continue
        record = old.get(str(destination))
        if record and record.get("owned") and record.get("sha256") == _sha256(destination):
            continue
        _confirm_overwrite(destination, yes, "Agent")

    launcher_name = "codex-blog.cmd" if os.name == "nt" else "codex-blog"
    launcher = _managed_path(_codex_home() / "bin" / launcher_name, "launcher")
    if not _regular_file_exists(launcher):
        return
    expected = _launcher_content(plugin_root)
    if _read_text(launcher) == expected:
        return
    record = next(
        (row for row in previous.get("launchers", []) if row.get("path") == str(launcher)),
        None,
    )
    if record and record.get("owned") and record.get("sha256") == _sha256(launcher):
        return
    _confirm_overwrite(launcher, yes, "launcher")


def _launcher_content(plugin_root: Path) -> str:
    runtime = plugin_root / "bin" / "codex-blog"
    if os.name == "nt":
        return f'@echo off\r\n"{sys.executable}" "{runtime}" %*\r\n'
    python = str(Path(sys.executable).resolve()).replace("'", "'\"'\"'")
    script = str(runtime).replace("'", "'\"'\"'")
    return f"#!/bin/sh\nexec '{python}' '{script}' \"$@\"\n"


def _write_launcher(
    path: Path, plugin_root: Path, previous: dict[str, Any], yes: bool
) -> dict[str, Any]:
    path = _managed_path(path, "launcher")
    _ensure_directory(path.parent)
    content = _launcher_content(plugin_root)
    old = next(
        (row for row in previous.get("launchers", []) if row.get("path") == str(path)),
        None,
    )
    existed = _regular_file_exists(path)
    same = existed and _read_text(path) == content
    managed_unchanged = bool(
        old and old.get("owned") and old.get("sha256") == (_sha256(path) if existed else "")
    )
    if existed and not same and not managed_unchanged:
        _confirm_overwrite(path, yes, "launcher")
    owned = bool(old and old.get("owned")) or not existed or not same
    if not same:
        _atomic_write(path, content.encode("utf-8"), mode=0o755 if os.name != "nt" else 0o644)
    return {"path": str(path), "sha256": _sha256(path), "owned": owned}


def _save_state(state: dict[str, Any]) -> None:
    state_path = _state_path()
    _ensure_directory(state_path.parent, mode=0o700)
    _atomic_write(
        state_path,
        (json.dumps(state, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        mode=0o600,
    )


def _managed_install_paths() -> list[Path]:
    home = _codex_home()
    paths = [home / "agents" / f"{name}.toml" for name in sorted(AGENT_NAMES)]
    launcher_name = "codex-blog.cmd" if os.name == "nt" else "codex-blog"
    paths.append(home / "bin" / launcher_name)
    return paths


def _snapshot_files(paths: list[Path]) -> dict[Path, tuple[bytes, int] | None]:
    snapshots: dict[Path, tuple[bytes, int] | None] = {}
    for path in paths:
        kind = "Agent" if path.parent.name == "agents" else "launcher"
        path = _managed_path(path, kind)
        if _regular_file_exists(path):
            snapshots[path] = (_read_bytes(path), stat.S_IMODE(os.lstat(path).st_mode))
        else:
            snapshots[path] = None
    return snapshots


def _restore_files(snapshots: dict[Path, tuple[bytes, int] | None]) -> None:
    for path, snapshot in snapshots.items():
        if snapshot is None:
            if _regular_file_exists(path):
                path.unlink()
            continue
        data, mode = snapshot
        exists = _regular_file_exists(path)
        changed = (
            not exists
            or _read_bytes(path) != data
            or stat.S_IMODE(os.lstat(path).st_mode) != mode
        )
        if changed:
            _atomic_write(path, data, mode=mode)


def _rollback_codex(
    marketplace_before: dict[str, Any] | None,
    plugin_before: dict[str, Any] | None,
    *,
    marketplace_changed: bool,
    plugin_changed: bool,
) -> list[str]:
    failures: list[str] = []

    def compensate(*argv: str) -> bool:
        result = _run(*argv, check=False)
        if result.returncode:
            message = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            failures.append(f"{' '.join(argv[:3])}: {message}")
            return False
        return True

    if plugin_changed:
        try:
            plugin_present = any(
                row.get("pluginId") == PLUGIN_ID for row in _installed_plugins()
            )
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            failures.append(f"could not inspect plugin during compensation: {exc}")
            plugin_present = False
        if plugin_present:
            compensate("codex", "plugin", "remove", PLUGIN_ID, "--json")
    if marketplace_changed:
        try:
            marketplace_present = any(
                row.get("name") == MARKETPLACE for row in _marketplaces()
            )
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            failures.append(f"could not inspect marketplace during compensation: {exc}")
            marketplace_present = False
        if marketplace_present:
            compensate("codex", "plugin", "marketplace", "remove", MARKETPLACE, "--json")
        if marketplace_before:
            old_root = str(marketplace_before.get("root", ""))
            if old_root:
                compensate("codex", "plugin", "marketplace", "add", old_root, "--json")
    if plugin_changed and plugin_before:
        compensate("codex", "plugin", "add", PLUGIN_ID, "--json")
    return failures


def install(args: argparse.Namespace) -> int:
    if sys.version_info < (3, 10):  # noqa: UP036 - friendly failure on direct execution
        raise RuntimeError("Python 3.10 or newer is required")
    if not shutil.which("codex"):
        raise RuntimeError("Codex CLI is required")
    source_plugin = REPO_ROOT / "plugins" / PLUGIN_NAME
    _validate_payload(source_plugin)
    _ensure_directory(_codex_home())
    previous = _load_state()
    _preflight_conflicts(source_plugin, previous, args.yes)
    marketplace_before = next(
        (row for row in _marketplaces() if row.get("name") == MARKETPLACE), None
    )
    plugin_before = next(
        (row for row in _installed_plugins() if row.get("pluginId") == PLUGIN_ID), None
    )
    if marketplace_before:
        current_root = Path(
            str(marketplace_before.get("root", ""))
        ).expanduser().resolve()
        if current_root != REPO_ROOT and (
            previous.get("marketplace") != MARKETPLACE
            or not previous.get("marketplace_owned")
        ):
            raise RuntimeError(
                f"marketplace {MARKETPLACE} already points to {current_root}; "
                "remove or rename it explicitly"
            )
    marketplace_changed = bool(
        marketplace_before is None
        or Path(str(marketplace_before.get("root", ""))).expanduser().resolve() != REPO_ROOT
    )
    plugin_changed = bool(marketplace_changed and plugin_before)
    snapshots = _snapshot_files(_managed_install_paths())
    parent_directories = {path.parent: path.parent.is_dir() for path in snapshots}
    parent_directories[_state_path().parent] = _state_path().parent.is_dir()
    try:
        marketplace_owned = _install_marketplace(
            previous, marketplace_before, plugin_before is not None
        )
        plugin_changed = True
        plugin_root, plugin_owned = _install_plugin(
            previous, was_installed=plugin_before is not None
        )
        source_version = _version(source_plugin)
        installed_version = _version(plugin_root)
        if installed_version != source_version:
            raise RuntimeError(
                f"installed plugin version {installed_version} does not match source {source_version}"
            )
        _validate_payload(plugin_root)
        agents = _install_agents(plugin_root, previous, True)
        launcher_name = "codex-blog.cmd" if os.name == "nt" else "codex-blog"
        launcher = _codex_home() / "bin" / launcher_name
        launcher_record = _write_launcher(launcher, plugin_root, previous, True)
        state = {
            "schema_version": 1,
            "version": installed_version,
            "marketplace": MARKETPLACE,
            "marketplace_owned": marketplace_owned,
            "marketplace_source": str(REPO_ROOT),
            "plugin_id": PLUGIN_ID,
            "plugin_owned": plugin_owned,
            "plugin_path": str(plugin_root),
            "agents": agents,
            "launchers": [launcher_record],
        }
        _save_state(state)
    except Exception as exc:
        rollback_failures: list[str] = []
        try:
            _restore_files(snapshots)
            for directory, existed in parent_directories.items():
                if not existed:
                    try:
                        directory.rmdir()
                    except OSError:
                        pass
        except (OSError, RuntimeError) as rollback_exc:
            rollback_failures.append(str(rollback_exc))
        rollback_failures.extend(
            _rollback_codex(
                marketplace_before,
                plugin_before,
                marketplace_changed=marketplace_changed,
                plugin_changed=plugin_changed,
            )
        )
        if rollback_failures:
            raise RuntimeError(
                f"{exc}; compensation incomplete: {'; '.join(rollback_failures)}"
            ) from exc
        raise
    print("Installed Codex Blog 2.1.1 with 33 Skills and 6 Agents.")
    print(f"Add {_codex_home() / 'bin'} to PATH to use the codex-blog command.")
    print("No image provider, MCP, API key, or external SEO Skill was configured.")
    return 0


def _remove_if_unchanged(record: dict[str, Any], kind: str) -> bool:
    if not record.get("owned"):
        return True
    path = _managed_path(record.get("path", ""), kind)
    if not _regular_file_exists(path):
        return True
    if record.get("sha256") != _sha256(path):
        print(f"Preserved modified file: {path}", file=sys.stderr)
        return False
    path.unlink()
    return True


def uninstall(_: argparse.Namespace) -> int:
    state = _load_state()
    if not state:
        raise RuntimeError(f"no install state at {_state_path()}; refusing an unscoped uninstall")
    agents = state.get("agents", [])
    launchers = state.get("launchers", [])
    if not isinstance(agents, list) or not isinstance(launchers, list):
        raise TypeError("install state contains invalid resource records")
    if state.get("plugin_owned") and state.get("plugin_id") != PLUGIN_ID:
        raise RuntimeError(f"unexpected owned plugin in install state: {state.get('plugin_id')}")
    if state.get("marketplace_owned") and state.get("marketplace") != MARKETPLACE:
        raise RuntimeError(
            f"unexpected owned marketplace in install state: {state.get('marketplace')}"
        )
    for record in agents:
        if not isinstance(record, dict):
            raise TypeError("install state contains invalid Agent record")
        _managed_path(record.get("path", ""), "Agent")
    for record in launchers:
        if not isinstance(record, dict):
            raise TypeError("install state contains invalid launcher record")
        _managed_path(record.get("path", ""), "launcher")
    failures: list[str] = []
    remaining_agents: list[dict[str, Any]] = []
    remaining_launchers: list[dict[str, Any]] = []
    for record in agents:
        try:
            removed = _remove_if_unchanged(record, "Agent")
        except (OSError, RuntimeError) as exc:
            removed = False
            failures.append(f"Agent {record.get('path')}: {exc}")
        if record.get("owned") and not removed:
            remaining_agents.append(record)
            if not any(str(record.get("path")) in failure for failure in failures):
                failures.append(f"modified Agent preserved: {record.get('path')}")
    for record in launchers:
        try:
            removed = _remove_if_unchanged(record, "launcher")
        except (OSError, RuntimeError) as exc:
            removed = False
            failures.append(f"launcher {record.get('path')}: {exc}")
        if record.get("owned") and not removed:
            remaining_launchers.append(record)
            if not any(str(record.get("path")) in failure for failure in failures):
                failures.append(f"modified launcher preserved: {record.get('path')}")
    state["agents"] = remaining_agents
    state["launchers"] = remaining_launchers

    plugin_failed = False
    if state.get("plugin_owned") and state.get("plugin_id") == PLUGIN_ID:
        result = _run("codex", "plugin", "remove", PLUGIN_ID, "--json", check=False)
        if result.returncode:
            plugin_failed = True
            message = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            failures.append(f"plugin remove failed: {message}")
        else:
            state["plugin_owned"] = False
    if (
        not plugin_failed
        and state.get("marketplace_owned")
        and state.get("marketplace") == MARKETPLACE
    ):
        result = _run(
            "codex", "plugin", "marketplace", "remove", MARKETPLACE, "--json", check=False
        )
        if result.returncode:
            message = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            failures.append(f"marketplace remove failed: {message}")
        else:
            state["marketplace_owned"] = False
    if failures:
        _save_state(state)
        raise RuntimeError(
            "uninstall incomplete; ownership state retained for retry: " + "; ".join(failures)
        )
    data_dir = _state_path().parent
    expected = _codex_home() / "codex-blog"
    if data_dir != expected:  # pragma: no cover - state path is a fixed construction
        raise RuntimeError(f"unexpected state directory outside CODEX_HOME: {data_dir}")
    state_path = _state_path()
    if _regular_file_exists(state_path):
        state_path.unlink()
    try:
        data_dir.rmdir()
    except OSError:
        print(f"Preserved user-owned data in: {data_dir}", file=sys.stderr)
    print("Uninstalled Codex Blog. Modified and user-owned files were preserved.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codex-blog-installer")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("install", help="install Marketplace, plugin, Agents, and launcher")
    add.add_argument("--yes", action="store_true", help="replace conflicting unmanaged files")
    add.set_defaults(func=install)
    remove = commands.add_parser("uninstall", help="remove only owned, unchanged resources")
    remove.set_defaults(func=uninstall)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Codex Blog installer: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
