#!/bin/bash
E=/mpac/sdicks02/k4s-runner/run-r1/end-prep
PY=/mpac/sdicks02/venvs/k4s-freeze/bin/python
C=72426428cd48db0342b2cb6358211424ebc686d0
GO_REF=ea3f7686c3293d0b9d72283e905b69c14d47e039
cd /tmp && umask 022
echo "A1 start $(date -u +%FT%TZ)"
env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 $PY -I -B $E/s1s2-r5/s1_copy_end_sources.py \
    --repository $E/repo-full --commit $C --dest $E/b2-copy-r1/end-sources \
    --outside-end-window "A1 GO $GO_REF, $(date -u +%FT%TZ)"
rc=$?; echo "__RC_A1=$rc $(date -u +%FT%TZ)"
if [ $rc -ne 0 ]; then echo "A1 failed; A1b NOT run"; exit $rc; fi
echo "A1b start $(date -u +%FT%TZ)"
env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 $PY -I -B $E/s3s9s10-r3/s1b_copy_admissions.py \
    --repository $E/repo-full --commit $C --dest $E/admissions-copy-r1 \
    --outside-end-window "A1b GO $GO_REF, $(date -u +%FT%TZ)"
rc=$?; echo "__RC_A1B=$rc $(date -u +%FT%TZ)"
exit $rc
