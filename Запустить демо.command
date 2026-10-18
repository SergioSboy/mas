#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
run_dir="results/demo_$(date +%Y%m%d_%H%M%S)_$$"
docker compose run --build --rm app --backend demo --out "/app/$run_dir" || exit 1
open "$run_dir/report.html"
