#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1
test "$1" = S-human
test -f "$job/student-micro3584-amendment.json"
unset PYTORCH_CUDA_ALLOC_CONF
export EXIT_HUMAN_MICRO_OVERRIDE=3584
export EXIT_HUMAN_MICRO_AMENDMENT=$job/student-micro3584-amendment.json
exec bash "$job/ops/run_fit_loader6_owned_v3.sh" "$@"
