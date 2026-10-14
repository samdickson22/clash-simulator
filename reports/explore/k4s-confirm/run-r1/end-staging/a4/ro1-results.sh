#!/bin/bash
# RO-1 host step (COORDINATOR 02656d67, option A). NOT RUN until coordinator GO after Sol review.
# Creates the EMPTY directory <runtime>/reports/strategy_council_20260928/engine-speed/results inside the staged,
# read-only runtime (frozen es_common.py:20 mkdirs it at import). One login per host from 05 (ControlMaster off), the
# remote side at nice 19. Guards before any change: hostname; realpath(parent) == expected; parent is a real directory
# (not a symlink) with no write bits; `results` absent (no file, dir or symlink). Actions: chmod u+w parent; mkdir
# results; chmod a-w results; chmod a-w parent. Then verify modes (no write bit on either; results empty). Prints
# `stat` of the parent before and of both after. Writes nothing else on the host. Local log only on 05.
# Usage: ro1-results.sh HOST     (127x03 | 127x04)          Exit: the host __RC token (0 ok; 9x refused; 255 ssh)
set -u
H=${1:-}
case "$H" in 127x03) BASE=/mpac/sdicks02/jobs/clasher/k4s-end-r1;; 127x04) BASE=/mpac/sdicks02/jobs-k4s/k4s-end-r1;;
  *) echo "usage: $0 127x03|127x04" >&2; exit 2;; esac
P=$BASE/runtime-98566c032d0b/reports/strategy_council_20260928/engine-speed
LOG=/mpac/sdicks02/k4s-runner/run-r1/end-staging/a4/ro1-results-$H.log
REMOTE='set -u
P='"'$P'"'; H='"'$H'"'
rc(){ echo "__RC=$1"; exit 0; }
[ "$(hostname -s)" = "$H" ] || rc 90
[ -d "$P" ] && [ ! -L "$P" ] || rc 91
[ "$(realpath -e -- "$P")" = "$P" ] || rc 92
[ ! -e "$P/results" ] && [ ! -L "$P/results" ] || rc 93
[ -z "$(find "$P" -maxdepth 0 -perm /222)" ] || rc 94
echo "BEFORE $(stat -c "%A %a %U %h %i %n" -- "$P")"
chmod u+w -- "$P" || rc 95
mkdir -- "$P/results" || { chmod a-w -- "$P"; rc 96; }
chmod a-w -- "$P/results" || rc 97
chmod a-w -- "$P" || rc 98
[ -z "$(find "$P" "$P/results" -maxdepth 0 -perm /222)" ] || rc 99
[ -z "$(ls -A -- "$P/results")" ] || rc 89
echo "AFTER $(stat -c "%A %a %U %h %i %n" -- "$P")"
echo "AFTER $(stat -c "%A %a %U %h %i %n" -- "$P/results")"
rc 0'
{ echo "== $(date -u +%FT%TZ) ro1-results $H"; /usr/bin/ssh -T -o BatchMode=yes -o ControlMaster=no -o ControlPath=none \
  -o StrictHostKeyChecking=yes -o ConnectTimeout=20 -o ClearAllForwardings=yes -o RequestTTY=no -- "$H" \
  "nice -n 19 /bin/bash -c $(printf '%q' "$REMOTE")"; echo "__SSH_RC=$?"; } 2>&1 | tee -a "$LOG"
tok=$(grep -o '__RC=[0-9]*' "$LOG" | tail -1 | cut -d= -f2); exit "${tok:-255}"
