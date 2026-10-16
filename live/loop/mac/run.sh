#!/bin/zsh
# ~/clasher-live/loop/run.sh <out name> <drive.py args...> : the live driver with the Mac runtime env (writes only under ~/clasher-live)
B=$HOME/clasher-live; BUNDLE=$B/clasher-live-macbench; CODE=$B/loop/code/${LL_CODE:-15117b86b-w1}
export PYTHONPATH=$CODE:$CODE/src:$CODE/live/perception CLASHER_BOT_RUNTIME=$BUNDLE/runtime \
  CLASHER_DELAY_NATIVE_DIR=$BUNDLE/runtime/native-mac CLASHER_BOT_RUNTIME_PINS=mac-r1-total LL_PINS=$B/state/pins-mac.json \
  CLASHER_LIVE_FAST="student:$B/students-live/rl5-v10/policy-00010.pt@0.5375" CLASHER_LOPP_MODELS=$BUNDLE/data/lopp-models \
  PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 NUMPY_MADVISE_HUGEPAGE=0
name=$1; shift
cd $B/tmp && exec $B/venv/bin/python -B $CODE/live/loop/drive.py --out $B/loop/runs/$name --export $BUNDLE/data/perc-export "$@"
