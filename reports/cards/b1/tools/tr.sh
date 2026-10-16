#!/bin/bash
# usage (05): tr.sh ROOT CARD KIND SCEN FROM TO [NAMES]  -- syncs tree + tools to 08 first
W=$(cd "$(dirname "$0")/../../../.." && pwd)
B=/mpac/sdicks02/jobs/clasher/cards/b1
rsync -a --delete --exclude target --exclude __pycache__ --exclude '*.pyc' "$W/engine-cards/" 127x08:$B/tree/
rsync -a "$W"/reports/cards/b1/tools/{trace,pytrace,tapcmp}.py 127x08:$B/fid/
root=$1; shift
ssh 127x08 "cd $B/fid && /mpac/sdicks02/repos/clasher-bot/.venv/bin/python apply_stats.py ../tree/py/gamedata.json stats-spec.json ../stats/gamedata.json >/dev/null; R=\$(readlink -f ../$root); CLASHER_ROOT=\$R PYTHONPATH=\$R/src FIDELITY_EXPECT_SRC=\$(readlink -f \$R/src)/ nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B ${SCRIPT:-trace.py} $*"
