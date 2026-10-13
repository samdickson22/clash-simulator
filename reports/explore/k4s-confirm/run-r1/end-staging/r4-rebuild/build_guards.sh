#!/bin/bash
# Runner: production S3 (s3s9s10-r4, IR-03) guard jobs on 05 -> end-staging/guard-jobs/guard-<host>-<tag>; build then verify.
E=/mpac/sdicks02/k4s-runner/run-r1/end-prep; S=/mpac/sdicks02/k4s-runner/run-r1/end-staging
PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python; P=98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb
M=$E/admissions-copy-r1/s1b-admissions-manifest.json; MS=$(sha256sum $M | cut -c1-64)
cd /tmp; umask 022
for host in 127x03 127x04; do for tag in pf00 rd00-a00 rd00-a01; do
  case $tag in pf00) sel="--preflight 00";; rd00-a00) sel="--round 00 --attempt 00";; rd00-a01) sel="--round 00 --attempt 01";; esac
  out=$S/guard-jobs/guard-$host-$tag
  env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 $PY -I -B $E/s3s9s10-r4/s3_guard_job.py build --host $host $sel --commit $P --s1b-manifest $M --s1b-manifest-sha256 $MS --out $out
  rc=$?; echo "__BUILD $host $tag rc=$rc"; [ $rc -eq 0 ] || exit $rc
  ms=$(sha256sum $out/guard-job-manifest.json | cut -c1-64); job=$(ls $out | grep '^k4s-end-guard-r1-')
  env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 $PY -I -B $E/s3s9s10-r4/s3_guard_job.py verify --out $out --job $job --manifest-sha256 $ms
  rc=$?; echo "__VERIFY $host $tag job=$job manifest=$ms rc=$rc"; [ $rc -eq 0 ] || exit $rc
  ls $out/$job
done; done
