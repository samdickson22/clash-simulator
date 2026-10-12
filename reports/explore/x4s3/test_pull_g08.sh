#!/usr/bin/env bash
# Fixture tests for pull_g08.sh r2 (X4S-3, exploration). Local only, no ssh.
# Each case runs a copy of pull_g08.sh with ONLY these substitutions:
#   /mpac -> $T/mpac (job prefix and 08 source root live in a fixture tree);
#   p="" -> p="$T" (ancestor walk starts at the fixture root);
#   hostname check 127x01 -> this host; `ssh "${SSH_OPTS[@]}" 127x08` -> `bash -c`;
#   rsync source "127x08:$SRC/" -> "$SRC/".
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
host=$(hostname)
fail=0

setup() {
  T=$(mktemp -d /tmp/x4s3-pull-XXXXXX)
  S=$T/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/packed
  mkdir -p "$T/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012/data" "$S/T1-like" "$S/batch-00011"
  for i in 00 01 02 03 04 05 06 07 08 09 10; do mkdir -p "$S/batch-000$i/train"; echo "$i" > "$S/batch-000$i/manifest.json"; done
  truncate -s "${1:-1M}" "$S/batch-00005/train/big.npy"
  echo x > "$S/top.json"
  J=$T/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012
  sed -e "s#/mpac#$T/mpac#g" -e "s#^p=\"\"\$#p=\"$T\"#" -e "s#== 127x01 ]]#== $host ]]#" \
      -e 's#ssh "${SSH_OPTS\[@\]}" 127x08 \\#bash -c \\#' -e 's#"127x08:$SRC/"#"$SRC/"#' \
      "$HERE/pull_g08.sh" > "$T/pull.sh"
  if grep -q 'SSH_OPTS\[@\]}" 127x08\|127x08:' "$T/pull.sh"; then echo "substitution failed" >&2; exit 2; fi
}
leftover() { pgrep -f "$T/" | grep -v "^$$\$" | wc -l; }
report() { # name ok rc
  echo "{\"case\":\"$1\",\"ok\":$2,\"rc\":$3}"; [[ $2 == true ]] || fail=1; }
cleanup() { rm -rf "$T"; }

# 1 success
setup; bash "$T/pull.sh" >/dev/null 2>&1; rc=$?
G=$J/data/g08; dirs=$(cd "$G" && ls -d batch-* | tr '\n' ' ')
ok=false; [[ $rc -eq 0 && -s $G/pull-end-utc.txt && -s $G/pull-start-utc.txt && -s $G/source-stat.txt && $dirs == "batch-00000 batch-00001 batch-00002 batch-00003 batch-00004 batch-00005 batch-00006 batch-00007 batch-00008 batch-00009 batch-00010 " && ! -e $G/T1-like && ! -e $G/top.json ]] && ok=true
report success $ok $rc; cleanup

# 2 STOP during transfer (1.2 GB sparse at 40 MB/s ~ 30 s); must stop within one 5 s poll + grace
setup 1200M; bash "$T/pull.sh" >/dev/null 2>&1 & pid=$!; sleep 4; t0=$(date +%s); touch "$J/STOP"; wait $pid; rc=$?; dt=$(( $(date +%s) - t0 ))
ok=false; [[ $rc -eq 3 && ! -e $J/data/g08/pull-end-utc.txt && $(leftover) -eq 0 && $dt -le 30 ]] && ok=true
report stop_during_transfer_${dt}s $ok $rc; cleanup

# 3 dangling STOP symlink before start
setup; ln -s "$T/nowhere" "$J/STOP"; bash "$T/pull.sh" >/dev/null 2>&1; rc=$?
ok=false; [[ $rc -eq 3 && ! -e $J/data/g08 ]] && ok=true
report dangling_stop_symlink $ok $rc; cleanup

# 4 SIGTERM to the pull script mid-transfer
setup 1200M; bash "$T/pull.sh" >/dev/null 2>&1 & pid=$!; sleep 4; kill -TERM $pid; wait $pid; rc=$?; sleep 1
ok=false; [[ $rc -eq 4 && ! -e $J/data/g08/pull-end-utc.txt && $(leftover) -eq 0 ]] && ok=true
report sigterm $ok $rc; cleanup

# 5 symlinked data ancestor (writes must not go through it)
setup; mkdir "$T/elsewhere"; rmdir "$J/data"; ln -s "$T/elsewhere" "$J/data"; bash "$T/pull.sh" >/dev/null 2>&1; rc=$?
ok=false; [[ $rc -ne 0 && -z $(ls -A "$T/elsewhere") ]] && ok=true
report symlink_ancestor $ok $rc; cleanup

# 6 symlinked g08 target
setup; mkdir "$T/elsewhere"; ln -s "$T/elsewhere" "$J/data/g08"; bash "$T/pull.sh" >/dev/null 2>&1; rc=$?
ok=false; [[ $rc -ne 0 && -z $(ls -A "$T/elsewhere") ]] && ok=true
report symlink_g08 $ok $rc; cleanup

# 7 pre-existing g08
setup; mkdir "$J/data/g08"; bash "$T/pull.sh" >/dev/null 2>&1; rc=$?
ok=false; [[ $rc -ne 0 && -z $(ls -A "$J/data/g08") ]] && ok=true
report g08_preexists $ok $rc; cleanup

# 8 source shard is a symlink -> stat preflight fails before any transfer
setup; mv "$S/batch-00003" "$T/b3"; ln -s "$T/b3" "$S/batch-00003"; bash "$T/pull.sh" >/dev/null 2>&1; rc=$?
ok=false; [[ $rc -ne 0 && ! -e $J/data/g08/pull-start-utc.txt && -z $(ls -d "$J"/data/g08/batch-* 2>/dev/null) ]] && ok=true
report source_shard_symlink $ok $rc; cleanup

# 9 source packed root is a symlink
setup; mv "$S" "$T/realpacked"; ln -s "$T/realpacked" "$S"; bash "$T/pull.sh" >/dev/null 2>&1; rc=$?
ok=false; [[ $rc -ne 0 && ! -e $J/data/g08/pull-start-utc.txt ]] && ok=true
report source_root_symlink $ok $rc; cleanup

echo "{\"all_ok\":$([[ $fail -eq 0 ]] && echo true || echo false)}"
exit $fail
