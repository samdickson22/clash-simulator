#!/usr/bin/env bash
# Wait for a pack job to exit, check it sealed, then copy the packed dir to other hosts' job dirs.
#   bot/exit/pack_sync.sh PACK_PID PACKED_DIR HOST:JOB_DIR [HOST:JOB_DIR ...]
# Each copy lands in JOB_DIR/<basename PACKED_DIR>/ and gets a .synced marker (also written locally) only after
# rsync succeeds, so GPU queue lines can wait on "<packed>/.synced".
set -uo pipefail
pid=${1:?PACK_PID}; src=${2:?PACKED_DIR}; shift 2
while kill -0 "$pid" 2>/dev/null; do sleep 30; done
[[ -s "$src/manifest.json" && -d "$src/train" ]] || { echo "$(date -u +%FT%TZ) $src not sealed; abort"; exit 1; }
name=$(basename "$src")
for dst in "$@"; do
    host=${dst%%:*}; dir=${dst#*:}
    if nice -n 19 rsync -a "$src/" "$host:$dir/$name/"; then
        ssh "$host" "touch '$dir/$name/.synced'" && echo "$(date -u +%FT%TZ) synced $name -> $dst"
    else
        echo "$(date -u +%FT%TZ) rsync $name -> $dst FAILED"
    fi
done
touch "$src/.synced"
