#!/usr/bin/env python3
"""Perform secret-safe, read-only checks for a configured image provider."""

from __future__ import annotations

import argparse
import json
import os
import shutil


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate image-provider prerequisites")
    result.add_argument("--command", help="Provider executable to locate")
    result.add_argument(
        "--secret-env",
        action="append",
        default=[],
        help="Required secret environment-variable name; repeatable",
    )
    result.add_argument(
        "--base-url-env",
        help="Optional environment-variable name containing a custom base URL",
    )
    result.add_argument("--json", action="store_true", help="Emit JSON")
    return result


def main() -> int:
    args = parser().parse_args()
    checks: list[dict[str, object]] = []

    if args.command:
        location = shutil.which(args.command)
        checks.append(
            {
                "check": "command",
                "name": args.command,
                "ok": location is not None,
                "detail": location or "not found",
            }
        )

    for name in args.secret_env:
        checks.append(
            {
                "check": "secret_env",
                "name": name,
                "ok": bool(os.environ.get(name)),
                "detail": "set" if os.environ.get(name) else "not set",
            }
        )

    if args.base_url_env:
        value = os.environ.get(args.base_url_env, "")
        checks.append(
            {
                "check": "base_url_env",
                "name": args.base_url_env,
                "ok": value.startswith(("https://", "http://localhost", "http://127.0.0.1")),
                "detail": "set" if value else "not set",
            }
        )

    ok = bool(checks) and all(bool(item["ok"]) for item in checks)
    payload = {"status": "ready" if ok else "not_ready", "checks": checks, "secrets_redacted": True}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for item in checks:
            marker = "PASS" if item["ok"] else "FAIL"
            print(f"[{marker}] {item['check']} {item['name']}: {item['detail']}")
        if not checks:
            print("No provider checks requested.")
        print(f"Status: {payload['status']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
