#!/bin/zsh
# overlay_up.sh: start the always-on clasher live page (:8765) detached, if not already running. Idempotent and safe while
# a session runs: the server only proxies the driver's own page (:8766); with an older driver still on :8765 it waits
# for the port. Logs: ~/clasher-live/loop/logs/overlay-server.log; pid: ~/clasher-live/loop/overlay-server.pid.
B=$HOME/clasher-live; CODE=$B/loop/code/${LL_CODE:-15117b86b-w1}
mkdir -p $B/loop/logs
cd $CODE/live/loop || exit 1
$B/venv/bin/python -c 'import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])' \
  $B/venv/bin/python -B overlay_server.py "$@" >> $B/loop/logs/overlay-server.log 2>&1 < /dev/null &
sleep 2
tail -1 $B/loop/logs/overlay-server.log
