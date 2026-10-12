#!/usr/bin/env bash
# Candidate: independent review required. Invoke through frozen detach.sh.
# No SSH until the exact E4 command exits. Never retry the measurement command.
set -u
job=$1
shift
case "$job" in
  /mpac/sdicks02/jobs/clasher/t1-20261010-r1/*) ;;
  *) exit 90 ;;
esac
case "$job" in *..*|*[[:space:]]*) exit 90 ;; esac
test -d "$job" || exit 90
test ! -e "$job/measurement" || exit 90
test ! -e "$job/exit.json" || exit 90
test "$#" -gt 0 || exit 90

# The idle bash parent remains outside the E4 tree. E4 owns its exact worker
# tree and enforces every frozen guard. The approved argv is supplied unchanged.
"$@"
measurement_exit=$?
exit_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
printf '{"utc":"%s","exit_code":%s,"measurement_returned":true,"outcomes_sealed":true}\n' \
  "$exit_utc" "$measurement_exit" > "$job/exit.json.tmp"
mv "$job/exit.json.tmp" "$job/exit.json"

# Both success and failure fragments survive. 05 creates this exclusive receive
# namespace before launch. All network work starts only after E4 has returned.
while test ! -e "$job/STOP-COPY"; do
  if timeout 900 nice -n 9 taskset -c 62 rsync -a --checksum --partial \
      "$job/measurement/" "127x05:$job/durable-measurement/" && \
     timeout 30 nice -n 9 taskset -c 62 rsync -a --checksum \
      "$job/exit.json" "127x05:$job/"; then
    copied_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    printf '{"utc":"%s","transfer_complete":true,"measurement_exit_code":%s,"hash_verification_pending":true}\n' \
      "$copied_utc" "$measurement_exit" > "$job/TRANSFER-COMPLETE.json.tmp"
    mv "$job/TRANSFER-COMPLETE.json.tmp" "$job/TRANSFER-COMPLETE.json"
    if timeout 30 nice -n 9 taskset -c 62 rsync -a --checksum \
        "$job/TRANSFER-COMPLETE.json" "127x05:$job/"; then
      exit "$measurement_exit"
    fi
  fi
  sleep 10
done
exit 91
