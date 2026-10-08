#!/usr/bin/env bash
set -euo pipefail
source /mpac/sdicks02/repos/clasher-lease/env.sh
# The supervisor forks and detaches only after synchronous, serialized admission.
# It owns label creation, PID publication, and the workload start under one lock.
exec nice -n 10 /usr/bin/python3 -B "$CLASHER_LEASE_ROOT/lease_watch_v2_hotfix_20261008_r1.py" "$@"
