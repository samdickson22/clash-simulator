#!/bin/bash
# 05: every 10 min, total Null's night footprint; at >= 250 GB write the Mac STOP file (runners shut their emulators
# down) and log it. LEAD budget 10-17: <= 300 GB on 05, pause at 250 GB.
N=/mpac/sdicks02/scratch/nulls/night
LIMIT=$((250*1024*1024*1024))
echo $$ > $N/logs/storage_guard.pid
while true; do
  b=$(du -sb $N 2>/dev/null | cut -f1)
  echo "$(date -u +%FT%TZ) night bytes $b ($((b/1024/1024/1024)) GiB)" >> $N/logs/storage.log
  if [ "${b:-0}" -ge $LIMIT ]; then
    ssh macmini-fleet 'date -u > ~/clasher-live/nulls/night/STOP; echo __RC=$?' >> $N/logs/storage.log 2>&1
    echo "$(date -u +%FT%TZ) STORAGE LIMIT: Mac STOP written" >> $N/logs/storage.log
    exit 0
  fi
  sleep 600
done
