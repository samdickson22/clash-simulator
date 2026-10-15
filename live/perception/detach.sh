#!/bin/bash
# usage: detach.sh LOG CMD...   (runs CMD under setsid+nice, prints PID; for 127x01 live-perception jobs)
log=$1; shift
cd /mpac/sdicks02/repos/clasher-live-perception
setsid nohup nice -n 10 "$@" > "$log" 2>&1 < /dev/null &
echo "PID $!"
