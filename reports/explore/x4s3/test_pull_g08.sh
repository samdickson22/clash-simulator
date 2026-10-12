#!/usr/bin/env bash
# Fixture tests for pull_g08.sh r3 (X4S-3, exploration). Local only, no ssh.
# Each case runs a copy of pull_g08.sh with ONLY these substitutions:
#   /mpac -> $T/mpac (job prefix and 08 source root live in a fixture tree);
#   p="" -> p="$T" (ancestor walk starts at the fixture root);
#   hostname check 127x01 -> this host; `ssh "${SSH_OPTS[@]}" 127x08` -> `bash -c`;
#   rsync source "127x08:$SRC/" -> "$SRC/".
# Publication cases put a test-only `date` wrapper first on PATH: on its 2nd call (the
# end-stamp generation) it touches STOP or sends TERM to the pull script, then runs date.
# Cleanup is checked by the exact owned PGID the script reports, not by name search.
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
  G=$J/data/g08
  sed -e "s#/mpac#$T/mpac#g" -e "s#^p=\"\"\$#p=\"$T\"#" -e "s#== 127x01 ]]#== $host ]]#" \
      -e 's#ssh "${SSH_OPTS\[@\]}" 127x08 \\#bash -c \\#' -e 's#"127x08:$SRC/"#"$SRC/"#' \
      "$HERE/pull_g08.sh" > "$T/pull.sh"
  if grep -q 'SSH_OPTS\[@\]}" 127x08\|127x08:' "$T/pull.sh"; then echo "substitution failed" >&2; exit 2; fi
  mkdir "$T/bin"
  cat > "$T/bin/date" <<EOF
#!/usr/bin/env bash
n=\$(( \$(cat "$T/date-calls" 2>/dev/null || echo 0) + 1 )); echo \$n > "$T/date-calls"
if [[ \$n -eq 2 ]]; then
  case "\${FAKE_DATE_MODE:-}" in
    stop) touch "$J/STOP" ;;
    term) kill -TERM \$PPID; sleep 1 ;;
  esac
fi
exec /bin/date "\$@"
EOF
  chmod +x "$T/bin/date"
}
# Processes left in the owned group the script reported (0 if it reported none).
group_left() {
  local g; g=$(sed -n 's/.*processes still in owned group \([0-9]*\).*/\1/p' "$T/err" | tail -1)
  [[ -z $g ]] && { echo 0; return; }
  ps -eo pgid= | awk -v g="$g" '$1 == g' | wc -l
}
no_marker() { [[ ! -e $G/pull-end-utc.txt && ! -e $G/pull-end-utc.tmp ]]; }
report() { echo "{\"case\":\"$1\",\"ok\":$2,\"rc\":$3}"; [[ $2 == true ]] || fail=1; }
cleanup() { rm -rf "$T"; }
# Background jobs of a non-interactive shell start with SIGINT ignored (and an ignored-on-entry
# signal cannot be trapped); restore default dispositions before exec, as a foreground run has.
run_bg() { python3 -c 'import os,signal,sys; [signal.signal(s, signal.SIG_DFL) for s in (signal.SIGINT, signal.SIGQUIT)]; os.execvp("bash", ["bash", sys.argv[1]])' "$T/pull.sh" >/dev/null 2>"$T/err" & pid=$!; }

# 1 success
setup; bash "$T/pull.sh" >/dev/null 2>"$T/err"; rc=$?
dirs=$(cd "$G" && ls -d batch-* | tr '\n' ' ')
ok=false; [[ $rc -eq 0 && -f $G/pull-end-utc.txt && ! -e $G/pull-end-utc.tmp && -s $G/pull-start-utc.txt && -s $G/source-stat.txt && $dirs == "batch-00000 batch-00001 batch-00002 batch-00003 batch-00004 batch-00005 batch-00006 batch-00007 batch-00008 batch-00009 batch-00010 " && ! -e $G/T1-like && ! -e $G/top.json ]] && ok=true
report success $ok $rc; cleanup

# 2 STOP during transfer (1.2 GB sparse at 40 MB/s ~ 30 s)
setup 1200M; run_bg; sleep 4; t0=$(date +%s); touch "$J/STOP"; wait $pid; rc=$?; dt=$(( $(date +%s) - t0 ))
ok=false; [[ $rc -eq 3 && $(group_left) -eq 0 && $dt -le 30 ]] && no_marker && grep -q 'owned group' "$T/err" && ok=true
report stop_during_transfer_${dt}s $ok $rc; cleanup

# 3 dangling STOP symlink before start
setup; ln -s "$T/nowhere" "$J/STOP"; bash "$T/pull.sh" >/dev/null 2>"$T/err"; rc=$?
ok=false; [[ $rc -eq 3 && ! -e $G ]] && ok=true
report dangling_stop_symlink $ok $rc; cleanup

# 4-6 TERM / INT / HUP to the pull script mid-transfer
for sig in TERM INT HUP; do
  setup 1200M; run_bg; sleep 4; kill -$sig $pid; wait $pid; rc=$?
  ok=false; [[ $rc -eq 4 && $(group_left) -eq 0 ]] && no_marker && grep -q 'owned group' "$T/err" && ok=true
  report sig$sig $ok $rc; cleanup
done

# 7 missing data directory: rejected, and nothing outside g08 is created
setup; rmdir "$J/data"; bash "$T/pull.sh" >/dev/null 2>"$T/err"; rc=$?
ok=false; [[ $rc -ne 0 && ! -e $J/data ]] && ok=true
report missing_data $ok $rc; cleanup

# 8 symlinked data ancestor (writes must not go through it)
setup; mkdir "$T/elsewhere"; rmdir "$J/data"; ln -s "$T/elsewhere" "$J/data"; bash "$T/pull.sh" >/dev/null 2>"$T/err"; rc=$?
ok=false; [[ $rc -ne 0 && -z $(ls -A "$T/elsewhere") ]] && ok=true
report symlink_ancestor $ok $rc; cleanup

# 9 symlinked g08 target
setup; mkdir "$T/elsewhere"; ln -s "$T/elsewhere" "$G"; bash "$T/pull.sh" >/dev/null 2>"$T/err"; rc=$?
ok=false; [[ $rc -ne 0 && -z $(ls -A "$T/elsewhere") ]] && ok=true
report symlink_g08 $ok $rc; cleanup

# 10 pre-existing g08
setup; mkdir "$G"; bash "$T/pull.sh" >/dev/null 2>"$T/err"; rc=$?
ok=false; [[ $rc -ne 0 && -z $(ls -A "$G") ]] && ok=true
report g08_preexists $ok $rc; cleanup

# 11 source shard is a symlink -> stat preflight fails before any transfer
setup; mv "$S/batch-00003" "$T/b3"; ln -s "$T/b3" "$S/batch-00003"; bash "$T/pull.sh" >/dev/null 2>"$T/err"; rc=$?
ok=false; [[ $rc -ne 0 && ! -e $G/pull-start-utc.txt && -z $(ls -d "$G"/batch-* 2>/dev/null) ]] && ok=true
report source_shard_symlink $ok $rc; cleanup

# 12 source packed root is a symlink
setup; mv "$S" "$T/realpacked"; ln -s "$T/realpacked" "$S"; bash "$T/pull.sh" >/dev/null 2>"$T/err"; rc=$?
ok=false; [[ $rc -ne 0 && ! -e $G/pull-start-utc.txt ]] && ok=true
report source_root_symlink $ok $rc; cleanup

# 13 STOP created while the end stamp is being generated -> exit 3, no marker, no temp
setup; FAKE_DATE_MODE=stop PATH=$T/bin:$PATH bash "$T/pull.sh" >/dev/null 2>"$T/err"; rc=$?
ok=false; [[ $rc -eq 3 && $(cat "$T/date-calls") -eq 2 ]] && no_marker && ok=true
report stop_during_publication $ok $rc; cleanup

# 14 TERM delivered while the end stamp is being generated -> exit 4, no marker, no temp
setup; FAKE_DATE_MODE=term PATH=$T/bin:$PATH bash "$T/pull.sh" >/dev/null 2>"$T/err"; rc=$?
ok=false; [[ $rc -eq 4 && $(cat "$T/date-calls") -eq 2 ]] && no_marker && ok=true
report term_during_publication $ok $rc; cleanup

echo "{\"all_ok\":$([[ $fail -eq 0 ]] && echo true || echo false)}"
exit $fail
