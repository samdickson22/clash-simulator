#!/usr/bin/env bash
# move a pending ev-NAME line from 04|08 (arg 2)'s cpuq6 to 01's cpuq6 (copy ckpt + calibration json 04 -> 05 -> 01)
set -euo pipefail
n=$1; S=${2:-04}; J4=/mpac/sdicks02/jobs/clasher/bot-exit-r1$([ $S = 08 ] || echo -$S); J1=/mpac/sdicks02/jobs/clasher/bot-exit-r1-01
line=$(ssh 127x$S "grep '^ev-$n ' $J4/cpuq6/QUEUE"); [[ -n "$line" ]]
ssh 127x$S "! grep -qx 'ev-$n' $J4/cpuq6/QUEUE.done && ! grep -q 'START ev-$n:' $J4/cpuq6/runner.log" || { echo "already started/done on 04"; exit 1; }
ssh 127x$S "echo ev-$n >> $J4/cpuq6/QUEUE.done; echo '# $(date -u +%FT%TZ) ev-$n moved to 01 cpuq6 (free slot on 01)' >> $J4/cpuq6/QUEUE"
ckpt=$(grep -oE "$J4/train-$n/step-[0-9]+\.pt" <<<"$line" | head -1); tmp=/tmp/sdicks02-exit8/mv-$n; mkdir -p $tmp
scp -q 127x$S:$ckpt 127x$S:$ckpt.calibration.json $tmp/
ssh 127x01 "mkdir -p $J1/train-$n"; scp -q $tmp/* 127x01:$J1/train-$n/
ssh 127x01 "cd $J1/train-$n && sha256sum $(basename $ckpt)"; sha256sum $tmp/$(basename $ckpt)
echo "${line//$J4/$J1}" | ssh 127x01 "cat >> $J1/cpuq6/QUEUE; tail -1 $J1/cpuq6/QUEUE | cut -c1-200"
rm -rf $tmp
