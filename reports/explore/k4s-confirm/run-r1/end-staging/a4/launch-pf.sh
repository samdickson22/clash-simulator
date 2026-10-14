#!/bin/bash
# A4 preflight launch (re-GO 556bb6e0, PF-2): one S7 session for HOST ATTEMPT ARGV_SHA, with exactly the three allow-timers.
set -u; H=$1; ATT=$2; AS=$3
R=/mpac/sdicks02/k4s-runner/run-r1; B=$R/end-prep/s5s6s7-r6; O=$R/end-staging/a4
(cd $B && sha256sum -c --quiet SHA256SUMS) || { echo "SHA256SUMS FAILED"; exit 2; }
RS=$(sha256sum $R/end-launch/ROOTS-DECLARATION.json | cut -c1-64)
cd /tmp; umask 022
echo "__START $H $ATT $(date -u +%FT%TZ)"
env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 /usr/bin/python3 -I -B $B/k4s_end_launch_gate.py \
  launch --host $H --kind preflight --attempt $ATT --argv-sha256 $AS --roots-sha256 $RS \
  --allow-timer "anacron.timer=hourly daytime anacron; no-op after cron.daily; preflight non-claiming; any load only raises measured bus (conservative)" \
  --allow-timer "systemd-tmpfiles-clean.timer=brief tmp cleanup; preflight non-claiming; conservative for bus gate" \
  --allow-timer "ua-timer.timer=short status refresh; preflight non-claiming; conservative for bus gate"
rc=$?; echo "__RC $H $ATT $rc $(date -u +%FT%TZ)"; exit $rc
