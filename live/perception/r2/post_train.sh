#!/bin/bash
# Perception round 2: export + full-val evals + full-val dump of one checkpoint on 127x01 (GPU). Validation only.
#   post_train.sh CKPT NAME     -> $J/export-NAME, $J/eval/{NAME-dense-s2,NAME-dense-s2-nocount,ev-NAME-s2}, $J/dump-NAME
set -euo pipefail
CKPT=$1; NAME=$2
J=/mpac/sdicks02/jobs/clasher/live-perc-r2-20261015
P=/mpac/sdicks02/repos/clasher-live-r2/live/perception
PY=/mpac/sdicks02/envs/clasher-gpu/bin/python
export OMP_NUM_THREADS=4 NUMPY_MADVISE_HUGEPAGE=0
cd $P
nice -n 10 $PY export_live.py --checkpoint $CKPT --output $J/export-$NAME --device cuda --cpu-threads 4
nice -n 10 $PY eval_val.py --checkpoint $CKPT --out $J/eval/$NAME-dense-s2 --device cuda --threads 4 --stride 2 --truth dense &
nice -n 10 $PY eval_val.py --checkpoint $CKPT --out $J/eval/$NAME-dense-s2-nocount --device cuda --threads 4 --stride 2 --truth dense --no-counts &
nice -n 10 $PY eval_events.py --checkpoint $CKPT --out $J/eval/ev-$NAME-s2 --stride 2 --device cuda &
for k in 0 1 2; do
  nice -n 10 $PY dump_records.py $J/export-$NAME $J/dump-$NAME --shard $k --nshards 3 --threads 1 --device cuda \
     --labels $J/labels-r2 > $J/logs/dump-$NAME-$k.log 2>&1 &
done
wait
echo DONE $NAME
