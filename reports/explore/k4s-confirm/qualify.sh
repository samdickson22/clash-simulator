#!/usr/bin/env bash
# PREREG-K4S per-host qualification (r3 §4.1). Delta vs T1 qualify.sh: K4S tests, K4S 125-state and game-level
# qualification, SD1 manifest check, guard-deck regeneration equality; the host audit is recorded, not asserted
# (admission is decided by the supervisor at launch). The independent verifier's tests need a git checkout and run
# there (receipts/verifier-tests.txt); two host-uptime-dependent T1 OP-7 test cases run via test_op7_boottime.py.
set -euo pipefail
job=${K4S_JOB:-/mpac/sdicks02/jobs/clasher/k4s-confirm-r1}
repo=$job/repo
K=reports/explore/k4s-confirm
runtime=$repo/$K/runtime.sh
cd "$repo"
bash "$runtime" $K/host_audit.py --job "$job" --out "$job/host-audit-qualification.json" || echo "host audit: not admitted now (recorded)"
bash "$runtime" $K/qualification_binding.py --job "$job" --record
bash "$runtime" $K/sd1_manifest.py check > "$job/sd1-manifest-check.txt"
bash "$runtime" -m pytest -q -p no:cacheprovider $K/test_anchor.py $K/test_coarse.py $K/test_belief.py $K/test_latency.py $K/test_gc_window.py \
  $K/test_schedule.py $K/test_replace.py $K/test_barrier.py $K/test_reduce.py $K/test_idle_services.py \
  $K/test_op1.py $K/test_op2.py $K/test_op3.py $K/test_op4.py $K/test_op5.py $K/test_op5_08.py $K/test_op6.py $K/test_op7.py \
  $K/test_sdefault.py $K/test_charge.py $K/test_op7_boottime.py $K/test_health.py $K/test_qual_tasks.py \
  --deselect "$K/test_op7.py::test_fresh_reaps_cannot_renew_stale_orphan_debt[apt_budget-apt_budget]" \
  --deselect "$K/test_op7.py::test_fresh_reaps_cannot_renew_stale_orphan_debt[ssh_budget-ssh_budget]" | tee "$job/tests.log"
date -u +%FT%TZ > "$job/TESTS-PASS"
bash "$runtime" $K/select_guard_decks.py --out "$job/guard-support-qualification.json"
test "$(sha256sum $K/guard-decks.json | cut -d' ' -f1)" = 6d51628bb1262f53258e88ef6247cfb41f2762f9f13323387fcd36ad126c48ef
bash "$runtime" -c "import json,sys;a=json.load(open('$job/guard-support-qualification.json'));b=json.load(open('$K/guard-decks.json'));a.pop('utc');b.pop('utc');sys.exit(0 if a==b else 1)"
bash "$runtime" $K/qualify.py --corpus "$job/corpus" --out "$job/qualification.json"
bash "$runtime" $K/qualify_k4s.py --corpus "$job/corpus" --out "$job/k4s-qualification.json"
date -u +%FT%TZ > "$job/QUALIFIED"
bash "$runtime" $K/qualify_belief.py --corpus "$job/corpus" --out "$job/belief-qualification.json"
date -u +%FT%TZ > "$job/BELIEF-QUALIFIED"
bash "$runtime" $K/qualification_binding.py --job "$job" --verify
