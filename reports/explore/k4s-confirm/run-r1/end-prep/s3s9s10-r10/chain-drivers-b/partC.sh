#!/bin/bash
# CHAIN-b part C: steps 6, 7 and the frozen-job step of part B again, with the fake-host path fixed (part B used
# $CH/hosts/127x03/mpac/sdicks02/... instead of $CH/hosts/127x03/...; nothing ran there).
CH=/tmp/k4s-r4chainb-H1qWfE; D=/dev/shm/s3s9s10r4-scratch/drivers-b; L=$CH/logs; B=/mpac/sdicks02/k4s-runner/run-r1/end-prep
PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python; RUN="env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 taskset -c 8-15"
step() { name=$1; shift; "$@" > $L/$name.out 2> $L/$name.err; rc=$?; echo "$(date -u +%FT%TZ) $name rc=$rc" >> $L/steps; return $rc; }
P=$(env -i PATH=/usr/bin:/bin HOME=/nonexistent GIT_OPTIONAL_LOCKS=0 git -C $B/repo-full rev-parse refs/remotes/origin/k4s-end-r1)
H=/mpac/sdicks02/jobs/clasher/k4s-end-r1; FB=$CH/hosts/127x03/jobs/clasher/k4s-end-r1
cd /tmp
mkdir -p $FB/stub-native $FB/preflight/preflight-127x03-l00 && printf 'STUB native (r4 CHAIN-b deliberate stop)\n' > $FB/stub-native/clasher_core.abi3.so
mkdir $FB/bundles/end-ref-127x03-rd00-a00 && cp $CH/staging-bundles/end-ref-127x03-rd00-a00/* $FB/bundles/end-ref-127x03-rd00-a00/ || exit 1
step s5-run-c $RUN $D/ns.sh 127x03 $PY -I -B $D/s5_drive.py $(cat $L/s5-args)
step frozen-identity-c $RUN $PY -I -B $D/frozen_identity_drive.py $FB/runtime-${P:0:12} $FB/bundles/end-ref-127x03-pf00 $FB/end-inputs-r1/clasher_core.abi3.so $FB/end-inputs-r1/K4-states.pkl
step frozen-job-c $RUN $PY -I -B $D/frozen_job_drive.py $FB/runtime-${P:0:12} $FB/repository $FB/bundles/end-ref-127x03-pf00/k4s-end-evidence/end-evidence.json --claim
echo "$(date -u +%FT%TZ) partC DONE" >> $L/steps
