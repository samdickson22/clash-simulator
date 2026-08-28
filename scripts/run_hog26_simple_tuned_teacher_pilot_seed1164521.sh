#!/usr/bin/env bash

set -euo pipefail

export UPDATES=${UPDATES:-20}
export SEED=${SEED:-1164521}
export OUTPUT_ROOT=${OUTPUT_ROOT:-checkpoints/hog26_simple_tuned_teacher_pilot_seed1164521}
export REPORT_ROOT=${REPORT_ROOT:-reports/hog26_simple_tuned_teacher_pilot_seed1164521}
export LEARNING_RATE=${LEARNING_RATE:-0.00001}
export SAVE_EVERY=${SAVE_EVERY:-2}
export REQUIRE_TERMINAL_BOUNDARY=0
export COMPLETE_MARKER=hog26_simple_tuned_teacher_pilot_seed1164521_complete_v1

exec "$(dirname "$0")/run_hog26_simple_balanced_teacher_seed1164501.sh"
