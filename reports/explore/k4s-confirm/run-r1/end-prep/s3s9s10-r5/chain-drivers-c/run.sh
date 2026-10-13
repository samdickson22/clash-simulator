#!/bin/bash
CH=/tmp/k4s-r4chainc-ieyb5y; D=/dev/shm/s3s9s10r4-scratch/drivers-c; L=$CH/logs; B=/mpac/sdicks02/k4s-runner/run-r1/end-prep; PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python
RUN="env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 taskset -c 8-15"
step() { name=$1; shift; "$@" > $L/$name.out 2> $L/$name.err; rc=$?; echo "$(date -u +%FT%TZ) $name rc=$rc" >> $L/steps; return $rc; }
sha() { sha256sum "$1" | cut -c1-64; }
P=$(env -i PATH=/usr/bin:/bin HOME=/nonexistent GIT_OPTIONAL_LOCKS=0 git -C $B/repo-full rev-parse refs/remotes/origin/k4s-end-r1)
S1=$B/admissions-copy-r1/s1b-admissions-manifest.json
cd /tmp
step s3-build $RUN $PY -I -B $B/s3s9s10-r4/s3_guard_job.py build --host 127x03 --preflight 00 --commit $P --s1b-manifest $S1 --s1b-manifest-sha256 $(sha $S1) --out $CH/guard-127x03-pf00 || exit 1
GS=$(sha $CH/guard-127x03-pf00/guard-job-manifest.json)
step s3-verify $RUN $PY -I -B $B/s3s9s10-r4/s3_guard_job.py verify --out $CH/guard-127x03-pf00 --job k4s-end-guard-r1-pf00 --manifest-sha256 $GS || exit 1
ADM=$(python3 -c "
import json
r=json.load(open('/mpac/sdicks02/k4s-runner/run-r1/end-staging/requests/request-127x03-pf00.json')); pre='$B/repo-full/'; out=[]
for n,a in sorted(r['guard']['admissions'].items()):
    out += ['--committed-admission', n, a['source'][len(pre):], a['sha256']]
print(' '.join(out))")
step s4-127x03-pf00 $D/run_s4.sh 127x03 pf00 $ADM || exit 1
step s10-guard $RUN $PY -I -B $D/chain_drive.py s10 --host 127x03 --create-base --guard-job $CH/guard-127x03-pf00 --guard-job-name k4s-end-guard-r1-pf00 --guard-manifest-sha256 $GS --record $CH/records/s10-guard --outside-end-window "r4 CHAIN-c fake host only" || exit 1
E4=reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3; RT=$CH/rt; mkdir -p $RT/$(dirname $E4) && cp -a /mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-98566c032d0b/runtime/$E4 $RT/$E4 && chmod -R u+w $RT   # frozen e4v3 copy (visible in the namespace)
BD=$CH/bundles/end-ref-127x03-pf00
step guard-ir03 $RUN $D/ns.sh 127x03 $PY -I -B $D/guard_ctor_drive.py $RT $BD ir03
step guard-orig $RUN $D/ns.sh 127x03 $PY -I -B $D/guard_ctor_drive.py $RT $BD orig
J=$CH/hosts/127x03/jobs/clasher; cp -a $J/k4s-end-guard-r1-pf00 $J/k4s-end-guard-r1-pf09 && chmod u+w $J/k4s-end-guard-r1-pf09 && cp $B/repo-full/reports/explore/k4s-confirm/end-guard-admissions/127x03-idle-services.json $J/k4s-end-guard-r1-pf09/idle-services.json
step guard-ir03-stale-idle-file $RUN $D/ns.sh 127x03 $PY -I -B $D/guard_ctor_drive.py $RT $BD ir03 /mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-pf09
echo "$(date -u +%FT%TZ) chain-c DONE" >> $L/steps
