#!/usr/bin/env bash
# K4S runner r1: launch one phase on one host. Order: verify bytes -> OA-1 copier (detached on 05, registered on the
# source) -> frozen launch.sh on the host. Usage: launch_phase.sh HOST PHASE DISPATCH_LOCAL [COPIER_CORE]
# Never touches 01/08; only the K4S job paths below.
set -euo pipefail
H=$1; PHASE=$2; DISPATCH=$3; CORE=${4:-62}
[[ "$PHASE" =~ ^(smoke|reporting|replacement-r[0-9]+)$ ]] || exit 2
[[ "$CORE" =~ ^(62|63)$ ]] || exit 2
JN=${K4S_JOBNAME:-k4s-confirm-r1}
[[ "$JN" =~ ^k4s-confirm-[a-z0-9-]+$ ]] || exit 2
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
NEWPID=$(python3 -c "import json;print(json.load(open('$L/copier/$H-$PHASE-pid.json'))['pid'])")
# Registration must be THIS copier, for THIS job/phase, on hub and source (Sol ops r1 finding 4).
for i in $(seq 1 300); do
  if python3 -c "import json,sys;r=json.load(open('$J/owned-copier-admission.json'));sys.exit(0 if r['identity']['pid']==$NEWPID and r['active'] is True and r['phase']=='$PHASE' and r['job']=='$J' and r['source_host']=='$H' else 1)" 2>/dev/null \
     && ssh -o BatchMode=yes $H "python3 -c \"import json,sys;r=json.load(open('$J/owned-copier-admission.json'));sys.exit(0 if r['identity']['pid']==$NEWPID and r['active'] is True and r['phase']=='$PHASE' else 1)\""; then break; fi
  kill -0 $NEWPID 2>/dev/null || { echo "new copier $NEWPID exited before registering" >&2; exit 3; }
  sleep 2
done
python3 -c "import json,sys;r=json.load(open('$J/owned-copier-admission.json'));sys.exit(0 if r['identity']['pid']==$NEWPID and r['active'] is True else 1)" || { echo "copier did not register" >&2; exit 3; }
echo copier-registered
# 3. frozen supervisor launch (nice 10, core 61, detached)
ssh -o BatchMode=yes $H "cd $J && K4S_JOB=$J bash $J/repo/reports/explore/k4s-confirm/launch.sh ${PHASE%%-r*} $J/$NAME ${PHASE#replacement-}" | tail -1
