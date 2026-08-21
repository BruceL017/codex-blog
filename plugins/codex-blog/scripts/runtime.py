#!/usr/bin/env python3
"""Run the installed Codex Blog package directly from the plugin checkout."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _ensure_supported_python() -> None:
    if sys.version_info >= (3, 10):
        return
    override = os.environ.get("CODEX_BLOG_PYTHON")
    candidates = [override] if override else [
        "python3.14",
        "python3.13",
        "python3.12",
        "python3.11",
        "python3.10",
    ]
    current = Path(sys.executable).resolve()
    for candidate in candidates:
        if not candidate:
            continue
        executable = shutil.which(candidate)
        if not executable or Path(executable).resolve() == current:
            continue
        probe = subprocess.run(
            [executable, "-c", "import sys; raise SystemExit(sys.version_info < (3, 10))"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if probe.returncode == 0:
            os.execv(executable, [executable, str(Path(__file__).resolve()), *sys.argv[1:]])
    print("Codex Blog requires Python 3.10 or newer.", file=sys.stderr)
    raise SystemExit(2)


_ensure_supported_python()

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "src"))

from codex_blog.cli import main  # noqa: E402

raise SystemExit(main())
