#!/usr/bin/env python3
"""Article-first compatibility preflight for Codex Blog.

The complete SEO Markdown article is the only blocking artifact. Renderer,
schema, link, PDF, and image state are reported from run-manifest.json but do
not block delivery. Use visual_preflight.py explicitly after opting into
images when viewport screenshots and strict visual asset checks are desired.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "src"))

from codex_blog.article import review_article  # noqa: E402
from codex_blog.pipeline import load_manifest, load_request  # noqa: E402
from codex_blog.utils import atomic_write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", "--run", dest="run", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--gate", type=int, choices=range(1, 6), help="Accepted for legacy callers; core review always runs")
    parser.add_argument("--init-review-nonce", action="store_true", help="Legacy no-op")
    parser.add_argument("--reset-iterations", action="store_true", help="Legacy no-op")
    parser.add_argument("--increment-iteration", action="store_true", help="Legacy no-op")
    args, _ = parser.parse_known_args()

    run_dir = Path(args.run).resolve()
    manifest = load_manifest(run_dir)
    request = load_request(run_dir)
    review = review_article(Path(manifest.article), request)
    report = {
        "schema_version": 1,
        "contract": "article-first",
        "core_complete": review.complete,
        "delivery_blocked": not review.complete,
        "errors": review.errors,
        "warnings": review.warnings,
        "metrics": review.metrics,
        "stages": {name: stage.to_dict() for name, stage in manifest.stages.items()},
        "images": {
            "mode": manifest.image_mode,
            "status": manifest.image_status,
            "required": False,
        },
    }
    atomic_write_json(run_dir / "preflight-report.json", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("PASS: complete SEO Markdown" if review.complete else "BLOCKED: incomplete SEO Markdown")
        for warning in review.warnings:
            print(f"WARN: {warning}", file=sys.stderr)
    return 0 if review.complete or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
