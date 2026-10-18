#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
run_dir="results/local_$(date +%Y%m%d_%H%M%S)_$$"
./run_local.sh --backend demo --out "$run_dir" || exit 1
open "$run_dir/report.html"
