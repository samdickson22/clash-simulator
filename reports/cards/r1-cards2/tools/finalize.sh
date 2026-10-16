#!/usr/bin/env bash
# Final candidate refresh after the carried 5f07238c gates finish. Scratch paths only.
set -euo pipefail
SELF=$(realpath "$0")
J=/mpac/sdicks02/jobs/clasher/cards/r1-cards2/final
R=/mpac/sdicks02/jobs/clasher/cards/runtime
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
export CARD_GATE_JOB=$J CARD_HEADLINE_OUT=$J/gate
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT CLASHER_DELAY_NATIVE_DIR
if [[ "${1:-}" = all || "${1:-}" = assemble ]]; then
  test -f "$J/../gates.done"
  test -f "$J/../eval-100-100.done"
  ssh 127x04 test -f /mpac/sdicks02/jobs/clasher/cards/r1-cards2/eval-0-100.done
fi
cd "$J/repo"
mkdir -p "$J/gate"
echo "$1 start $(date -u +%FT%TZ) pid $$"
case "${1:?assemble|smoke|k4l|k4l-cur|k4l-full|totality|all}" in
 assemble)
  native=$J/native/clasher_core.abi3.so
  echo "de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1  $native" | sha256sum -c -
  "$PY" -B bot/cards/build_runtime.py --tree "$J/source-878d5f459" --target "$R/r1-cards2-dev" --native "$native" > "$J/assemble-cards.log"
  "$PY" -B bot/cards/build_live16402.py --base "$R/r1-cards2-dev" --target "$R/live16402b-dev" --rs16 /mpac/sdicks02/jobs/clasher/cards/live16402/rs/cards-160402017-20261006.json --rs15 /mpac/sdicks02/jobs/clasher/cards/live16402/rs/cards-15.535.json --calibration /mpac/sdicks02/jobs/clasher/cards/live16402/rs/calibration-gamedata.json > "$J/assemble-live.log"
  echo "a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb  $R/live16402b-dev/gamedata.json" | sha256sum -c -
  ;;
 smoke|k4l)
  bash "$J/repo/reports/cards/r1-cards2/tools/run.sh" "$1"
  ;;
 k4l-cur|k4l-full)
  label=c56
  if [ "$1" = k4l-cur ]; then
    export CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1
    export CLASHER_DELAY_NATIVE_DIR=/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1 CLASHER_BOT_RUNTIME_PINS=r1-total
  else
    label=full
    export CLASHER_BOT_RUNTIME=$R/r1-cards2-dev CLASHER_DELAY_NATIVE_DIR=$R/r1-cards2-dev/native CLASHER_BOT_RUNTIME_PINS=r1-cards2
  fi
  "$PY" -B -m bot.eval.headline --out "$J/gate/hl-k4l-$label" --candidate K4L-R-gs-rw-fc-p2 --opponents R3a,v1 --games 6 --workers 2 > "$J/gate/hl-k4l-$label.log" 2>&1
  ;;
 totality)
  pids=()
  for cfg in root runtime; do for scrub in plain scrub; do
    flags=(); [ "$cfg" = runtime ] && flags+=(--runtime-config); [ "$scrub" = scrub ] && flags+=(--scrub)
    env CLASHER_BOT_RUNTIME="$R/live16402b-dev" CLASHER_BOT_RUNTIME_PINS=live16402b CLASHER_DELAY_NATIVE_DIR="$R/live16402b-dev/native" \
      "$PY" -B reports/cards/live16402/tools/totality_live.py "${flags[@]}" --roots "$R/roots-nt" --out "$J/gate/totality-$cfg-$scrub.json" > "$J/gate/totality-$cfg-$scrub.log" 2>&1 & pids+=("$!")
  done; done
  rc=0
  for p in "${pids[@]}"; do if wait "$p"; then echo "pid $p rc 0"; else echo "pid $p failed"; rc=1; fi; done
  [ "$rc" = 0 ]
  ;;
 all)
  for part in assemble smoke k4l-full totality; do bash "$SELF" "$part"; done
  ;;
esac
touch "$J/$1.done"
echo "$1 end $(date -u +%FT%TZ)"
