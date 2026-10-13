cd /tmp && env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 taskset -c 0-15 /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -I -B /dev/shm/ia-r1/drivers/s10_drive.py --host 127x03 --create-base \
  --runtime /mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-98566c032d0b --runtime-manifest-sha256 4dd88461caa82f09bb27bc6adad1756f62dbc8d21aa041441f8c106ef9b80e04 \
  --bundle /tmp/ia-r1-bundles-DQ3CBz/end-ref-127x03-pf00 ca4ce6ef49d460ecce37bad3c6d29229b03a10697b8cd69148163c9cb8d17499 15126b74447d6a2fcfdad29d79f02c82bff7bd8c4465ae6567605e7f4034533c \
  --guard-job /mpac/sdicks02/k4s-runner/run-r1/end-staging/guard-jobs/guard-127x03-pf00 --guard-job-name k4s-end-guard-r1-pf00 --guard-manifest-sha256 ced24d01718b18941da39b6d2afc4dc230a744c45a07806581ebe0325af2045d \
  --record /tmp/ia-r1-rec-4LOdiU/s10-127x03-A --outside-end-window "AUDIT-ONLY fake host (INTEGRATION-AUDIT-r1), no real host"
