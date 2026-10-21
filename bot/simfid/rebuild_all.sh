#!/usr/bin/env bash
# Every REBUILD.md run (bot/simfid/rebuild.py), sequential, 30 workers, MemAvailable guard (pause < 24 GiB, stop < 20).
#   bot/simfid/rebuild_all.sh [RUN_DIR]
# Engines: rt16402b-r3 = read-only deployed RL root (crown pin dropped for Fireball/Poison, as live16402 runtimes);
#          src-root    = this checkout's src/clasher with the repository-root gamedata.json.
# Re-run with a calibrated engine: ENGINES="name:SRC:ROOT:CROWN" bot/simfid/rebuild_all.sh
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
RD=${1:-/mpac/sdicks02/jobs/clasher/simfid-20261020/rebuild}
RT=/mpac/sdicks02/jobs/clasher/simfid-20261020/rt-live16402b-r3
ENGINES=${ENGINES:-"rt16402b-r3:$RT/src:$RT:Fireball,Poison src-root:$REPO/src:$REPO:"}
W=${WORKERS:-30}
memgate() {
  while :; do
    avail=$(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo)
    if [ "$avail" -lt 20 ]; then echo "MemAvailable ${avail} GiB < 20: stop"; exit 3; fi
    if [ "$avail" -ge 24 ]; then return; fi
    echo "MemAvailable ${avail} GiB < 24: pause"; sleep 60
  done
}
run() {  # engine sample config [name]
  local spec=$1 sample=$2 cfg=$3 name=${4:-$3}
  IFS=: read -r ename src root crown <<<"$spec"
  memgate
  "$REPO/bot/simfid/rebuild.sh" "$src" "$root" "$crown" run --sample "$RD/samples/$sample" --config "$cfg" \
    --name "$name" --out "$RD/results/$sample/$ename/$name.jsonl" --workers "$W"
}
first=${ENGINES%% *}
for cfg in main slack40 firstuse l11 lastcand deckorder; do run "$first" native50 "$cfg"; done
run "$first" native50 main main-repeat
for cfg in main slack40 firstuse l11 lastcand deckorder; do run "$first" random1000 "$cfg"; done
for spec in ${ENGINES#"$first"}; do
  for cfg in main slack40; do run "$spec" native50 "$cfg"; done
  run "$spec" random1000 main
done
PYTHONPATH=$REPO /mpac/sdicks02/repos/clasher/.venv/bin/python -m bot.simfid.rebuild_report "$RD" \
  --json "$RD/report.json" --md "$RD/report.md"
