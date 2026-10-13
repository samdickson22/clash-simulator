#!/bin/bash
# AUDIT-ONLY: runs the IA-P1-patched S4 copy (scratch) with the runner's real request; output in tempdir /tmp/ia-r1-bundles-DQ3CBz
H=$1; K=$2; shift 2
RQ=/mpac/sdicks02/k4s-runner/run-r1/end-staging/requests/request-$H-$K.json
cd /tmp && exec env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 taskset -c 0-15 /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B /dev/shm/ia-r1/code/b3-r5/assemble_fleet_reference.py --request $RQ --request-sha256 $(sha256sum $RQ|cut -d' ' -f1) --repository /mpac/sdicks02/k4s-runner/run-r1/end-prep/repo-full "$@" --out /tmp/ia-r1-bundles-DQ3CBz/end-ref-$H-$K
