#!/usr/bin/env bash
# Play-quality owner L16 runner: bot.livediag.l16_cadence from TREE (a git-archive tree under $J/repo-*), the same
# environment as bot-fullpool/l16.sh (runtime live16402b-r3, deck-search helpers, PYTHONHASHSEED=0), own job prefix.
#   bot/exit/cpu_job.sh <workers+2> bot/pq/l16.sh TREE --workers W --out $J/<run>/<shard> ...   (via bot/detach.sh)
set -euo pipefail
J=/mpac/sdicks02/jobs/clasher/bot-pq
tree=${1:?TREE}; shift
[[ "$tree" == $J/repo-* && -d "$tree/bot" ]] || { echo "bad tree $tree" >&2; exit 2; }
helpers=/mpac/sdicks02/jobs/clasher/bot-deckopt2-sam; old=/mpac/sdicks02/jobs/clasher/bot-deckopt2
case "$(hostname -s)" in
 127x04|127x08) runtime_root=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3 ;;
 127x01) runtime_root=/mpac/sdicks02/jobs/clasher/bot-fullpool/roots/live16402b-r3 ;;
 *) echo "host not in the bot-pq set" >&2; exit 2 ;;
esac
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT BOT_BELIEF_PRIOR CLASHER_LIVE_FAST
export CLASHER_LEVELS_CACHE=/mpac/sdicks02/jobs/clasher/bot-fullpool/level-configs NUMBA_CACHE_DIR=$J/numba-cache
export PYTHONHASHSEED=0 NUMPY_MADVISE_HUGEPAGE=0 PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1
export CLASHER_BOT_RUNTIME="$runtime_root" CLASHER_DELAY_NATIVE_DIR="$runtime_root/native" CLASHER_BOT_RUNTIME_PINS=live16402b-r3
export CLASHER_LOPP_MODELS="$old/fullpool/models/lopp-fp"
export BOT_FULLPOOL_POLICIES="v1=$old/fullpool/models/ext/main02-fp.pt,R3a=$old/fullpool/models/ext/R3a-fp.pt"
export CLASHER_LEVELS_PLACEMENT_PROOF="$old/placement-proof.json"
export PYTHONPATH="$helpers:$old:$tree"
cd "$tree"
# as bot-fullpool/l16.sh: a re-queued block never reuses an --out dir (l16_cadence requires a fresh one); it runs the whole
# case set again into <out>-r<N> (rows are deterministic: duplicates must match and count once in the readouts)
args=("$@")
for i in "${!args[@]}"; do
    if [[ "${args[$i]}" == --out && -e "${args[$((i+1))]}" ]]; then
        o=${args[$((i+1))]}; n=2; while [[ -e "$o-r$n" ]]; do n=$((n+1)); done; args[$((i+1))]="$o-r$n"
    fi
done
set -- "${args[@]}"
echo "pq-l16 start $(date -u +%FT%TZ) host $(hostname -s) tree $(cat STAGED-REV 2>/dev/null) args $*"
rc=0; nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -m bot.livediag.l16_cadence "$@" || rc=$?
echo "pq-l16 end $(date -u +%FT%TZ) rc $rc"; exit $rc
