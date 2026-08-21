#!/usr/bin/env python3
"""Create a secret-free Codex MCP image-provider configuration plan.

This helper intentionally does not edit Codex configuration or install a
package. It prints the values an operator can pass to the Codex Blog installer
or add to their existing MCP configuration after reviewing the provider.
"""

from __future__ import annotations

import argparse
import json
import re


NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Print a secret-free Codex MCP image-provider setup plan"
    )
    result.add_argument("--name", required=True, help="Codex MCP server name")
    result.add_argument("--command", required=True, help="Reviewed executable name")
    result.add_argument("--arg", action="append", default=[], help="Command argument; repeatable")
    result.add_argument(
        "--secret-env",
        action="append",
        default=[],
        help="Environment-variable name containing a secret; repeatable",
    )
    result.add_argument("--json", action="store_true", help="Emit JSON")
    return result


def main() -> int:
    args = parser().parse_args()
    if not NAME_RE.fullmatch(args.name):
        raise SystemExit("--name must contain only letters, digits, underscore, or hyphen")
    invalid = [name for name in args.secret_env if not ENV_RE.fullmatch(name)]
    if invalid:
        raise SystemExit(f"invalid environment-variable name: {invalid[0]}")

    plan = {
        "status": "plan",
        "writes_performed": False,
        "server": args.name,
        "command": args.command,
        "args": args.arg,
        "secret_env": args.secret_env,
        "next_step": (
            "Review the command/package, configure it as an MCP server in Codex, "
            "and export the named secret variables outside project files."
        ),
    }
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print(f"MCP server: {plan['server']}")
        print(f"Command: {plan['command']}")
        print(f"Arguments: {json.dumps(plan['args'])}")
        print(f"Secret environment variables: {', '.join(plan['secret_env']) or 'none'}")
        print(plan["next_step"])
        print("No files were changed and no package was installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
