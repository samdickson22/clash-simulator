#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1
export EXIT_LOADER_WORKERS=6
export EXIT_LOADER_AMENDMENT=$job/student-owned-gpu-amendment-v2.json
export EXIT_LOADER_AMENDMENT_SHA256=23e63c3c70e9eaa7c5ded4c1f79300ee9eb515fbbf98721e3a46c45d6e752abf
test -f "$job/loader-qualification/$1/PASS.json"
exec bash "$job/ops/run_fit.sh" "$@"
