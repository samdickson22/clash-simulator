#!/bin/bash
# r4 chain (copy of the audit's run_s4.sh): the ADOPTED b3-r6 S4, unmodified, with the runner's real request; output in /tmp/k4s-r4chainb-H1qWfE/bundles
H=$1; K=$2; shift 2
RQ=/mpac/sdicks02/k4s-runner/run-r1/end-staging/requests/request-$H-$K.json
cd /tmp && exec env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 taskset -c 8-15 /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B /mpac/sdicks02/k4s-runner/run-r1/end-prep/b3-r6/assemble_fleet_reference.py --request $RQ --request-sha256 $(sha256sum $RQ|cut -d' ' -f1) --repository /mpac/sdicks02/k4s-runner/run-r1/end-prep/repo-full "$@" --out /tmp/k4s-r4chainb-H1qWfE/bundles/end-ref-$H-$K
