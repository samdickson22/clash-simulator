#!/usr/bin/env bash
# Invoke through fleet_run.sh on 127x01, with authentic T1 completion receipts.
set -euo pipefail
[[ $(hostname -s) == 127x01 ]] || { echo '127x01 only' >&2; exit 2; }
arm=${1:?t6 or t7}; state=${2:?T1 pipeline-state.json}; receipt=${3:?T1 phase-a-exit.json}; destination=${4:?fresh output directory}
root=/mpac/sdicks02/repos/clasher
code=$root/reports/strategy_council_20260928/live-loop/v4/l1
split=$root/reports/strategy_council_20260928/live-loop/v4/split.json
source=/mpac/sdicks02/repos/clasher-v4-data/matches
python=/mpac/sdicks02/envs/clasher-gpu/bin/python
[[ $arm == t6 || $arm == t7 ]] || exit 2
# Reserve four process slots; count existing Python workers conservatively.
workers=$(ps -u "$(id -un)" -o comm= | awk '$1 ~ /^python/ {n++} END {print n+0}')
cap=96
[[ -z $(who) ]] || cap=16
(( workers + 4 <= cap )) || { echo "Host worker capacity exceeded: $workers + 4 > $cap" >&2; exit 75; }
free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
(( free >= 16384 )) || { echo 'Need >=16GiB free GPU memory' >&2; exit 75; }
[[ ! -e $destination ]] || { echo 'Fresh output directory required' >&2; exit 2; }
mkdir -p "$destination"
"$python" "$code/formal_guard.py" --phase-state "$state" --phase-exit "$receipt" --source "$source" --split "$split" --output "$destination/admission.json"
if [[ $arm == t6 ]]; then
  "$python" "$code/prepare_t6.py" --source "$source" --split "$split" --output "$destination/dataset" --workers 2
  "$python" "$code/run_t6_shake.py" --dataset "$destination/dataset" --output "$destination/run" --epochs 24 --steps 400 --pixel-cache-mib 4096
else
  "$python" "$code/train_v4.py" --source "$source" --split "$split" --output "$destination/model" --epochs 24 --steps 400
fi
