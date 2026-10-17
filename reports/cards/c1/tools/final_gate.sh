#!/bin/bash -p
# PREPARATION ONLY: independent approval, B2 acceptance/integration and frozen schema-2 inputs required.
set -euo pipefail
[[ $# == 5 ]] || { echo 'Expected RUN SOURCE NATIVE_SHA256 B2_ACCEPTED_COMMIT TOOLS_COMMIT' >&2; exit 2; }
exec /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B \
  "$(dirname "$0")/final_gate.py" "$@"
