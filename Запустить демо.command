#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
run_dir="results/demo_$(date +%Y%m%d_%H%M%S)_$$"
project_python=".venv/bin/python"
[[ -x "$project_python" ]] || project_python="python3"
"$project_python" main.py --backend demo --out "$run_dir" || exit 1
open "$run_dir/report.html"
