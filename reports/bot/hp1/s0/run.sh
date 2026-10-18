#!/usr/bin/env bash
# One HEADLINE run for HP1 S0: run.sh NAME WORKERS CANDIDATES OPPONENTS GAMES START BASE
# Launch (env sourced FIRST so cpu_job/cpu_room see BOT_CPU_CAP=70):
#   source $job/env.sh && bash $job/source/bot/detach.sh $job/runs/NAME.log $job/runs/NAME.receipt.json \
#       bash $job/source/bot/exit/cpu_job.sh $((WORKERS+1)) nice -n 15 bash $job/run.sh NAME WORKERS ...
# Exit 0 means headline finished; validity is decided by s0_validate.py on 05 (headline records game errors as rows).
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -euo pipefail
(( $# == 7 )) || { echo "usage: run.sh NAME WORKERS CANDIDATES OPPONENTS GAMES START BASE"; exit 2; }
source /mpac/sdicks02/jobs/clasher/bot-hp1-s0-20261017/env.sh
name=$1 workers=$2 cand=$3 opp=$4 games=$5 start=$6 base=$7
[[ $name =~ ^[a-z0-9-]+$ ]] || { echo "bad name $name"; exit 2; }
# bounded canonical decimals only (no leading zeros: bash would read 020 as octal; <= 16 digits: no overflow)
for v in "$workers" "$games" "$start" "$base"; do [[ $v =~ ^(0|[1-9][0-9]{0,15})$ ]] || { echo "not a canonical decimal integer: $v"; exit 2; }; done
(( workers >= 1 && workers <= 16 )) || { echo "workers must be 1..16"; exit 2; }
(( games >= 1 )) || { echo "games must be >= 1"; exit 2; }
for list in "$cand" "$opp"; do
  [[ -n $list && $list != *,,* && $list != ,* && $list != *, ]] || { echo "empty entry in list: $list"; exit 2; }
  n=$(tr ',' '\n' <<< "$list" | wc -l); u=$(tr ',' '\n' <<< "$list" | sort -u | wc -l)
  (( n == u )) || { echo "duplicate entry in list: $list"; exit 2; }
done
runs=$job/runs; out=$runs/$name; mkdir -p "$runs"
mkdir "$out" 2>/dev/null || { echo "refusing to reuse $out"; exit 3; }       # atomic reservation
trap 'echo $? > "$runs/$name.exit"; date -u > "$runs/$name.ended"' EXIT
export NUMBA_CACHE_DIR=$job/numba-$name; mkdir -p "$NUMBA_CACHE_DIR"
date -u > "$runs/$name.admitted"
"$py" -u -m bot.eval.headline --out "$out" --candidate "$cand" --opponents "$opp" --games "$games" \
  --start "$start" --workers "$workers" --base "$base" --engine rsim16402 --levels max --decks x4s
