#!/bin/bash
# Full 66-card fidelity, three arms in sequence (127x08, b2/fid): base (pre-B2 engine), mech (B2), stats (B2 + scratch overlay).
cd "$(dirname "$0")"
for arm in base:baseroot mech:root stats:rootstats; do
  ./run_fid.sh ../${arm#*:} final-${arm%%:*}.jsonl 4 --table 160402 > final-${arm%%:*}.log 2>&1
done
echo done > final.done
