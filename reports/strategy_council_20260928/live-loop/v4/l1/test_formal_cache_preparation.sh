#!/usr/bin/env bash
set -euo pipefail
[[ $(hostname -s) == 127x01 ]] || exit 2
output=${1:?fresh fixture directory}
mkdir "$output"
code=/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/live-loop/v4/l1
python=/mpac/sdicks02/envs/clasher-gpu/bin/python
"$python" -B "$code/test_cache_allocation.py"
"$python" -B "$code/test_validation_admission_v4.py" --output "$output/admission"
bash "$code/test_body_selection_pipeline.sh" "$output/pipeline"
