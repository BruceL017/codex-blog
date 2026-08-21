"""Build hook that embeds the Codex plugin runtime in standalone wheels."""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

ROOT = Path(__file__).resolve().parent
BUNDLE_DIRS = (
    ".codex-plugin",
    "agents",
    "agents-src",
    "assets",
    "branding",
    "data",
    "LICENSES",
    "schemas",
    "scripts",
    "skills",
)
BUNDLE_FILES = (
    "CHANGELOG.md",
    "CITATION.cff",
    "LICENSE",
    "NOTICE",
    "THIRD_PARTY.md",
    "UPSTREAM.md",
    "README.md",
    "pyproject.toml",
    "requirements.lock",
)


def _reject_symlinks(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError(f"refusing to bundle symlink: {path.relative_to(ROOT)}")
    if path.is_dir():
        for child in path.rglob("*"):
            if child.is_symlink():
                raise RuntimeError(f"refusing to bundle symlink: {child.relative_to(ROOT)}")


class BundlePluginBuild(_build_py):
    """Copy maintained plugin resources into codex_blog/_bundle at build time."""

    def run(self) -> None:
        super().run()
        package = Path(self.build_lib).resolve() / "codex_blog"
        bundle = package / "_bundle"
        expected_parent = package.resolve()
        if bundle.parent.resolve() != expected_parent:
            raise RuntimeError(f"unsafe bundle target: {bundle}")
        if bundle.exists():
            shutil.rmtree(bundle)
        bundle.mkdir(parents=True)
        for name in BUNDLE_DIRS:
            source = ROOT / name
            if not source.is_dir():
                raise RuntimeError(f"required bundle directory is missing: {name}")
            _reject_symlinks(source)
            shutil.copytree(
                source,
                bundle / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
            )
        for name in BUNDLE_FILES:
            source = ROOT / name
            if not source.is_file():
                raise RuntimeError(f"required bundle file is missing: {name}")
            _reject_symlinks(source)
            shutil.copy2(source, bundle / name)
        self.announce(f"bundled Codex plugin resources in {bundle}", level=2)


setup(cmdclass={"build_py": BundlePluginBuild})
