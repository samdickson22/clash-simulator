#!/usr/bin/env bash
# K4S runner r1: launch one phase on one host. Order: verify bytes -> OA-1 copier (detached on 05, registered on the
# source) -> frozen launch.sh on the host. Usage: launch_phase.sh HOST PHASE DISPATCH_LOCAL [COPIER_CORE]
# Never touches 01/08; only the K4S job paths below.
set -euo pipefail
H=$1; PHASE=$2; DISPATCH=$3; CORE=${4:-62}
JN=${K4S_JOBNAME:-k4s-confirm-r1}
case $H in 127x03) J=/mpac/sdicks02/jobs/clasher/$JN;; 127x04) J=/mpac/sdicks02/jobs-k4s/$JN;; *) exit 2;; esac
L=/mpac/sdicks02/k4s-runner/run-r1
MANIFEST=$L/oa1/FROZEN-K4S.json
NAME=$(basename "$DISPATCH")
want_manifest=$(sha256sum "$MANIFEST" | cut -d' ' -f1); want_dispatch=$(sha256sum "$DISPATCH" | cut -d' ' -f1)
# 1. bytes on the host (manifest is never overwritten once present: its sha is stamped into games)
ssh -o BatchMode=yes $H "test ! -e $J/FROZEN-K4S.json || test \$(sha256sum $J/FROZEN-K4S.json | cut -d' ' -f1) = $want_manifest"
scp -q "$DISPATCH" $H:$J/$NAME
ssh -o BatchMode=yes $H "test -e $J/FROZEN-K4S.json" || scp -q "$MANIFEST" $H:$J/FROZEN-K4S.json
ssh -o BatchMode=yes $H "set -e; test \$(sha256sum $J/FROZEN-K4S.json | cut -d' ' -f1) = $want_manifest; test \$(sha256sum $J/$NAME | cut -d' ' -f1) = $want_dispatch; test ! -e $J.STOP; test ! -e $J/STOP-\$(hostname); test -z \"\$(who)\"; echo host-ok"
# 2. OA-1 copier on 05 (lock, register, verified receipt on the source) before any supervisor
mkdir -p $L/copier
rm -f $L/copier/$H-$PHASE-pid.json
bash /mpac/sdicks02/repos/clasher-k4s-run/reports/explore/k4s-confirm/detach.sh $L/copier/$H-$PHASE.log $L/copier/$H-$PHASE-pid.json \
  taskset -c $CORE nice -n 19 /bin/python3 -B $L/oa1/mirror_k4s.py --job $J --host $H --phase $PHASE
for i in $(seq 1 60); do
  ssh -o BatchMode=yes $H "grep -q '\"active\": true' $J/owned-copier-admission.json 2>/dev/null" && break; sleep 2
done
ssh -o BatchMode=yes $H "grep -q '\"active\": true' $J/owned-copier-admission.json" || { echo "copier did not register" >&2; exit 3; }
echo copier-registered
# 3. frozen supervisor launch (nice 10, core 61, detached)
ssh -o BatchMode=yes $H "cd $J && K4S_JOB=$J bash $J/repo/reports/explore/k4s-confirm/launch.sh ${PHASE%%-r*} $J/$NAME ${PHASE#replacement-}" | tail -1
