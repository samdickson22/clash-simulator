#!/bin/zsh
# live-diag -wint/-K2 sibling of run-fullpool.sh (restart3b-stage e6e7c124): ONLY the code-dir default (fullpool-r1-wint) and LL_MANIFEST (MANIFEST-fullpool-wint.json) differ.
# ~/clasher-live/loop/run-fullpool.sh <out name> <drive.py args...> : the live driver on the FULL CARD POOL (runtime live16402b-r3-mac,
# translator true ids + learned owner model v1.1 (owner-v11/owner.json 7fe134fb -> owner-model.json 487ae8dd; v1 fallback: yolo/owner.json 184201a8), code tree code/fullpool-r1, its own manifest). Writes only under ~/clasher-live.
# Rollback = start the next session with ~/clasher-live/loop/run.sh (the C56 set: tree 15117b86b-w1, MANIFEST.json), unchanged.
B=$HOME/clasher-live; CODE=$B/loop/code/${LL_CODE:-fullpool-r1-wint}; RT=$B/fullpool/live16402b-r3
export PYTHONPATH=$CODE:$CODE/src:$CODE/live/perception CLASHER_BOT_RUNTIME=$RT CLASHER_DELAY_NATIVE_DIR=$RT/native \
  CLASHER_BOT_RUNTIME_PINS=live16402b-r3-mac CLASHER_LIVE_TRUE_IDS=$B/yolo/true-ids-v3b.json \
  CLASHER_LIVE_OWNER_MODEL=$B/yolo/owner-v11/owner.json \
  CLASHER_LIVE_FAST=student:$B/fullpool/models/fits/f1a2/step-001200.pt CLASHER_LOPP_MODELS=$B/fullpool/models/lopp-fp \
  BOT_FULLPOOL_POLICIES=v1=$B/fullpool/models/ext/main02-fp.pt,R3a=$B/fullpool/models/ext/R3a-fp.pt \
  BOT_BELIEF_PRIOR=fullpool:11433651:freq=b53b02a1fde4 \
  LL_MANIFEST=$B/loop/MANIFEST-fullpool-wint.json \
  PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 NUMPY_MADVISE_HUGEPAGE=0 \
  PYTHONHASHSEED=0   # R.meta card token ids depend on the hash seed; training/evals use 0
unset LL_PINS          # the mac-r1-total pin registration is C56-only; live16402b-r3-mac is a PIN_SETS entry
name=$1; shift
cd $B/tmp && exec $B/venv/bin/python -B $CODE/live/loop/drive.py --out $B/loop/runs/$name --export $B/clasher-live-macbench/data/perc-export "$@"
