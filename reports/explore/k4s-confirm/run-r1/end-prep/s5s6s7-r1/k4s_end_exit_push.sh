#!/usr/bin/env bash
# Narrow K4S END candidate (delta of T1 0a87166f): independent delta approval required before launch.
# Frozen detach.sh must use $job/detach.log and $job/detach.json.
set -u
job=${1:?JOB}
shift
host=$(hostname)
case "$host" in
  127x03) base=/mpac/sdicks02/jobs/clasher/k4s-end-r1 ;;
  127x04) base=/mpac/sdicks02/jobs-k4s/k4s-end-r1 ;;
  *) exit 90 ;;
esac
case "$job" in */|*..*|*[[:space:]]*) exit 90 ;; esac
attempt=${job##*/}
[[ "$attempt" =~ ^[A-Za-z0-9._-]+$ ]] || exit 90
parent=${job%/*}
case "$parent" in
  "$base/attempts") ;;
  *) exit 90 ;;
esac
# The claim records only basename(--out), so it must be unique per attempt: the attempt name.
measurement=$job/$attempt
repository=$base/repository
test -d "$job" && test ! -L "$job" || exit 90
test ! -e "$measurement" && test ! -e "$job/exit.json" || exit 90
test -f "$job/detach.log" && test -s "$job/detach.json" || exit 90
output_count=0
expect_output=false
repository_count=0
expect_repository=false
round_count=0
expect_round=false
for arg in "$@"; do
  if "$expect_output"; then
    test "$arg" = "$measurement" || exit 90
    expect_output=false
  elif "$expect_repository"; then
    test "$arg" = "$repository" || exit 90
    expect_repository=false
  elif "$expect_round"; then
    [[ "$arg" =~ ^(0|[1-9][0-9]?)$ ]] || exit 90
    round=$arg
    expect_round=false
  elif test "$arg" = --out; then
    output_count=$((output_count + 1))
    expect_output=true
  elif test "$arg" = --repository; then
    repository_count=$((repository_count + 1))
    expect_repository=true
  elif test "$arg" = --round; then
    round_count=$((round_count + 1))
    expect_round=true
  else
    # Also refuses argparse abbreviations/=-forms of --out, --repository and --round.
    case "$arg" in --o*|--rep*|--ro*) exit 90 ;; esac
  fi
done
test "$output_count" = 1 && ! "$expect_output" || exit 90
test "$repository_count" = 1 && ! "$expect_repository" || exit 90
test "$round_count" = 1 && ! "$expect_round" || exit 90
test "$#" -gt 0 || exit 90
registry="$repository/reports/explore/k4s-confirm/end/registry/round-$(printf '%02d' "$round")/$host"
receive="/mpac/sdicks02/k4s-runner/run-r1/end-received/$host/$attempt"
# 05 pre-creates this exact exclusive receive directory empty before launch.
printf '%s\0' "$@" > "$job/argv.nul" || exit 91

# No trap, polling, timer or network call while the foreground END command runs.
"$@"
measurement_exit=$?
exit_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
measurement_exists=false
test ! -d "$measurement" || measurement_exists=true
registry_exists=false
test ! -d "$registry" || registry_exists=true
printf '{"utc":"%s","host":"%s","attempt":"%s","exit_code":%s,"command_exited":true,"measurement_exists":%s,"registry_exists":%s}\n' \
  "$exit_utc" "$host" "$attempt" "$measurement_exit" "$measurement_exists" "$registry_exists" > "$job/exit.json.tmp"
mv "$job/exit.json.tmp" "$job/exit.json" || exit 91

# Count and total deadline bound post-exit transport; never retry END.
deadline=$((SECONDS + 1200))
push_file() {
  local source=$1 target=$2 limit=$3 tries=0 rc=0 remaining
  while test "$tries" -lt 3; do
    remaining=$((deadline - SECONDS))
    test "$remaining" -gt 0 || return 124
    test "$remaining" -ge "$limit" || limit=$remaining
    tries=$((tries + 1))
    timeout -k 30 "$limit" nice -n 9 taskset -c 62 rsync \
      -a --checksum --partial "$source" "127x05:$target"
    rc=$?
    test "$rc" -ne 0 || return 0
    case "$rc" in 255|10|12|30|35|124|137) ;; *) return "$rc" ;; esac
    test "$tries" -ge 3 || sleep 10
  done
  return "$rc"
}
failed=0
# Metadata is attempted independently and before any measurement directory.
for name in exit.json detach.log detach.json argv.nul; do
  push_file "$job/$name" "$receive/" 30 || failed=1
done
# The registry claim directory is pushed whenever it exists, with or without a measurement (RC-5).
if "$registry_exists"; then
  push_file "$registry/" "$receive/registry/" 30 || failed=1
fi
if "$measurement_exists"; then
  push_file "$measurement/" "$receive/durable-measurement/" 900 || failed=1
fi
if test "$failed" = 0; then
  copied_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  printf '{"utc":"%s","host":"%s","attempt":"%s","transfer_complete":true,"measurement_exit_code":%s,"measurement_exists":%s,"hash_verification_pending":true}\n' \
    "$copied_utc" "$host" "$attempt" "$measurement_exit" "$measurement_exists" > "$job/TRANSFER-COMPLETE.json.tmp"
  mv "$job/TRANSFER-COMPLETE.json.tmp" "$job/TRANSFER-COMPLETE.json"
  push_file "$job/TRANSFER-COMPLETE.json" "$receive/" 30 || failed=1
fi
if test "$failed" != 0; then
  printf '{"transfer_complete":false,"measurement_exit_code":%s,"transport_failed":true}\n' \
    "$measurement_exit" > "$job/PUSH-FAILED.json"
  # One final bounded metadata attempt; original evidence remains on the host.
  timeout -k 30 30 nice -n 9 taskset -c 62 rsync -a --checksum \
    "$job/PUSH-FAILED.json" "127x05:$receive/" || true
  exit 92
fi
exit "$measurement_exit"
