#!/usr/bin/env bash
set -euo pipefail
job=${S1_JOB:-/mpac/sdicks02/jobs/clasher/s1-20261010-r1}
repo=$job/repo
runtime=$repo/reports/explore/s1/runtime.sh
cd "$repo"
bash "$runtime" reports/explore/s1/host_audit.py --job "$job" --out "$job/host-audit-qualification.json"
bash "$runtime" -m pytest -q reports/explore/s1/test_anchor.py reports/explore/s1/test_coarse.py reports/explore/s1/test_belief.py reports/explore/s1/test_latency.py reports/explore/s1/test_gc_window.py
date -u +%FT%TZ > "$job/TESTS-PASS"
bash "$runtime" reports/explore/s1/qualify.py --corpus "$job/corpus" --out "$job/qualification.json"
date -u +%FT%TZ > "$job/QUALIFIED"
bash "$runtime" reports/explore/s1/qualify_belief.py --corpus "$job/corpus" --out "$job/belief-qualification.json"
date -u +%FT%TZ > "$job/BELIEF-QUALIFIED"
