#!/usr/bin/env bash
# K4S runner r1: two sealed checks 5 min apart (≈10 min); exits 2 immediately on an anomaly. Health only.
L=/mpac/sdicks02/k4s-runner/run-r1
for i in 1 2; do
  out=$(cd /tmp && python3 $L/tools/checkpoint.py ${K4S_PHASE:-replacement-r2} watch); rc=$?
  echo "$out" > $L/health/last-check.json
  echo "$out" | python3 -c "import json,sys;d=json.loads(sys.stdin.read());print(d['utc'],d['summary'],'ANOMALIES:',d['anomalies'])"
  [ $rc -ne 0 ] && { echo ANOMALY; exit 2; }
  [ $i -lt 2 ] && sleep 290
done
exit 0
