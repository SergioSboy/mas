#!/usr/bin/env bash
set -euo pipefail
project_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$project_dir"
project_python="$project_dir/.venv/bin/python"
if [[ ! -x "$project_python" ]]; then
  echo 'Сначала создайте .venv и установите зависимости по разделу README «Без Docker».' >&2
  exit 1
fi
exec "$project_python" "$project_dir/main.py" "$@"
