#!/usr/bin/env bash
# Mirror RoyaleLearn run dirs 04<->08 (off-host copies) and to 03 (eval area). Run from 127x05.
# Copies only; never deletes. Usage: mirror.sh
set -euo pipefail
T=/mpac/sdicks02/jobs/clasher/bot-ext-train
for pair in "127x08 127x04" "127x04 127x08"; do
  set -- $pair; src=$1; dst=$2
  ssh $src "cd $T && for r in rlppo-r*/; do r=\${r%/}; rsync -a --exclude '*.log' \$r $dst:$T/mirror-$src/; rsync -a \$r 127x03:/mpac/sdicks02/jobs/clasher/bot-ext-eval/runs/; done; ls -d rlppo-r*/" 
done
