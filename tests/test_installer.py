from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

state_path = Path(os.environ["FAKE_CODEX_STATE"])
try:
    state = json.loads(state_path.read_text())
except (OSError, ValueError):
    state = {"marketplace": False, "marketplace_root": "", "plugin": False, "calls": []}
args = sys.argv[1:]
state.setdefault("calls", []).append(args)

def save():
    state_path.write_text(json.dumps(state))

failure_key = " ".join(args[:3] if args[:2] == ["plugin", "marketplace"] else args[:2])
failures = state.setdefault("failures", {})
if int(failures.get(failure_key, 0)) > 0:
    failures[failure_key] = int(failures[failure_key]) - 1
    save()
    print("simulated failure: " + failure_key, file=sys.stderr)
    raise SystemExit(9)

if args[:3] == ["plugin", "marketplace", "list"]:
    rows = []
    if state["marketplace"]:
        rows.append({"name": "brucel017-codex-blog", "root": state["marketplace_root"]})
    print(json.dumps({"marketplaces": rows}))
elif args[:3] == ["plugin", "marketplace", "add"]:
    state["marketplace"] = True
    state["marketplace_root"] = args[3]
    save(); print("{}")
elif args[:3] == ["plugin", "marketplace", "remove"]:
    state["marketplace"] = False
    state["marketplace_root"] = ""
    save(); print("{}")
elif args[:2] == ["plugin", "list"]:
    rows = []
    if state["plugin"]:
        rows.append({
            "pluginId": "codex-blog@brucel017-codex-blog",
            "source": {"path": state.get("plugin_path") or os.path.join(os.environ["FAKE_REPO"], "plugins", "codex-blog")},
        })
    print(json.dumps({"installed": rows, "available": []}))
elif args[:2] == ["plugin", "add"]:
    state["plugin"] = True; save(); print("{}")
elif args[:2] == ["plugin", "remove"]:
    state["plugin"] = False; save(); print("{}")
else:
    save()
    print("unsupported fake command: " + repr(args), file=sys.stderr)
    raise SystemExit(2)
save()
'''


@pytest.fixture
def fake_environment(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "fake bin"
    bin_dir.mkdir()
    fake_script = bin_dir / "fake_codex.py"
    fake_script.write_text(FAKE_CODEX, encoding="utf-8")
    if os.name == "nt":
        codex = bin_dir / "codex.cmd"
        codex.write_text(f'@echo off\r\n"{sys.executable}" "{fake_script}" %*\r\n', encoding="utf-8")
    else:
        codex = bin_dir / "codex"
        codex.write_text(FAKE_CODEX, encoding="utf-8")
        codex.chmod(codex.stat().st_mode | stat.S_IXUSR)
    env = os.environ.copy()
    env.update(
        {
            "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
            "CODEX_HOME": str(tmp_path / "Codex Home With Spaces"),
            "FAKE_CODEX_STATE": str(tmp_path / "fake-state.json"),
            "FAKE_REPO": str(ROOT),
        }
    )
    return env


def _installer(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "install.py"), *args],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _fake_state(env: dict[str, str]) -> dict:
    return json.loads(Path(env["FAKE_CODEX_STATE"]).read_text(encoding="utf-8"))


def _symlink_or_skip(target: Path, link: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks are unavailable in this environment: {exc}")


def test_install_repeat_and_owned_uninstall(fake_environment: dict[str, str]) -> None:
    env = fake_environment
    first = _installer(env, "install")
    assert first.returncode == 0, first.stderr
    assert "No image provider" in first.stdout

    codex_home = Path(env["CODEX_HOME"])
    state_path = codex_home / "codex-blog" / "install-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert len(state["agents"]) == 6
    assert Path(state["plugin_path"]).name == "codex-blog"
    assert not any("mcp" in call for call in _fake_state(env)["calls"])

    launcher_name = "codex-blog.cmd" if os.name == "nt" else "codex-blog"
    launcher = codex_home / "bin" / launcher_name
    assert launcher.is_file()
    assert str(ROOT / "plugins" / "codex-blog" / "bin" / "codex-blog") in launcher.read_text()

    first_call_count = len(_fake_state(env)["calls"])
    repeated = _installer(env, "install")
    assert repeated.returncode == 0, repeated.stderr

    repeat_calls = _fake_state(env)["calls"][first_call_count:]
    remove_call = ["plugin", "remove", "codex-blog@brucel017-codex-blog", "--json"]
    add_call = ["plugin", "add", "codex-blog@brucel017-codex-blog", "--json"]
    assert remove_call in repeat_calls
    assert add_call in repeat_calls
    assert repeat_calls.index(remove_call) < repeat_calls.index(add_call)

    removed = _installer(env, "uninstall")
    assert removed.returncode == 0, removed.stderr
    assert not (codex_home / "agents" / "blog-writer.toml").exists()
    assert not state_path.exists()
    external = _fake_state(env)
    assert external["marketplace"] is False
    assert external["plugin"] is False


def test_install_failure_rolls_back_new_codex_resources(
    fake_environment: dict[str, str],
) -> None:
    env = fake_environment
    Path(env["FAKE_CODEX_STATE"]).write_text(
        json.dumps(
            {
                "marketplace": False,
                "marketplace_root": "",
                "plugin": False,
                "calls": [],
                "failures": {"plugin add": 1},
            }
        ),
        encoding="utf-8",
    )

    result = _installer(env, "install")

    assert result.returncode == 1
    external = _fake_state(env)
    assert external["marketplace"] is False
    assert external["plugin"] is False
    codex_home = Path(env["CODEX_HOME"])
    assert not (codex_home / "codex-blog" / "install-state.json").exists()
    assert not list((codex_home / "agents").glob("*.toml"))


def test_install_rejects_installed_version_that_does_not_match_source(
    fake_environment: dict[str, str], tmp_path: Path
) -> None:
    env = fake_environment
    cached_plugin = tmp_path / "stale-plugin-cache"
    shutil.copytree(ROOT / "plugins" / "codex-blog", cached_plugin)
    manifest_path = cached_plugin / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = "2.0.0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    Path(env["FAKE_CODEX_STATE"]).write_text(
        json.dumps(
            {
                "marketplace": False,
                "marketplace_root": "",
                "plugin": False,
                "plugin_path": str(cached_plugin),
                "calls": [],
            }
        ),
        encoding="utf-8",
    )

    result = _installer(env, "install")

    assert result.returncode == 1
    assert "does not match source" in result.stderr
    external = _fake_state(env)
    assert external["marketplace"] is False
    assert external["plugin"] is False


def test_preexisting_matching_resources_are_not_owned(fake_environment: dict[str, str]) -> None:
    env = fake_environment
    source = ROOT / "plugins" / "codex-blog" / "agents" / "blog-writer.toml"
    destination = Path(env["CODEX_HOME"]) / "agents" / source.name
    destination.parent.mkdir(parents=True)
    destination.write_bytes(source.read_bytes())
    Path(env["FAKE_CODEX_STATE"]).write_text(
        json.dumps(
            {
                "marketplace": True,
                "marketplace_root": str(ROOT),
                "plugin": True,
                "calls": [],
            }
        ),
        encoding="utf-8",
    )

    installed = _installer(env, "install")
    assert installed.returncode == 0, installed.stderr
    state_path = Path(env["CODEX_HOME"]) / "codex-blog" / "install-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    record = next(row for row in state["agents"] if row["path"] == str(destination))
    assert record["owned"] is False
    assert state["marketplace_owned"] is False
    assert state["plugin_owned"] is False

    removed = _installer(env, "uninstall")
    assert removed.returncode == 0, removed.stderr
    assert destination.is_file()
    external = _fake_state(env)
    assert external["marketplace"] is True
    assert external["plugin"] is True


def test_modified_owned_file_keeps_retryable_uninstall_state(
    fake_environment: dict[str, str],
) -> None:
    env = fake_environment
    installed = _installer(env, "install")
    assert installed.returncode == 0, installed.stderr
    codex_home = Path(env["CODEX_HOME"])
    state_path = codex_home / "codex-blog" / "install-state.json"
    modified = codex_home / "agents" / "blog-seo.toml"
    modified.write_text(modified.read_text() + "\n# user customization\n", encoding="utf-8")

    removed = _installer(env, "uninstall")

    assert removed.returncode == 1
    assert modified.is_file()
    assert state_path.is_file()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert [Path(row["path"]).name for row in state["agents"]] == ["blog-seo.toml"]


def test_plugin_remove_failure_keeps_state_and_marketplace_for_retry(
    fake_environment: dict[str, str],
) -> None:
    env = fake_environment
    installed = _installer(env, "install")
    assert installed.returncode == 0, installed.stderr
    fake_state_path = Path(env["FAKE_CODEX_STATE"])
    external = _fake_state(env)
    external.setdefault("failures", {})["plugin remove"] = 1
    fake_state_path.write_text(json.dumps(external), encoding="utf-8")

    failed = _installer(env, "uninstall")

    assert failed.returncode == 1
    codex_home = Path(env["CODEX_HOME"])
    state_path = codex_home / "codex-blog" / "install-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["plugin_owned"] is True
    assert state["marketplace_owned"] is True
    assert _fake_state(env)["plugin"] is True
    assert _fake_state(env)["marketplace"] is True

    retried = _installer(env, "uninstall")
    assert retried.returncode == 0, retried.stderr
    assert not state_path.exists()


def test_marketplace_remove_failure_updates_retryable_uninstall_state(
    fake_environment: dict[str, str],
) -> None:
    env = fake_environment
    installed = _installer(env, "install")
    assert installed.returncode == 0, installed.stderr
    fake_state_path = Path(env["FAKE_CODEX_STATE"])
    external = _fake_state(env)
    external.setdefault("failures", {})["plugin marketplace remove"] = 1
    fake_state_path.write_text(json.dumps(external), encoding="utf-8")

    failed = _installer(env, "uninstall")

    assert failed.returncode == 1
    state_path = Path(env["CODEX_HOME"]) / "codex-blog" / "install-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["plugin_owned"] is False
    assert state["marketplace_owned"] is True
    assert state["agents"] == []
    assert state["launchers"] == []
    assert _fake_state(env)["plugin"] is False
    assert _fake_state(env)["marketplace"] is True

    retried = _installer(env, "uninstall")
    assert retried.returncode == 0, retried.stderr
    assert not state_path.exists()


def test_unmanaged_agent_refuses_before_codex_changes(fake_environment: dict[str, str]) -> None:
    env = fake_environment
    destination = Path(env["CODEX_HOME"]) / "agents" / "blog-reviewer.toml"
    destination.parent.mkdir(parents=True)
    destination.write_text('name = "user-owned"\n', encoding="utf-8")

    refused = _installer(env, "install")
    assert refused.returncode == 1
    assert "refusing to overwrite unmanaged Agent" in refused.stderr
    assert "user-owned" in destination.read_text(encoding="utf-8")
    assert not Path(env["FAKE_CODEX_STATE"]).exists()

    accepted = _installer(env, "install", "--yes")
    assert accepted.returncode == 0, accepted.stderr
    source = ROOT / "plugins" / "codex-blog" / "agents" / "blog-reviewer.toml"
    assert destination.read_bytes() == source.read_bytes()


def test_wrong_marketplace_root_is_preserved(fake_environment: dict[str, str]) -> None:
    env = fake_environment
    state_path = Path(env["FAKE_CODEX_STATE"])
    state_path.write_text(
        json.dumps(
            {
                "marketplace": True,
                "marketplace_root": str(ROOT.parent / "different-repo"),
                "plugin": False,
                "calls": [],
            }
        ),
        encoding="utf-8",
    )
    result = _installer(env, "install")
    assert result.returncode == 1
    assert "already points" in result.stderr
    external = _fake_state(env)
    assert external["marketplace"] is True
    assert not any(call[:2] in (["plugin", "remove"], ["plugin", "add"]) for call in external["calls"])
    assert not any(
        call[:3]
        in (["plugin", "marketplace", "remove"], ["plugin", "marketplace", "add"])
        for call in external["calls"]
    )


def test_uninstall_without_state_refuses_scope(fake_environment: dict[str, str]) -> None:
    result = _installer(fake_environment, "uninstall")
    assert result.returncode == 1
    assert "refusing an unscoped uninstall" in result.stderr


def test_install_rejects_symlinked_codex_home(fake_environment: dict[str, str], tmp_path: Path) -> None:
    env = fake_environment
    real_home = tmp_path / "attacker-controlled-home"
    real_home.mkdir()
    linked_home = tmp_path / "linked-codex-home"
    _symlink_or_skip(real_home, linked_home, directory=True)
    env["CODEX_HOME"] = str(linked_home)

    result = _installer(env, "install")

    assert result.returncode == 1
    assert "symlink" in result.stderr.lower()
    assert list(real_home.iterdir()) == []
    assert not Path(env["FAKE_CODEX_STATE"]).exists()


def test_install_rejects_symlinked_destination_directory(
    fake_environment: dict[str, str], tmp_path: Path
) -> None:
    env = fake_environment
    codex_home = Path(env["CODEX_HOME"])
    codex_home.mkdir()
    redirected_agents = tmp_path / "redirected-agents"
    redirected_agents.mkdir()
    _symlink_or_skip(redirected_agents, codex_home / "agents", directory=True)

    result = _installer(env, "install")

    assert result.returncode == 1
    assert "symlink" in result.stderr.lower()
    assert list(redirected_agents.iterdir()) == []
    assert not Path(env["FAKE_CODEX_STATE"]).exists()


def test_uninstall_rejects_symlinked_state_directory(
    fake_environment: dict[str, str], tmp_path: Path
) -> None:
    env = fake_environment
    codex_home = Path(env["CODEX_HOME"])
    codex_home.mkdir()
    redirected_state = tmp_path / "redirected-state"
    redirected_state.mkdir()
    state_path = redirected_state / "install-state.json"
    state_path.write_text(
        json.dumps({"schema_version": 1, "agents": [], "launchers": []}),
        encoding="utf-8",
    )
    _symlink_or_skip(redirected_state, codex_home / "codex-blog", directory=True)

    result = _installer(env, "uninstall")

    assert result.returncode == 1
    assert "symlink" in result.stderr.lower()
    assert state_path.is_file()


def test_uninstall_rejects_state_record_outside_codex_home(
    fake_environment: dict[str, str], tmp_path: Path
) -> None:
    env = fake_environment
    codex_home = Path(env["CODEX_HOME"])
    state_path = codex_home / "codex-blog" / "install-state.json"
    state_path.parent.mkdir(parents=True)
    outside = tmp_path / "must-not-delete.toml"
    outside.write_text("protected\n", encoding="utf-8")
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "agents": [
                    {
                        "path": str(outside),
                        "sha256": "invalid-is-enough-to-test-scope-first",
                        "owned": True,
                    }
                ],
                "launchers": [],
            }
        ),
        encoding="utf-8",
    )

    result = _installer(env, "uninstall")

    assert result.returncode == 1
    assert "outside" in result.stderr.lower() or "unexpected" in result.stderr.lower()
    assert outside.read_text(encoding="utf-8") == "protected\n"
    assert state_path.is_file()


def test_uninstall_rejects_owned_external_identity_without_deleting_state(
    fake_environment: dict[str, str],
) -> None:
    env = fake_environment
    codex_home = Path(env["CODEX_HOME"])
    state_path = codex_home / "codex-blog" / "install-state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "plugin_owned": True,
                "plugin_id": "different-plugin@example",
                "marketplace_owned": True,
                "marketplace": "different-marketplace",
                "agents": [],
                "launchers": [],
            }
        ),
        encoding="utf-8",
    )

    result = _installer(env, "uninstall")

    assert result.returncode == 1
    assert "unexpected owned plugin" in result.stderr
    assert state_path.is_file()
    assert not Path(env["FAKE_CODEX_STATE"]).exists()


def test_uninstall_does_not_follow_owned_file_symlink(
    fake_environment: dict[str, str], tmp_path: Path
) -> None:
    env = fake_environment
    installed = _installer(env, "install")
    assert installed.returncode == 0, installed.stderr

    agent = Path(env["CODEX_HOME"]) / "agents" / "blog-writer.toml"
    external = tmp_path / "external-blog-writer.toml"
    external.write_bytes(agent.read_bytes())
    agent.unlink()
    _symlink_or_skip(external, agent)

    result = _installer(env, "uninstall")

    assert result.returncode == 1
    assert "symlink" in result.stderr.lower()
    assert external.is_file()
    assert agent.is_symlink()


def test_atomic_write_preserves_existing_file_if_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = ROOT / "scripts" / "install.py"
    spec = importlib.util.spec_from_file_location("_test_installer_module", module_path)
    assert spec and spec.loader
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)

    target = tmp_path / "state.json"
    target.write_bytes(b"old-state\n")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(installer.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        installer._atomic_write(target, b"new-state\n", mode=0o600)

    assert target.read_bytes() == b"old-state\n"
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_atomic_write_closes_temporary_file_before_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = ROOT / "scripts" / "install.py"
    spec = importlib.util.spec_from_file_location("_closed_fd_installer_module", module_path)
    assert spec and spec.loader
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)

    target = tmp_path / "state.json"
    opened_fd: int | None = None
    real_open = installer.os.open
    real_fstat = installer.os.fstat
    real_replace = installer.os.replace

    def track_open(path: Path, flags: int, mode: int = 0o777) -> int:
        nonlocal opened_fd
        opened_fd = real_open(path, flags, mode)
        return opened_fd

    def replace_only_after_close(source: Path, destination: Path) -> None:
        assert opened_fd is not None
        with pytest.raises(OSError):
            real_fstat(opened_fd)
        real_replace(source, destination)

    monkeypatch.setattr(installer.os, "open", track_open)
    monkeypatch.setattr(installer.os, "replace", replace_only_after_close)

    installer._atomic_write(target, b"new-state\n", mode=0o600)

    assert target.read_bytes() == b"new-state\n"


def test_state_write_failure_rolls_back_files_and_codex_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = ROOT / "scripts" / "install.py"
    spec = importlib.util.spec_from_file_location("_transaction_installer_module", module_path)
    assert spec and spec.loader
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr(installer.shutil, "which", lambda _name: "/fake/codex")
    external = {"marketplace": False, "plugin": False}

    def marketplaces() -> list[dict[str, str]]:
        if not external["marketplace"]:
            return []
        return [{"name": installer.MARKETPLACE, "root": str(installer.REPO_ROOT)}]

    def plugins() -> list[dict[str, object]]:
        if not external["plugin"]:
            return []
        return [
            {
                "pluginId": installer.PLUGIN_ID,
                "source": {
                    "path": str(installer.REPO_ROOT / "plugins" / installer.PLUGIN_NAME)
                },
            }
        ]

    def run(*argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        if argv[1:4] == ("plugin", "marketplace", "add"):
            external["marketplace"] = True
        elif argv[1:4] == ("plugin", "marketplace", "remove"):
            external["marketplace"] = False
        elif argv[1:3] == ("plugin", "add"):
            external["plugin"] = True
        elif argv[1:3] == ("plugin", "remove"):
            external["plugin"] = False
        return subprocess.CompletedProcess(list(argv), 0, "{}", "")

    monkeypatch.setattr(installer, "_marketplaces", marketplaces)
    monkeypatch.setattr(installer, "_installed_plugins", plugins)
    monkeypatch.setattr(installer, "_run", run)
    monkeypatch.setattr(
        installer, "_save_state", lambda _state: (_ for _ in ()).throw(OSError("disk full"))
    )

    with pytest.raises(OSError, match="disk full"):
        installer.install(Namespace(yes=True))

    assert external == {"marketplace": False, "plugin": False}
    assert not list((codex_home / "agents").glob("*.toml"))
    launcher_name = "codex-blog.cmd" if os.name == "nt" else "codex-blog"
    assert not (codex_home / "bin" / launcher_name).exists()
    assert not (codex_home / "codex-blog" / "install-state.json").exists()
