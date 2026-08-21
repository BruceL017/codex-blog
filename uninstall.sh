#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

if [[ -n "${CODEX_BLOG_PYTHON:-}" ]]; then
  candidates=("${CODEX_BLOG_PYTHON}")
else
  candidates=(python3.14 python3.13 python3.12 python3.11 python3.10 python3 python)
fi

for candidate in "${candidates[@]}"; do
  if command -v "${candidate}" >/dev/null 2>&1 \
    && "${candidate}" "${repo_dir}/scripts/python_probe.py" >/dev/null 2>&1; then
    exec "${candidate}" "${repo_dir}/scripts/install.py" uninstall "$@"
  fi
done

echo "Codex Blog requires Python 3.10 or newer." >&2
exit 2
