#!/usr/bin/env bash
set -euo pipefail
[[ $(hostname -s) == 127x01 ]] || exit 2
output=${1:?fresh fixture directory}
mkdir "$output"
code=/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/live-loop/v4/l1
python=/mpac/sdicks02/envs/clasher-gpu/bin/python
"$python" -B "$code/test_selection_matrix_v4.py"
"$python" -B "$code/test_validation_select_v4.py" --output "$output/select"
"$python" -B "$code/test_verify_event_selection_v4.py" --output "$output/verify-event"
"$python" -B "$code/test_verify_calibration_v4.py" --output "$output/verify-calibration"
"$python" -B "$code/test_joint_selection_v4.py" --output "$output/joint"
