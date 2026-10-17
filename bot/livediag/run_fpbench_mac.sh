#!/bin/zsh
# ~/clasher-live/livediag-bench/run-fpbench-mac.sh <bench|prestop> <args...>  (bot lead live-diag; bench-only, writes only its --out)
# Env = loop/run-fullpool.sh (restart3b-stage, sha256 e6e7c1246d663574...) lines 5-15 verbatim except LL_MANIFEST=MANIFEST-fullpool-wint.json (the wint tree), plus LL_HANDSYNC=1 (the deployed SyncSession).
# Code tree under test = $B/loop/code/${LL_CODE:-fullpool-r1}. Run only in the LIVE LEAD Mac slot (never during a session / Null's block).
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
export LL_HANDSYNC=1
unset LL_PINS FP_TEST_STALL FP_TEST_NOWATCH FP_TEST_NOCHILDALARM FP_TEST_MARK FP_TEST_SESSFILE FP_TEST_SUP_RAISE FP_TEST_SIG_AT_EOF FP_TEST_FAST_RAISE FP_TEST_SEARCH_RAISE FP_TEST_BELIEF_TIMEOUT FP_TEST_POOL_ERR FP_TEST_MUTATE   # test hooks never reach a real run
HERE=${0:A:h}; mode=$1; shift
case $mode in bench) mod=fp_mac_bench.py;; prestop) mod=fp_prestop_check.py;; *) echo "usage: $0 bench|prestop ..."; exit 2;; esac
cd $B/tmp && exec $B/venv/bin/python -B $HERE/$mod --code $CODE "$@"   # the script supervises itself (--deadline-s)
