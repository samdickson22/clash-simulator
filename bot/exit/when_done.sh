#!/usr/bin/env bash
# Detached helper (not a queue item): wait for FILE to exist, then append LINE to QUEUE. Gives up after MAX_H hours.
#   bot/exit/when_done.sh FILE QUEUE "LINE" [MAX_H]
set -uo pipefail
f=${1:?FILE}; q=${2:?QUEUE}; line=${3:?LINE}; max=${4:-12}; t=0
until [[ -e "$f" ]]; do sleep 60; t=$((t + 60)); (( t > max * 3600 )) && { echo "gave up on $f"; exit 1; }; done
echo "$line" >> "$q"; echo "$(date -u +%FT%TZ) appended ${line%% *} to $q"
