#!/usr/bin/env python3
"""Return success for a usable Codex Blog installer Python."""

from __future__ import annotations

import sys


def main() -> int:
    if sys.version_info < (3, 10):  # noqa: UP036 - the probe may be run by older Python
        return 1
    try:
        import hashlib  # noqa: F401
        import json  # noqa: F401
        import pathlib  # noqa: F401
        import subprocess  # noqa: F401
    except ImportError:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
