#!/bin/bash
# usage: run.sh <py312|py38> <normal|O> [--collect-only]
umask 022
B=/mpac/sdicks02/k4s-runner/run-r1/end-prep/b3-r6
FR=$(ls -d /dev/shm/b3r6/frozen-*)
case $1 in py312) PY=/mpac/sdicks02/venvs/k4s-freeze/bin/python; PP=;; py38) PY=/usr/bin/python3; PP=/dev/shm/s3s9s10r2-pytest38;; esac
OPT=; [ "$2" = O ] && OPT=-O
shift 2
cd /tmp && env PYTHONDONTWRITEBYTECODE=1 ${PP:+PYTHONPATH=$PP} K4S_FROZEN_ROOT=$FR nice -n 19 taskset -c 0-7 $PY -B $OPT -m pytest -q -p no:cacheprovider \
  -k "not test_production_q6" "$@" $B/test_assemble_fleet_reference.py $B/test_s4_r4_git.py $B/test_s4_r5_bootstrap.py $B/test_s4_r6_runtime_pin.py
