#!/usr/bin/env bash
# X4S2 backstop: vacate 127x08 before 12:30Z (coordinator 07:28Z update). Touch STOP at 12:15Z, wait for drain, verify zero X4S2 processes.
set -u
J=/mpac/sdicks02/jobs/clasher/x4s2-20261011
out=$J/logs/vacate08.jsonl
until [ "$(date -u +%H%M)" -ge 1215 ]; do sleep 20; done
s() { timeout 40 ssh -o ConnectTimeout=15 -o BatchMode=yes 127x08 "$@"; }
s "touch $J/STOP; date -u +%FT%TZ > $J/logs/STOP-touched-utc.txt"
echo "{\"utc\":\"$(date -u +%FT%TZ)\",\"event\":\"STOP touched on 127x08\"}" >> $out
while [ "$(date -u +%H%M)" -lt 1227 ]; do
  n=$(s "ps -eo args | grep -v grep | grep -c x4s2-20261011")
  echo "{\"utc\":\"$(date -u +%FT%TZ)\",\"event\":\"census\",\"x4s2_processes\":\"$n\"}" >> $out
  if [ "$n" = "0" ]; then
    s "ps -u sdicks02 -o pid=,args= | grep -v -e sshd -e 'ps -u' -e grep -e systemd -e sd-pam -e dbus -e gnome-keyring -e tracker -e 'bash -c' | head -20" > $J/logs/vacate08-user-procs.txt 2>&1
    echo "{\"utc\":\"$(date -u +%FT%TZ)\",\"event\":\"VACANT\",\"x4s2_processes\":0}" >> $out
    exit 0
  fi
  sleep 15
done
echo "{\"utc\":\"$(date -u +%FT%TZ)\",\"event\":\"NOT VACANT by 12:27Z - escalate\"}" >> $out
