#!/bin/sh
# Invoke from the staged code directory under ~/clasher-pretrain-bench/.
set -eu
exec "$HOME/clasher-live/venv/bin/python" -B -m bot.pretrain_v1.bench_selected "$@"
