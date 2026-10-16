#!/bin/bash
# C56 parity gate for Batch B1 (copy of batchA/tools/gate.sh): BOT LEAD native-total-tools (parity_fixtures.py, parity_roots.py, compare.py),
# unmodified, run as the NATIVE-TOTAL.md section 4 runs did, on two arms:
#   pinned  = runtime r1 Python (src, engine-rs glue) + native-total-r1 (681b5f2c)
#   total   = b1 rt/ (r1 mirror with src -> tree/py/src, engine-rs -> tree) + b1 out/ native
# Usage (127x04):  cpu_job.sh 8 tools/gate.sh  -> gate/compare.json.   <= 8 processes at a time (fixtures, then roots), nice.
set -uo pipefail
A=$(cd "$(dirname "$0")/.." && pwd)
G=$A/gate; mkdir -p $G
R1=/mpac/sdicks02/repos/clasher-bot-runtime/r1
PIN=/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1
ES=$R1/reports/strategy_council_20260928/engine-speed
T=$A/gate-tools
cd /mpac/sdicks02/repos/clasher-bot
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
N="nice -n 15"
echo "fixtures start $(date -u +%FT%TZ)"
CLASHER_ROOT=$R1 PYTHONPATH=$PIN:$R1/engine-rs:$R1/src:$ES:/mpac/sdicks02/repos/clasher-bot \
  $N .venv/bin/python -B $T/parity_fixtures.py --out $G/fixtures-pinned.jsonl --workers 3 > $G/fixtures-pinned.log 2>&1 &
CLASHER_ROOT=$A/rt PYTHONPATH=$A/out:$A/tree:$A/tree/py/src:$ES:/mpac/sdicks02/repos/clasher-bot \
  $N .venv/bin/python -B $T/parity_fixtures.py --out $G/fixtures-total.jsonl --workers 3 > $G/fixtures-total.log 2>&1 &
wait
echo "fixtures end $(date -u +%FT%TZ)"
for i in 0 1 2 3; do
  CLASHER_BOT_RUNTIME=$R1 CLASHER_DELAY_NATIVE_DIR=$PIN $N .venv/bin/python -B $T/parity_roots.py --roots $A/roots \
    --sample 300 --shard $i/4 --out $G/roots-pinned-$i.jsonl > $G/roots-pinned-$i.log 2>&1 &
  CLASHER_BOT_RUNTIME=$A/rt CLASHER_DELAY_NATIVE_DIR=$A/out $N .venv/bin/python -B $T/parity_roots.py --roots $A/roots \
    --sample 300 --shard $i/4 --out $G/roots-total-$i.jsonl > $G/roots-total-$i.log 2>&1 &
done
wait
echo "all end $(date -u +%FT%TZ)"
.venv/bin/python $T/compare.py $G > $G/compare.json; cat $G/compare.json
