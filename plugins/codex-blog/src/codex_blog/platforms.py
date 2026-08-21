from __future__ import annotations

from pathlib import Path

from .utils import atomic_write_json, atomic_write_text, safe_read_text

SIGNALS = (
    ("nextjs-mdx", ("next.config.js", "next.config.mjs", "next.config.ts"), "mdx"),
    ("astro", ("astro.config.mjs", "astro.config.ts"), "markdown"),
    ("hugo", ("hugo.toml", "config.toml"), "markdown"),
    ("jekyll", ("_config.yml", "_config.yaml"), "markdown"),
    ("wordpress", ("wp-config.php", "wp-content"), "html"),
    ("ghost", ("ghost", "content/themes"), "html"),
    ("eleventy", (".eleventy.js", "eleventy.config.js"), "markdown"),
    ("gatsby", ("gatsby-config.js", "gatsby-config.ts"), "mdx"),
)


def detect_platform(root: Path) -> dict[str, str]:
    for platform, signals, output in SIGNALS:
        for signal in signals:
            if (root / signal).exists():
                return {"platform": platform, "format": output, "signal": signal}
    return {"platform": "static", "format": "markdown", "signal": "default"}


def adapt_platform(article: Path, project_root: Path, run_dir: Path) -> list[Path]:
    """Create one detected-platform handoff artifact without publishing it."""
    detected = detect_platform(project_root)
    platform = detected["platform"]
    output_format = detected["format"]
    destination_dir = run_dir / "platform"
    if destination_dir.is_symlink():
        raise ValueError(f"refusing symlink platform directory: {destination_dir}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    if destination_dir.is_symlink() or destination_dir.resolve().parent != run_dir.resolve():
        raise ValueError("platform directory must stay inside the run directory")
    if output_format == "html":
        source = run_dir / f"{article.stem}.html"
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"HTML is unavailable for the detected {platform} handoff")
        destination = destination_dir / f"{article.stem}.{platform}.html"
    else:
        source = article
        suffix = ".mdx" if output_format == "mdx" else ".md"
        destination = destination_dir / f"{article.stem}.{platform}{suffix}"
    if source.is_symlink():
        raise ValueError(f"refusing symlink platform source: {source}")
    if destination.parent.resolve() != destination_dir.resolve():
        raise ValueError("platform artifact must stay inside the platform directory")
    atomic_write_text(destination, safe_read_text(source, label="platform source"))
    report = run_dir / "platform-report.json"
    atomic_write_json(
        report,
        {
            **detected,
            "artifact": str(destination),
            "publish_performed": False,
            "policy": "Handoff artifact only; Codex Blog never publishes to a CMS automatically.",
        },
    )
    return [destination, report]
