# source on a fleet host: runtime pins r1-total (panic-free native), single-threaded BLAS, THP madvise off
export NUMPY_MADVISE_HUGEPAGE=0 CLASHER_BOT_RUNTIME_PINS=r1-total \
  CLASHER_DELAY_NATIVE_DIR=/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1 \
  CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1 \
  CLASHER_LIVE_FAST=student:/mpac/sdicks02/repos/clasher-bot-runtime/students/it5s2-step001200.pt@0.5375 \
  PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= \
  PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=${NR_TREE:-/mpac/sdicks02/repos/clasher-bot-noise}
NR_PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
