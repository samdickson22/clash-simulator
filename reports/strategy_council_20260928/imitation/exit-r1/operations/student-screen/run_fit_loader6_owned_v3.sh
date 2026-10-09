#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1
export EXIT_LOADER_WORKERS=6
export EXIT_LOADER_AMENDMENT=$job/student-owned-gpu-amendment-v3.json
export EXIT_LOADER_AMENDMENT_SHA256
EXIT_LOADER_AMENDMENT_SHA256=$(sha256sum "$EXIT_LOADER_AMENDMENT" | cut -d ' ' -f 1)
test -f "$job/loader-qualification/$1/PASS.json"
exec bash "$job/ops/run_fit.sh" "$@"
