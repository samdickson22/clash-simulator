#!/usr/bin/env bash
# Invoke under the 01 fleet wrapper; fixtures and compact results only.
set -euo pipefail
[[ $(hostname -s) == 127x01 ]] || exit 2
output=${1:?fresh fixture directory}
mkdir "$output"
code=/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/live-loop/v4/l1
python=/mpac/sdicks02/envs/clasher-gpu/bin/python
"$python" -B "$code/test_validation_replay_v4.py"
"$python" -B "$code/test_validation_score_v4.py" --output "$output/score"
"$python" -B "$code/test_selection_matrix_v4.py"
"$python" -B "$code/test_card_thresholds_v4.py"
"$python" -B "$code/test_validation_select_v4.py" --output "$output/select"
