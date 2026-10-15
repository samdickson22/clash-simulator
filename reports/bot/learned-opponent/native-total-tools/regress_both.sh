#!/bin/bash
set -uo pipefail
cd /mpac/sdicks02/repos/clasher-bot
B=/mpac/sdicks02/jobs/clasher/bot-native-total
export CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
for n in pinned:/mpac/sdicks02/repos/clasher-bot-runtime/r1/native total:/mpac/sdicks02/repos/clasher-bot-native-total/native; do tag=${n%%:*}; dir=${n#*:}
  CLASHER_DELAY_NATIVE_DIR=$dir nice -n 10 .venv/bin/python -B $B/regress.py --dir $B/regress --out $B/regress-$tag.json > $B/regress-$tag.log 2>&1 &
done
wait; date -u +%FT%TZ
