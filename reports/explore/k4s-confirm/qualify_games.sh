#!/usr/bin/env bash
# PREREG-K4S game-level qualification on one host (r3 §4.1): T1 vs K4S no-deadline command hashes, every arm
# charged, zero budget; then the outcome-blind check. Eleven 5-core slots on cores 5-59; waits for all.
# The T1 reference runtime (ef4c073a reports/explore/t1, plan.json input paths rebound to this job) must be staged
# at $job/repo/reports/explore/t1 (see QUALIFICATION.md).
set -euo pipefail
job=${K4S_JOB:?K4S_JOB}
cd "$job/repo"
G=$job/out/games; mkdir -p "$G/logs"
pids=()
L() { local name=$1 cores=$2 runtime=$3; shift 3
  if [ "$runtime" = t1 ]; then
    T1_JOB=$job taskset -c "$cores" bash reports/explore/t1/runtime.sh -P reports/explore/k4s-confirm/qualify_games.py --runtime t1 --cores "$cores" "$@" > "$G/logs/$name.log" 2>&1 &
  else
    K4S_JOB=$job taskset -c "$cores" bash reports/explore/k4s-confirm/runtime.sh reports/explore/k4s-confirm/qualify_games.py --runtime k4s --cores "$cores" "$@" > "$G/logs/$name.log" 2>&1 &
  fi
  pids+=($!)
}
ALL="K4-200 K4S-200 K4-180 K4S-180 K4-160 K4S-160 K4S-140 K4S-120 K4-140 K4-120"
L t1-nd-p0 5,6,7,8,9 t1 --mode nodeadline --population primary --index 0 --arms K4-200 --out "$G/t1-nd"
L t1-nd-g1 10,11,12,13,14 t1 --mode nodeadline --population guard --index 1 --arms K4-200 --out "$G/t1-nd"
L k4s-nd-p0 15,16,17,18,19 k4s --mode nodeadline --population primary --index 0 --arms K4-200 K4S-200 --out "$G/k4s-nd-p0"
L k4s-nd-g1 20,21,22,23,24 k4s --mode nodeadline --population guard --index 1 --arms K4-200 K4S-200 --out "$G/k4s-nd-g1"
L k4s-ch-p2 25,26,27,28,29 k4s --mode charged --population primary --index 2 --arms $ALL --out "$G/k4s-ch-p2"
L k4s-ch-g3 30,31,32,33,34 k4s --mode charged --population guard --index 3 --arms $ALL --out "$G/k4s-ch-g3"
L k4s-zero 35,36,37,38,39 k4s --mode zero --population primary --index 4 --arms K4S-200 K4S-120 --out "$G/k4s-zero"
L t1-inj-p5 40,41,42,43,44 t1 --mode injected --population primary --index 5 --arms K4-200 --out "$G/t1-inj"
L t1-inj-g7 45,46,47,48,49 t1 --mode injected --population guard --index 7 --arms K4-200 --out "$G/t1-inj"
L k4s-inj-p5 50,51,52,53,54 k4s --mode injected --population primary --index 5 --arms K4-200 --out "$G/k4s-inj"
L k4s-inj-g7 55,56,57,58,59 k4s --mode injected --population guard --index 7 --arms K4-200 --out "$G/k4s-inj"
rc=0; for p in "${pids[@]}"; do wait "$p" || rc=1; done
[ $rc -eq 0 ]
K4S_JOB=$job bash reports/explore/k4s-confirm/runtime.sh reports/explore/k4s-confirm/check_games.py --games "$G" --out "$job/out/check-games.json"
