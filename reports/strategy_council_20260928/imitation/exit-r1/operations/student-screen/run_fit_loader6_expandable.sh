#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1
test "$1" = S-human
test -f "$job/allocator-qualification/S-human/PASS.json"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
exec bash "$job/ops/run_fit_loader6.sh" "$@"
