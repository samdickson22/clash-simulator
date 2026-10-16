# Shared environment for the full-pool generation/retrain scripts (source it; see reports/bot/fullpool/PLAN.md).
# Override any of these before sourcing or on the command line. ROOT must be the released live16402 root.
: "${ROOT:?ROOT = runtime root (e.g. the released live16402-on-r1-cards2 root)}"
: "${PINS:=live16402b}"                                     # CLASHER_BOT_RUNTIME_PINS
: "${J:=/mpac/sdicks02/jobs/clasher/bot-fullpool}"           # job dir (same path on 03/04/08)
: "${EXT:=$J/ext}"                                          # extended checkpoints (bot/fullpool/extend.py receipts)
: "${LOPP:=$J/lopp-fp}"                                     # K4L nets (originals + *fp.npz)
: "${PY:=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python}"
: "${OWN:=full}"                                            # full (R.bots widened) | c56 (search seats on C56 decks)
: "${FREQ12:=b53b02a1fde4}"                                 # frozen LIVE freq table the training decks use
: "${TRAIN_BASE:=2613058991490864}"                         # FP-TRAIN1
: "${TRAIN_SEED:=11433651}"
STUDENT="student:$EXT/rl5-v10-fp.pt@0.5375"
DECKS="fullpool:$TRAIN_SEED:freq=$FREQ12$([ "$OWN" = c56 ] && echo ,own=c56)"
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 \
  CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 NUMPY_MADVISE_HUGEPAGE=0 \
  CLASHER_BOT_RUNTIME=$ROOT CLASHER_DELAY_NATIVE_DIR=$ROOT/native CLASHER_BOT_RUNTIME_PINS=$PINS \
  CLASHER_LOPP_MODELS=$LOPP BOT_FULLPOOL_POLICIES="v1=$EXT/main02-fp.pt,R3a=$EXT/R3a-fp.pt"
