#!/usr/bin/env bash
# X4S-3 (exploration, NEVER ADOPTABLE): the single read-only pull of the eleven
# G-08 packed shards (127x08 batch-00000..00010) listed in six-million concat
# manifest 7e21f90a. Runs ON 127x01, in the FOREGROUND, attended by the operator
# (coordinator ruling on Sol r2: R2-1 concurrent path replacement and R2-2/R2-3
# process-handoff/preflight lifecycle races are accepted residuals; no unattended run).
# r3 = r2 + coordinator items 1-5 (preexisting data, noclobber operational files,
# timeouts + LC_ALL=C, ps record on abort, temp+rename end stamp).
#
# 127x08 is only read: one stat preflight and the rsync sender, both at nice 19 /
# ionice idle. No --delete, no remote writes. Every local write (rsync receiver and
# the operational files) lands inside the fixed directory $G08, which must not exist
# before the run; $J/data and all its ancestors must already exist as real
# directories (nothing outside g08 is created). STOP ($J/STOP, -e or -L) is checked
# at start, before the transfer, every 5 s during it, and before publishing success.
# Verification is a separate step: verify_g.py --mode g08.
set -euo pipefail
set -o noclobber
umask 022
export LC_ALL=C
J=/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012
G08=$J/data/g08
SRC=/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/packed
SHARDS=(batch-00000 batch-00001 batch-00002 batch-00003 batch-00004 batch-00005
        batch-00006 batch-00007 batch-00008 batch-00009 batch-00010)
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=20)
END=$G08/pull-end-utc.txt
END_TMP=$G08/pull-end-utc.tmp

die() { echo "pull_g08: $*" >&2; exit "${2:-1}"; }
stop_present() { [[ -e $J/STOP || -L $J/STOP ]]; }
fresh() { [[ ! -e $1 && ! -L $1 ]] || die "operational file already present: $1"; }

[[ $(hostname) == 127x01 ]] || die "not 127x01"
stop_present && die "STOP present before start" 3

# Every component from / to $J/data must already exist as a real directory.
p=""
for part in mpac sdicks02 jobs clasher x4s3-student-scale-20261012 data; do
  p=$p/$part
  [[ -L $p ]] && die "symlink component: $p"
  [[ -d $p ]] || die "not an existing directory: $p"
done
[[ -e $G08 || -L $G08 ]] && die "$G08 already exists; the pull is one-shot into a fresh directory"
mkdir -- "$G08"                       # no -p: the only directory this script creates
[[ -d $G08 && ! -L $G08 ]] || die "g08 is not a real directory"

# Source-root check (read-only on 08): the packed root, its ancestors and the
# eleven shard roots must all be real directories. stat without -L does not
# follow a final link, so a symlink reports "symbolic link"; C locale on both ends.
remote_paths=(/mpac /mpac/sdicks02 /mpac/sdicks02/jobs /mpac/sdicks02/jobs/clasher
              /mpac/sdicks02/jobs/clasher/exit-g-topup-20261010 "$SRC")
for s in "${SHARDS[@]}"; do remote_paths+=("$SRC/$s"); done
stat_out=$(timeout 120 nice -n 19 ionice -c3 ssh "${SSH_OPTS[@]}" 127x08 \
  "LC_ALL=C nice -n 19 ionice -c3 stat -c '%F|%n' -- ${remote_paths[*]}") || die "remote stat failed or timed out"
fresh "$G08/source-stat.txt"
printf '%s\n' "$stat_out" > "$G08/source-stat.txt"
expected=$(for r in "${remote_paths[@]}"; do printf 'directory|%s\n' "$r"; done)
[[ $stat_out == "$expected" ]] || die "08 source root/shards are not all real directories"

inc=()
for s in "${SHARDS[@]}"; do inc+=("--include=/$s/***"); done

pgid=""
cleanup() {
  local why=$1
  rm -f -- "$END_TMP"                  # never leave an unpublished stamp
  rm -f -- "$END"                      # a failing exit never leaves a success marker
  if [[ -n $pgid ]]; then
    if kill -0 -- "-$pgid" 2>/dev/null; then
      kill -TERM -- "-$pgid" 2>/dev/null || true
      for _ in $(seq 40); do kill -0 -- "-$pgid" 2>/dev/null || break; sleep 0.5; done
      kill -KILL -- "-$pgid" 2>/dev/null || true
    fi
    wait "$pgid" 2>/dev/null || true
    echo "pull_g08: processes still in owned group $pgid after cleanup (none listed = gone):" >&2
    ps -eo pid=,pgid=,stat=,args= | awk -v g="$pgid" '$2 == g' >&2 || true
  fi
  echo "pull_g08: stopped ($why); no end timestamp published" >&2
}
trap 'cleanup signal; exit 4' INT TERM HUP

stop_present && die "STOP present before transfer" 3
fresh "$G08/pull-start-utc.txt"
date -u +%FT%TZ > "$G08/pull-start-utc.txt"
# Own process group for timeout, rsync and its ssh child.
setsid timeout 5400 nice -n 19 ionice -c3 taskset -c 56-61 \
  rsync -rt --bwlimit=40000 \
  --rsync-path='LC_ALL=C nice -n 19 ionice -c3 rsync' \
  -e 'ssh -o BatchMode=yes -o ConnectTimeout=20' \
  "${inc[@]}" --exclude='*' \
  "127x08:$SRC/" "$G08/" &
pgid=$!
# The transfer must lead its own group (unless it already exited; wait gives its status).
own=$(ps -o pgid= -p "$pgid" | tr -d ' ' || true)
if [[ -n $own && $own != "$pgid" ]]; then cleanup "no own process group"; exit 1; fi

while kill -0 "$pgid" 2>/dev/null; do
  if stop_present; then cleanup STOP; exit 3; fi
  sleep 5
done
set +e; wait "$pgid"; rc=$?; set -e
if [[ $rc -ne 0 ]]; then cleanup "rsync/timeout exit $rc"; exit "$rc"; fi

# Publish success: stamp to a fresh temp file, final STOP check, then atomic rename.
fresh "$END_TMP"; fresh "$END"
date -u +%FT%TZ > "$END_TMP"
if stop_present; then cleanup "STOP at publication"; exit 3; fi
mv -T --no-clobber -- "$END_TMP" "$END"
[[ -f $END && ! -L $END && ! -e $END_TMP ]] || { cleanup "publication failed"; exit 1; }
exit 0
