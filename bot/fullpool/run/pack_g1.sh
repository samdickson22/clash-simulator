#!/usr/bin/env bash
# On each G1 host after (or during: sealed shards only) generation: pack its shards into one mmap corpus.
#   ROOT=<root> bot/exit/cpu_job.sh 2 bot/fullpool/run/pack_g1.sh HOSTTAG [EXCLUDE_PACK...]
# -> $J/G1/packed-g1<suffix>-x<HOSTTAG>; a later pack passes the earlier ones as EXCLUDE so packs stay disjoint.
set -euo pipefail
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
TAG=${1:?HOSTTAG}; shift; SUFFIX=${SUFFIX:-a}
[[ ! -e "$J/G1/packed-g1$SUFFIX-x$TAG" ]] || { echo 'fresh pack output required' >&2; exit 1; }
ex=(); for e in "$@"; do ex+=(--exclude "$e"); done
nice -n 15 "$PY" -B -m bot.exit.pack --games "$J/G1/games" --out "$J/G1/packed-g1$SUFFIX-x$TAG" "${ex[@]}"
echo "pack end $(date -u +%FT%TZ) rc 0"; du -sh "$J/G1/packed-g1$SUFFIX-x$TAG"
