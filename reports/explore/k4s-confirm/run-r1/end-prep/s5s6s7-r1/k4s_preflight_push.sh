#!/usr/bin/env bash
# K4S END PREFLIGHT candidate (S5; derived from k4s_end_exit_push.sh): review required before any use.
# Runs k4s_end_preflight.py once in the foreground (never end_reference.py), then pushes the preflight
# directory to 05. Records that neither the registry root nor the declared attempt parent changed.
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
  "$base/preflight") ;;
  *) exit 90 ;;
esac
measurement=$job/$attempt
repository=$base/repository
attempts=$base/attempts
registry_root=$repository/reports/explore/k4s-confirm/end/registry
test -d "$job" && test ! -L "$job" || exit 90
test ! -e "$measurement" && test ! -e "$job/exit.json" || exit 90
test -f "$job/detach.log" && test -s "$job/detach.json" || exit 90
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
    case "$arg" in */k4s_end_preflight.py) script_count=$((script_count + 1)) ;; esac
  fi
done
test "$output_count" = 1 && ! "$expect_output" || exit 90
test "$repository_count" = 1 && ! "$expect_repository" || exit 90
test "$parent_count" = 1 && ! "$expect_parent" || exit 90
test "$script_count" = 1 || exit 90
test "$#" -gt 0 || exit 90
receive="/mpac/sdicks02/k4s-runner/run-r1/preflight-received/$host/$attempt"
listing() {
  if test -e "$1"; then (cd "$1" && find . -print0 | LC_ALL=C sort -z | sha256sum | cut -d' ' -f1); else echo absent; fi
}
registry_before=$(listing "$registry_root")
attempts_before=$(listing "$attempts")
printf '%s\0' "$@" > "$job/argv.nul" || exit 91

# No trap, polling, timer or network call while the foreground preflight runs.
"$@"
measurement_exit=$?
exit_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
measurement_exists=false
test ! -d "$measurement" || measurement_exists=true
registry_after=$(listing "$registry_root")
attempts_after=$(listing "$attempts")
printf '{"utc":"%s","host":"%s","attempt":"%s","exit_code":%s,"command_exited":true,"measurement_exists":%s,"registry_listing_before":"%s","registry_listing_after":"%s","attempts_listing_before":"%s","attempts_listing_after":"%s"}\n' \
  "$exit_utc" "$host" "$attempt" "$measurement_exit" "$measurement_exists" "$registry_before" "$registry_after" \
  "$attempts_before" "$attempts_after" > "$job/exit.json.tmp"
mv "$job/exit.json.tmp" "$job/exit.json" || exit 91

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
  printf '{"utc":"%s","host":"%s","attempt":"%s","transfer_complete":true,"measurement_exit_code":%s,"measurement_exists":%s}\n' \
    "$copied_utc" "$host" "$attempt" "$measurement_exit" "$measurement_exists" > "$job/TRANSFER-COMPLETE.json.tmp"
  mv "$job/TRANSFER-COMPLETE.json.tmp" "$job/TRANSFER-COMPLETE.json"
  push_file "$job/TRANSFER-COMPLETE.json" "$receive/" 30 || failed=1
fi
if test "$failed" != 0; then
  printf '{"transfer_complete":false,"measurement_exit_code":%s,"transport_failed":true}\n' \
    "$measurement_exit" > "$job/PUSH-FAILED.json"
  timeout -k 30 30 nice -n 9 taskset -c 62 rsync -a --checksum \
    "$job/PUSH-FAILED.json" "127x05:$receive/" || true
  exit 92
fi
exit "$measurement_exit"
