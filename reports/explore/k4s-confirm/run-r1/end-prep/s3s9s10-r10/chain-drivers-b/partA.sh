#!/bin/bash
CH=/tmp/k4s-r4chainb-H1qWfE; D=/dev/shm/s3s9s10r4-scratch/drivers-b; L=$CH/logs; B=/mpac/sdicks02/k4s-runner/run-r1/end-prep
step() { name=$1; shift; "$@" > $L/$name.out 2> $L/$name.err; rc=$?; echo "$(date -u +%FT%TZ) $name rc=$rc" >> $L/steps; return $rc; }
P=$(env -i PATH=/usr/bin:/bin HOME=/nonexistent GIT_OPTIONAL_LOCKS=0 git -C $B/repo-full rev-parse refs/remotes/origin/k4s-end-r1)
cd /tmp
step s9-build env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 taskset -c 8-15 /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B $B/s3s9s10-r4/s9_end_runtime.py build --commit $P --out $CH/runtime-${P:0:12} || exit 1
for k in "127x03 pf00" "127x03 rd00-a00" "127x04 pf00"; do set -- $k
  RQ=/mpac/sdicks02/k4s-runner/run-r1/end-staging/requests/request-$1-$2.json
  ADM=$(python3 -c "
import json
r=json.load(open('$RQ')); pre='$B/repo-full/'; out=[]
for n,a in sorted(r['guard']['admissions'].items()):
    assert a['source'].startswith(pre); out += ['--committed-admission', n, a['source'][len(pre):], a['sha256']]
print(' '.join(out))")
  step s4-$1-$2 $D/run_s4.sh $1 $2 $ADM || exit 1
done
echo "$(date -u +%FT%TZ) partA DONE" >> $L/steps
