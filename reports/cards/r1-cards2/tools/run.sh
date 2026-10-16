#!/usr/bin/env bash
# Scratch-only mechanical orchestration of the existing runtime and live16402 gates.
# Launch under setsid cpu_job.sh 8 nice -n 15. No frozen runtime writes.
set -euo pipefail
J=${CARD_GATE_JOB:-/mpac/sdicks02/jobs/clasher/cards/r1-cards2}
R=${CARD_RUNTIME_DIR:-/mpac/sdicks02/jobs/clasher/cards/runtime}
RT=/mpac/sdicks02/repos/clasher-bot-runtime
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
cd "$J/repo"
mkdir -p "$J/gate"
arm() {
  case "$1" in
    cur) env CLASHER_BOT_RUNTIME="$RT/r1" CLASHER_DELAY_NATIVE_DIR="$RT/native-total-r1" CLASHER_BOT_RUNTIME_PINS=r1-total "${@:2}" ;;
    cards) env CLASHER_BOT_RUNTIME="$R/r1-cards2-dev" CLASHER_DELAY_NATIVE_DIR="$R/r1-cards2-dev/native" CLASHER_BOT_RUNTIME_PINS=r1-cards2 "${@:2}" ;;
    live) env CLASHER_BOT_RUNTIME="$R/live16402b-dev" CLASHER_DELAY_NATIVE_DIR="$R/live16402b-dev/native" CLASHER_BOT_RUNTIME_PINS=live16402b "${@:2}" ;;
  esac
}
wait_all() {
  local rc=0 p
  for p in "$@"; do if wait "$p"; then echo "pid $p rc 0"; else echo "pid $p failed"; rc=1; fi; done
  return "$rc"
}
if [[ "${1:?build|smoke|gates|k4l|eval}" != build && "$1" != smoke && -f "$J/LONG-GATES-ON-HOLD" ]]; then
  cat "$J/LONG-GATES-ON-HOLD" >&2
  exit 2
fi
echo "${1:?build|smoke|gates|k4l|eval} start $(date -u +%FT%TZ) host $(hostname) pid $$"
case "$1" in
 build)
  source_tree=${CARD_SOURCE_TREE:-$J/source-b7c6976e4}
  native_sha=${CARD_NATIVE_SHA256:-5f07238c3c3c1eafa7ada7b87aae00f9c40f69f78680aca206a4733c7b729252}
  bash "$J/build-j8.sh" "$source_tree/engine-cards" "$J/native-rebuild"
  echo "$native_sha  $J/native-rebuild/clasher_core.abi3.so" | sha256sum -c -
  "$PY" -B bot/cards/build_runtime.py --tree "$source_tree" --target "$R/r1-cards2-dev" --native "$J/native-rebuild/clasher_core.abi3.so" > "$J/assemble-cards.log"
  "$PY" -B bot/cards/build_live16402.py --base "$R/r1-cards2-dev" --target "$R/live16402b-dev" --rs16 /mpac/sdicks02/jobs/clasher/cards/live16402/rs/cards-160402017-20261006.json --rs15 /mpac/sdicks02/jobs/clasher/cards/live16402/rs/cards-15.535.json --calibration /mpac/sdicks02/jobs/clasher/cards/live16402/rs/calibration-gamedata.json > "$J/assemble-live.log"
  echo 'a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb  '"$R/live16402b-dev/gamedata.json" | sha256sum -c -
  touch "$J/build.done"
  ;;
 smoke)
  for a in cards live; do
    arm "$a" "$PY" -B reports/cards/runtime/tools/smoke_scope.py > "$J/smoke-$a.json" 2> "$J/smoke-$a.log"
    cat "$J/smoke-$a.json"
  done
  ;;
 k4l)
  out=${CARD_HEADLINE_OUT:-$J/gate-final}
  mkdir -p "$out"
  pids=()
  for a in cur cards; do
    label=c56; [ "$a" = cards ] && label=full
    arm "$a" "$PY" -B -m bot.eval.headline --out "$out/hl-k4l-$label" --candidate K4L-R-gs-rw-fc-p2 --opponents R3a,v1 --games 6 --workers 1 > "$out/hl-k4l-$label.log" 2>&1 & pids+=("$!")
  done
  wait_all "${pids[@]}"
  touch "$J/headline-final.done"
  ;;
 gates)
  test -f "$J/build.done"
  pids=()
  for a in cur cards; do
    label=live; [ "$a" = cards ] && label=full
    for shard in 0 1; do
      arm "$a" "$PY" -B reports/cards/runtime/tools/parity_scope_roots.py --roots "$R/roots-nt" --sample 300 --shard "$shard/2" --out "$J/gate/roots-$label-$shard.jsonl" > "$J/gate/roots-$label-$shard.log" 2>&1 & pids+=("$!")
    done
  done
  wait_all "${pids[@]}"
  touch "$J/roots.done"
  echo "roots end $(date -u +%FT%TZ)"
  pids=()
  for a in cur cards; do
    label=c56; [ "$a" = cards ] && label=full
    arm "$a" "$PY" -B -m bot.eval.headline --out "$J/gate/hl-k4l-$label" --candidate K4L-R-gs-rw-fc-p2 --opponents R3a,v1 --games 6 --workers 1 > "$J/gate/hl-k4l-$label.log" 2>&1 & pids+=("$!")
  done
  wait_all "${pids[@]}"
  touch "$J/headline.done"
  echo "headline end $(date -u +%FT%TZ)"
  M=reports/cards/runtime/tools/noncore_matches.py
  for spec in D1:random D2:random D3:random D4:random M1:random D1:R3a; do
    arm cards "$PY" -B "$M" --player LIVE-K4L-R-gs-rw-fc-w200-t4-p4 --opponent "${spec#*:}" --deck "${spec%%:*}" --games 1 --seed 20261016300 --out "$J/gate/noncore-cards.jsonl" >> "$J/gate/noncore-cards.log" 2>&1
    echo "cards noncore $spec rc 0 $(date -u +%FT%TZ)"
  done
  touch "$J/cards-noncore.done"
  pids=()
  for cfg in root runtime; do for scrub in plain scrub; do
    flags=(); [ "$cfg" = runtime ] && flags+=(--runtime-config); [ "$scrub" = scrub ] && flags+=(--scrub)
    arm live "$PY" -B reports/cards/live16402/tools/totality_live.py "${flags[@]}" --roots "$R/roots-nt" --out "$J/gate/totality-$cfg-$scrub.json" > "$J/gate/totality-$cfg-$scrub.log" 2>&1 & pids+=("$!")
  done; done
  wait_all "${pids[@]}"
  touch "$J/totality.done"
  echo "totality end $(date -u +%FT%TZ)"
  fast() {
    for d in "$@"; do for o in random R3a; do
      arm live "$PY" -B "$M" --player LIVE-fast-it5s2 --opponent "$o" --deck "$d" --games 3 --out "$J/gate/fast-live.jsonl"
    done; done
  }
  fast D1 D2 D3 > "$J/gate/fast-a.log" 2>&1 & f1=$!
  fast D4 M1 X1 > "$J/gate/fast-b.log" 2>&1 & f2=$!
  for spec in D1:random D2:random D3:random D4:random M1:random X1:random D1:R3a D2:R3a D3:R3a D4:R3a M1:R3a; do
    arm live "$PY" -B "$M" --player LIVE-K4L-R-gs-rw-fc-w200-t4-p4 --opponent "${spec#*:}" --deck "${spec%%:*}" --games 3 --out "$J/gate/noncore-live.jsonl" >> "$J/gate/noncore-live.log" 2>&1
    echo "live noncore $spec rc 0 $(date -u +%FT%TZ)"
  done
  wait_all "$f1" "$f2"
  touch "$J/gates.done"
  ;;
 eval)
  test -d "$R/live16402b-dev"
  start=${CARD_EVAL_START:-0}; games=${CARD_EVAL_GAMES:-200}
  out=${CARD_EVAL_OUT:-$J/gate/hl-live16402b}
  arm live "$PY" -B -m bot.eval.headline --out "$out" --candidate K4L-R-gs-rw-fc --opponents R3a,v1 --start "$start" --games "$games" --workers "${CARD_EVAL_WORKERS:-6}" > "$out.log" 2>&1
  touch "$J/eval-$start-$games.done"
  ;;
esac
echo "$1 end $(date -u +%FT%TZ)"
