#!/usr/bin/env bash
# Push the x4s2 harness from the 05 checkout into each host's runtime overlay (light rsync).
set -euo pipefail
src=/mpac/sdicks02/repos/clasher/reports/explore/x4s2/
for h in "$@"; do
  nice -n 19 rsync -a --delete --exclude __pycache__ --exclude receipts/ --rsync-path='nice -n 19 rsync' "$src" "$h:/mpac/sdicks02/jobs/clasher/x4s2-20261011/repo/reports/explore/x4s2/"
done
