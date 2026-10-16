#!/bin/bash
# Dev loop (run on 127x05): sync engine-cards to 08 b1/tree, run the fidelity harness for CARDS on ROOT, print diffs.
# usage: fid.sh TAG ROOT(root|rootstats) CARD...
set -euo pipefail
tag=$1; root=$2; shift 2
W=$(cd "$(dirname "$0")/../../../.." && pwd)/engine-cards
B=/mpac/sdicks02/jobs/clasher/cards/b1
rsync -a --delete --exclude target --exclude __pycache__ --exclude '*.pyc' "$W/" 127x08:$B/tree/
ssh 127x08 "cd $B/fid && rm -f $tag.jsonl && /mpac/sdicks02/repos/clasher-bot/.venv/bin/python apply_stats.py ../tree/py/gamedata.json stats-spec.json ../stats/gamedata.json >/dev/null && POOL=${POOL:-pool.json} bash run_fid.sh ../$root $tag.jsonl 3 --cards $* > $tag.log 2>&1; /mpac/sdicks02/repos/clasher-bot/.venv/bin/python diffs.py $tag.jsonl --n ${N:-8}; grep -i error $tag.log | head -3"
