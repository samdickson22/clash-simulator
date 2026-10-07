#!/bin/bash
set -u
cd /Users/sam/Desktop/code/clasher
LOG=reports/strategy_council_20260928/pilot/logs/transfer-to-f35-parallel.log
SSH="ssh -T -o BatchMode=yes -o Compression=no -c aes128-gcm@openssh.com"
{ find datasets/external -mindepth 2 -maxdepth 3 -type d; find reports/strategy_council_20260928/live-loop -mindepth 2 -maxdepth 4 -type d; } | awk -F/ '{print NF"\t"$0}' | sort -rn | cut -f2 \
 | xargs -P 8 -I{} /opt/homebrew/bin/rsync -aR --partial --exclude=__pycache__/ --exclude=.DS_Store -e "$SSH" --rsync-path=/usr/bin/rsync "./{}" sdicks02@f35:/data2/sdicks02/repos/clasher/ >> $LOG 2>&1
echo "$(date -u +%FT%TZ) tail helpers exit $?" >> $LOG
