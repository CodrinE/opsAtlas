#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$project_root/.venv/Scripts/python.exe" ]]; then
  python_bin="$project_root/.venv/Scripts/python.exe"
elif [[ -x "$project_root/.venv/bin/python" ]]; then
  python_bin="$project_root/.venv/bin/python"
else
  python_bin="python3"
fi
exec "$python_bin" "$project_root/cli/compose.py" stop "$@"
