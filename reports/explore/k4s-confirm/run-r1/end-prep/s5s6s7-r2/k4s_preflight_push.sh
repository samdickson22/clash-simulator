#!/usr/bin/env bash
# K4S END PREFLIGHT wrapper r2 (S5; derived from k4s_end_exit_push.sh r2, safe_input adoption). Review required.
# Runs k4s_end_preflight.py once in the foreground through frozen-exec (never end_reference.py), then pushes the
# preflight directory to 05. No shell redirection writes any file: argv.nul, exit.json, TRANSFER-DONE.json and
# PUSH-FAILED.json are created through the pinned safe_input CLI (exclusive, no-follow, never replaced). The
# registry/attempt-parent listings are taken by the preflight itself through safe_input.
# Frozen detach.sh must use $job/detach.log and $job/detach.json.
set -u -o pipefail
job=${1:?JOB}
shift
python=/usr/bin/python3
host=$(hostname) || exit 90
case "$host" in
  127x03) base=/mpac/sdicks02/jobs/clasher/k4s-end-r1 ;;
  127x04) base=/mpac/sdicks02/jobs-k4s/k4s-end-r1 ;;
  *) exit 90 ;;
esac
receive_base=/mpac/sdicks02/k4s-runner/run-r1/preflight-received
tools=$base/tools
host_tool=$tools/k4s_end_host_tool.py
host_tool_sha=cf19269071d57f0d1fe9b7ce5f865b4641ecda62c88e418cd73b711a57a5d6f3
case "$job" in */|*..*|*[[:space:]]*) exit 90 ;; esac
attempt=${job##*/}
[[ "$attempt" =~ ^preflight-${host}-l[0-9]{2}$ ]] || exit 90
parent=${job%/*}
test "$parent" = "$base/preflight" || exit 90
measurement=$job/$attempt
repository=$base/repository
attempts=$base/attempts
test -d "$job" && test ! -L "$job" || exit 90
for name in "$attempt" exit.json exit.json.tmp argv.nul TRANSFER-DONE.json TRANSFER-DONE.json.tmp PUSH-FAILED.json; do
  test ! -e "$job/$name" && test ! -L "$job/$name" || exit 90
done
test -f "$job/detach.log" && test ! -L "$job/detach.log" || exit 90
test -s "$job/detach.json" && test ! -L "$job/detach.json" || exit 90
test -f "$host_tool" && test ! -L "$host_tool" || exit 90
printf '%s  %s\n' "$host_tool_sha" "$host_tool" | sha256sum --check --status --strict || exit 90
output_count=0
expect_output=false
repository_count=0
expect_repository=false
parent_count=0
expect_parent=false
script_count=0
for arg in "$@"; do
  if "$expect_output"; then
    test "$arg" = "$measurement" || exit 90
    expect_output=false
  elif "$expect_repository"; then
    test "$arg" = "$repository" || exit 90
    expect_repository=false
  elif "$expect_parent"; then
    test "$arg" = "$attempts" || exit 90
    expect_parent=false
  elif test "$arg" = --out; then
    output_count=$((output_count + 1))
    expect_output=true
  elif test "$arg" = --repository; then
    repository_count=$((repository_count + 1))
    expect_repository=true
  elif test "$arg" = --attempt-parent; then
    parent_count=$((parent_count + 1))
    expect_parent=true
  else
    case "$arg" in --o*|--rep*|--at*) exit 90 ;; esac
    case "$arg" in */end_reference.py|end_reference.py) exit 90 ;; esac
    case "$arg" in "$tools/k4s_end_preflight.py") script_count=$((script_count + 1)) ;; esac
  fi
done
test "$output_count" = 1 && ! "$expect_output" || exit 90
test "$repository_count" = 1 && ! "$expect_repository" || exit 90
test "$parent_count" = 1 && ! "$expect_parent" || exit 90
test "$script_count" = 1 || exit 90
test "$#" -gt 0 || exit 90
receive="$receive_base/$host/$attempt"
tool() { "$python" -I -S "$host_tool" "$@"; }
receipt=$(printf '%s\0' "$@" | tool si -- create-excl --host "$host" --root "$job" --rel argv.nul --max-size 65536) \
  || exit 91

# No trap, polling, timer or network call while the foreground preflight runs.
tool frozen-exec -- "$@"
measurement_exit=$?
exit_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
measurement_exists=false
test ! -d "$measurement" || measurement_exists=true
receipt=$(printf '{"utc":"%s","host":"%s","attempt":"%s","exit_code":%s,"command_exited":true,"measurement_exists":%s}\n' \
  "$exit_utc" "$host" "$attempt" "$measurement_exit" "$measurement_exists" \
  | tool si -- create-excl --host "$host" --root "$job" --rel exit.json.tmp --max-size 4096) || exit 91
tool si -- publish-excl --host "$host" --root "$job" --rel exit.json.tmp --final exit.json || exit 91

# Count and total deadline bound post-exit transport; never retry the preflight.
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
for name in exit.json detach.log detach.json argv.nul; do
  push_file "$job/$name" "$receive/" 30 || failed=1
done
if "$measurement_exists"; then
  push_file "$measurement/" "$receive/preflight/" 900 || failed=1
fi
if test "$failed" = 0; then
  copied_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  receipt=$(printf '{"utc":"%s","host":"%s","attempt":"%s","transfer_complete":true,"measurement_exit_code":%s,"measurement_exists":%s}\n' \
    "$copied_utc" "$host" "$attempt" "$measurement_exit" "$measurement_exists" \
    | tool si -- create-excl --host "$host" --root "$job" --rel TRANSFER-DONE.json.tmp --max-size 4096) || failed=1
fi
if test "$failed" = 0; then
  tool si -- publish-excl --host "$host" --root "$job" --rel TRANSFER-DONE.json.tmp --final TRANSFER-DONE.json \
    || failed=1
fi
if test "$failed" = 0; then
  push_file "$job/TRANSFER-DONE.json" "$receive/" 30 || failed=1
fi
if test "$failed" != 0; then
  receipt=$(printf '{"transfer_complete":false,"measurement_exit_code":%s,"transport_failed":true}\n' \
    "$measurement_exit" \
    | tool si -- create-excl --host "$host" --root "$job" --rel PUSH-FAILED.json --max-size 4096) || exit 92
  timeout -k 30 30 nice -n 9 taskset -c 62 rsync -a --checksum \
    "$job/PUSH-FAILED.json" "127x05:$receive/" || true
  exit 92
fi
exit "$measurement_exit"
