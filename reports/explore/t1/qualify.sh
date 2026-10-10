#!/usr/bin/env bash
set -euo pipefail
job=${T1_JOB:-/mpac/sdicks02/jobs/clasher/t1-20261010-r1}
repo=$job/repo
runtime=$repo/reports/explore/t1/runtime.sh
cd "$repo"
bash "$runtime" reports/explore/t1/host_audit.py --job "$job" --out "$job/host-audit-qualification.json"
bash "$runtime" reports/explore/t1/qualification_binding.py --job "$job" --record
bash "$runtime" -m pytest -q reports/explore/t1/test_anchor.py reports/explore/t1/test_coarse.py reports/explore/t1/test_belief.py reports/explore/t1/test_latency.py reports/explore/t1/test_gc_window.py reports/explore/t1/test_schedule.py reports/explore/t1/test_replace.py reports/explore/t1/test_barrier.py reports/explore/t1/test_corpus.py reports/explore/t1/test_reduce.py reports/explore/t1/test_idle_services.py reports/explore/t1/test_op1.py reports/explore/t1/test_op2.py reports/explore/t1/test_op3.py reports/explore/t1/test_op4.py
date -u +%FT%TZ > "$job/TESTS-PASS"
bash "$runtime" reports/explore/t1/select_guard_decks.py --out "$job/guard-support-qualification.json"
bash "$runtime" reports/explore/t1/qualify.py --corpus "$job/corpus" --out "$job/qualification.json"
date -u +%FT%TZ > "$job/QUALIFIED"
bash "$runtime" reports/explore/t1/qualify_belief.py --corpus "$job/corpus" --out "$job/belief-qualification.json"
date -u +%FT%TZ > "$job/BELIEF-QUALIFIED"
bash "$runtime" reports/explore/t1/qualification_binding.py --job "$job" --verify
