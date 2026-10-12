#!/usr/bin/env bash
# X4S-3 (exploration, NEVER ADOPTABLE): receipts/checkpoint mirror, runs ON 127x05.
# Read-only pull from the X4S-3 job prefix on 127x01 into the plan's 05 mirror prefix,
# every 30 min, at nice 19 / ionice idle on both ends, bwlimit 20 MB/s. Excludes bulk
# corpus copies, runtime trees and caches; includes receipts, logs, games, inputs/*.pt.
# Writes only under $M on 05 (rsync -rt: no --delete, no links). Stops on $M/MIRROR.STOP.
set -euo pipefail
[[ $(hostname) == 127x05 ]]
J=/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012
M=$J/mirror
for p in /mpac /mpac/sdicks02 /mpac/sdicks02/jobs /mpac/sdicks02/jobs/clasher "$J"; do
  [[ -L $p ]] && { echo "symlink component $p" >&2; exit 1; }
  [[ -d $p ]] || mkdir -- "$p"
done
[[ -L $M ]] && exit 1
mkdir -p -- "$M"
while :; do
  [[ -e $M/MIRROR.STOP || -L $M/MIRROR.STOP ]] && exit 0
  rc=0
  nice -n 19 ionice -c3 rsync -rt --bwlimit=20000 \
    --rsync-path='nice -n 19 ionice -c3 rsync' \
    -e 'ssh -o BatchMode=yes -o ConnectTimeout=20' \
    --exclude='/data/g08/batch-*' --exclude='/data/g01/batch-*' --exclude=/cache/ --exclude=/base/ \
    --exclude='/rt-*/repo/' --exclude='/rt-*/native/' --exclude=/corpus/ --exclude=/qual/s1rt/ \
    --exclude='/fits/*/step-*.pt' --exclude=/attempts/ \
    "127x01:$J/" "$M/" >> "$J/mirror.log" 2>&1 || rc=$?
  echo "$(date -u +%FT%TZ) rc=$rc" >> "$J/mirror-runs.log"
  sleep 1800
done
