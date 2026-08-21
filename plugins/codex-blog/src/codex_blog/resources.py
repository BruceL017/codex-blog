from __future__ import annotations

from pathlib import Path


def plugin_root() -> Path:
    """Return the source plugin root or the resource root bundled in a wheel."""
    package_root = Path(__file__).resolve().parent
    candidates = (package_root.parents[1], package_root / "_bundle")
    for candidate in candidates:
        if (
            (candidate / "scripts" / "blog_render.py").is_file()
            and (candidate / "skills" / "blog" / "SKILL.md").is_file()
            and (candidate / "agents").is_dir()
        ):
            return candidate
    raise RuntimeError(
        "Codex Blog resources are missing; reinstall from the plugin source or a complete wheel"
    )
