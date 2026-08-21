#!/usr/bin/env python3
"""Install a built wheel in isolation and exercise bundled runtime resources."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import venv
from pathlib import Path


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(argv)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _python(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _launcher(environment: Path) -> Path:
    return environment / ("Scripts/codex-blog.exe" if os.name == "nt" else "bin/codex-blog")


def _article(keyword: str) -> str:
    return f"""---
title: {keyword}: A Practical Guide
description: A complete guide to planning, running, and reviewing a resilient content workflow.
slug: standalone-content-workflow
primary_keyword: {keyword}
---

# {keyword}: A Practical Guide

The {keyword} approach gives content teams a dependable way to move from a
search need to a useful article without making optional production work part of
the writing contract. A durable process identifies the intended reader,
clarifies the question that brought that reader to the page, records which
sources may support each claim, and saves the article before attempting extra
formats. This guide explains how to prepare that work, review it, and hand it
off while preserving a complete reader-facing result.

## Start with a clear writing contract

A reliable workflow begins with a compact writing contract. It names the
primary topic, the reader's situation, the search intent, the page type, and the
decision or task the article should help with. It also separates direct
evidence from assumptions and ideas that still need checking. That distinction
prevents a promising note from becoming a confident factual statement merely
because it appeared in a brief.

The outline should answer the main question early and arrange later sections in
the order a reader naturally needs them. Each section needs a clear purpose,
enough explanation to stand on its own, and a connection to the overall
promise. Source notes stay attached to the claims they support, while brand
voice and internal-link suggestions remain guidance rather than substitutes for
useful information. With this contract in place, the writer can concentrate on
coherent prose instead of negotiating the deliverable during every paragraph.

## Finish the article before optional production

The Markdown article is the stable checkpoint. It should contain descriptive
metadata, one clear main heading, a useful opening, substantive sections, and a
conclusion that helps the reader act. It should not contain unfinished markers,
broken visual references, invented citations, or instructions intended only
for the production team. A person who receives only this file should still get
the complete explanation promised by the title.

Once that checkpoint exists, downstream work can enrich it. Structured data can
describe the visible article, HTML can support browser review, PDF can support
offline circulation, and platform detection can prepare a handoff for the
current site target. These outputs are valuable, but they should not redefine
whether the article is complete. If a renderer or checker is unavailable, the
run report records the failed attempts and the article remains available.

Image work belongs even later. A deferred run does not inspect provider
configuration, create placeholders, or treat the lack of a cover as a quality
defect. After non-image work reaches a terminal state, the user can decline
images, request a cover, or request a cover with a small set of relevant inline
illustrations. That choice resumes from saved state and does not rewrite the
body.

## Review claims and preserve state

An editorial pass checks whether the article answers the intended query,
whether headings match their sections, and whether the conclusion follows from
the preceding explanation. Confirmed errors should be corrected or removed.
Specific claims that cannot be verified should become careful qualitative
language or disappear, rather than surviving as confident assertions. This
keeps uncertainty visible without leaving internal review notes in published
copy.

The run manifest makes the workflow auditable. It records the normalized
request, the digest of the saved article, stage attempts, warnings, artifacts,
and the image decision. A completed stage is not repeated during resume. A
failed optional stage gets its bounded retry and then becomes degraded or
skipped, so later work can continue without erasing earlier success.

## Conclusion

An article-first pipeline protects the result that matters most: a complete,
useful article. Define the reader and evidence boundaries, finish the Markdown,
review the claims, and then attempt optional formats as independent
enhancements. This order keeps production resumable and transparent while
ensuring that a missing renderer, checker, or image provider cannot hold the
core publication draft hostage.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path, help="Wheel file or directory containing one wheel")
    args = parser.parse_args(argv)
    supplied = args.wheel.resolve()
    if supplied.is_dir():
        wheels = sorted(supplied.glob("*.whl"))
        if len(wheels) != 1:
            raise SystemExit(f"expected one wheel in {supplied}, found {len(wheels)}")
        wheel = wheels[0]
    else:
        wheel = supplied
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise SystemExit(f"wheel not found: {wheel}")

    with tempfile.TemporaryDirectory(prefix="codex-blog-wheel-") as raw:
        root = Path(raw).resolve()
        smoke_env = os.environ.copy()
        smoke_env["CODEX_HOME"] = str(root / "codex-home")
        smoke_env.pop("CODEX_BLOG_IMAGE_CONFIG", None)
        smoke_env.pop("CODEX_BLOG_DATA_DIR", None)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=os.name != "nt").create(environment)
        python = _python(environment)
        _run(
            [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
            env=smoke_env,
        )
        launcher = _launcher(environment)

        doctor = json.loads(_run([str(launcher), "doctor"], cwd=root, env=smoke_env).stdout)
        if doctor.get("skills") != 33 or doctor.get("agents") != 6:
            raise RuntimeError(f"wheel resource inventory is incomplete: {doctor}")
        if doctor.get("configured_image_providers") != []:
            raise RuntimeError(f"isolated default unexpectedly discovered image providers: {doctor}")
        if Path(str(doctor.get("plugin_root", ""))).name != "_bundle":
            raise RuntimeError(f"wheel did not select its packaged resource root: {doctor}")
        bundle_root = Path(doctor["plugin_root"])
        for name in (
            "pyproject.toml",
            "LICENSE",
            "NOTICE",
            "THIRD_PARTY.md",
            "UPSTREAM.md",
            "LICENSES/Apache-2.0.txt",
            "LICENSES/CC-BY-4.0.txt",
            "LICENSES/semantic-cluster-engine-MIT.txt",
            "schemas/cluster-run-manifest.schema.json",
        ):
            if not (bundle_root / name).is_file():
                raise RuntimeError(f"wheel attribution or package metadata is missing: {name}")

        project = root / "project"
        project.mkdir()
        _run(
            [str(launcher), "init", "--project-root", str(project)],
            cwd=project,
            env=smoke_env,
        )
        prepared = json.loads(
            _run(
                [
                    str(launcher),
                    "prepare",
                    "Standalone wheel smoke",
                    "--keyword",
                    "standalone content workflow",
                    "--output-root",
                    str(project / ".codex-blog" / "output"),
                    "--word-count",
                    "500",
                ],
                cwd=project,
                env=smoke_env,
            ).stdout
        )
        run_dir = Path(prepared["run_dir"])
        article = Path(prepared["article"])
        article.write_text(_article("Standalone content workflow"), encoding="utf-8")
        finalized = json.loads(
            _run(
                [
                    str(launcher),
                    "finalize",
                    "--run",
                    str(run_dir),
                    "--project-root",
                    str(project),
                    "--skip-external-links",
                ],
                cwd=project,
                env=smoke_env,
            ).stdout
        )
        if finalized.get("status") not in {"complete", "complete_with_warnings"}:
            raise RuntimeError(f"wheel finalization did not deliver the article: {finalized}")
        if finalized.get("image_prompt_required") is not True:
            raise RuntimeError(f"first finalization did not emit the image question: {finalized}")
        if finalized.get("image_prompt") != (
            "The article and non-image outputs are complete. Generate images now?"
        ):
            raise RuntimeError(f"unexpected deferred-image question: {finalized}")
        manifest_path = run_dir / "run-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("image_status") != "not_requested" or (run_dir / "images").exists():
            raise RuntimeError("default wheel run created or requested images")
        if manifest.get("image_decision") != "asked":
            raise RuntimeError(f"manifest did not claim the one-time image question: {manifest}")
        for field in (
            "article_digest",
            "request_digest",
            "language",
            "template",
            "provenance",
            "conflicts",
            "image_decision",
        ):
            if field not in manifest:
                raise RuntimeError(f"manifest is missing required field: {field}")
        if len(manifest["article_digest"]) != 64 or len(manifest["request_digest"]) != 64:
            raise RuntimeError("manifest digests are not populated")
        if any(
            stage.get("attempts", 0) > 2
            for name, stage in manifest.get("stages", {}).items()
            if name != "core_article"
        ):
            raise RuntimeError("a downstream stage exceeded the one-retry limit")

        article_before_resume = article.read_bytes()
        attempts_before_resume = {
            name: stage.get("attempts", 0)
            for name, stage in manifest.get("stages", {}).items()
        }
        resumed = json.loads(
            _run(
                [
                    str(launcher),
                    "finalize",
                    "--run",
                    str(run_dir),
                    "--project-root",
                    str(project),
                    "--skip-external-links",
                ],
                cwd=project,
                env=smoke_env,
            ).stdout
        )
        if resumed.get("image_prompt_required") is not False or resumed.get("image_prompt") is not None:
            raise RuntimeError(f"deferred-image question was emitted more than once: {resumed}")
        resumed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        attempts_after_resume = {
            name: stage.get("attempts", 0)
            for name, stage in resumed_manifest.get("stages", {}).items()
        }
        if attempts_after_resume != attempts_before_resume:
            raise RuntimeError("resume repeated an already terminal stage")
        if article.read_bytes() != article_before_resume:
            raise RuntimeError("resume rewrote the complete article")

        _run(
            [str(launcher), "run", "lint_prose.py", "--help"],
            cwd=project,
            env=smoke_env,
        )
        _run(
            [str(launcher), "run", "generate_agents.py", "--check"],
            cwd=project,
            env=smoke_env,
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "wheel": wheel.name,
                    "skills": doctor["skills"],
                    "agents": doctor["agents"],
                    "status": finalized["status"],
                    "images": manifest["image_status"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
