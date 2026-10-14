#!/usr/bin/env bash
# rocheck-r1 launcher: S5's env (launch argv: OMP/OPENBLAS/MKL=1; frozen_git_env: GIT_* stripped, P2-4 GIT keys set),
# + audit hook via PYTHONPATH, nice 19, taskset 8-23, 20 min time box.
set -u
B=/mpac/sdicks02/k4s-runner/run-r1/end-staging/rocheck-r1
PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python
for v in $(compgen -e | grep '^GIT_'); do unset "$v"; done
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_ATTR_NOSYSTEM=1 GIT_NO_REPLACE_OBJECTS=1 \
  GIT_OPTIONAL_LOCKS=0 GIT_TERMINAL_PROMPT=0 GIT_LITERAL_PATHSPECS=1 GIT_PAGER=cat GIT_NO_LAZY_FETCH=1 \
  GIT_ASKPASS=/bin/false
export GIT_CONFIG_PARAMETERS="'core.hookspath=/dev/null' 'core.fsmonitor=false' 'protocol.allow=never'"
export ROCHECK_LOG_DIR=$B/tracelog ROCHECK_LAUNCH_ARGV=$B/driver/launch-argv.json PYTHONPATH=$B/audit
mkdir -p $B/work && cd $B/work
env | sort > $B/logs/env.txt
date -u +"launch %FT%TZ"
echo "launcher pid $$"
nice -n 19 taskset -c 8-23 timeout -k 30 1200 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  "$PY" -B $B/driver/rocheck_driver.py $B/driver/k4s_end_preflight.py $B/base $B/logs/driver-steps.jsonl
rc=$?
date -u +"exit rc=$rc %FT%TZ"
echo "__RC=$rc"
