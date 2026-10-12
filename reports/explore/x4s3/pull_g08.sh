#!/usr/bin/env bash
# X4S-3 (exploration, NEVER ADOPTABLE): the single read-only pull of the eleven
# G-08 packed shards (127x08 batch-00000..00010) listed in six-million concat
# manifest 7e21f90a. Runs ON 127x01. r2 (Sol review r1 P1/P5/P6 + source-root check).
#
# 127x08 is only read: one stat preflight and the rsync sender, both at nice 19 /
# ionice idle. No --delete, no remote writes. Every local write (rsync receiver and
# both timestamps) lands inside the fixed directory $G08, which must not exist
# before the run and whose ancestors must all be real directories (no symlinks).
# STOP ($J/STOP, checked with -e and -L) is polled every 5 s during the transfer;
# on STOP or a signal the owned rsync/ssh process group is killed and reaped.
# Verification is a separate step: verify_g.py --mode g08.
set -euo pipefail
umask 022
J=/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012
G08=$J/data/g08
SRC=/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/packed
SHARDS=(batch-00000 batch-00001 batch-00002 batch-00003 batch-00004 batch-00005
        batch-00006 batch-00007 batch-00008 batch-00009 batch-00010)
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=20)

die() { echo "pull_g08: $*" >&2; exit "${2:-1}"; }
stop_present() { [[ -e $J/STOP || -L $J/STOP ]]; }

[[ $(hostname) == 127x01 ]] || die "not 127x01"
stop_present && die "STOP present before start" 3

# P1: every existing component from / to $G08 must be a real directory, not a link.
p=""
for part in mpac sdicks02 jobs clasher x4s3-student-scale-20261012 data; do
  p=$p/$part
  if [[ $part == data && ! -e $p && ! -L $p ]]; then mkdir -- "$p"; fi
  [[ -L $p ]] && die "symlink component: $p"
  [[ -d $p ]] || die "not a directory: $p"
done
[[ -e $G08 || -L $G08 ]] && die "$G08 already exists; the pull is one-shot into a fresh directory"
mkdir -- "$G08"                       # no -p: fails if anything appeared meanwhile
[[ -d $G08 && ! -L $G08 ]] || die "g08 is not a real directory"

# Source-root check (read-only on 08): the packed root, its ancestors and the
# eleven shard roots must all be real directories. stat without -L does not
# follow links, so a symlink reports "symbolic link".
remote_paths=(/mpac /mpac/sdicks02 /mpac/sdicks02/jobs /mpac/sdicks02/jobs/clasher
              /mpac/sdicks02/jobs/clasher/exit-g-topup-20261010 "$SRC")
for s in "${SHARDS[@]}"; do remote_paths+=("$SRC/$s"); done
stat_out=$(nice -n 19 ionice -c3 ssh "${SSH_OPTS[@]}" 127x08 \
  "nice -n 19 ionice -c3 stat -c '%F|%n' -- ${remote_paths[*]}") || die "remote stat failed"
printf '%s\n' "$stat_out" > "$G08/source-stat.txt"
expected=$(for r in "${remote_paths[@]}"; do printf 'directory|%s\n' "$r"; done)
[[ $stat_out == "$expected" ]] || die "08 source root/shards are not all real directories"

inc=()
for s in "${SHARDS[@]}"; do inc+=("--include=/$s/***"); done

pgid=""
cleanup() {
  local why=$1
  if [[ -n $pgid ]] && kill -0 -- "-$pgid" 2>/dev/null; then
    kill -TERM -- "-$pgid" 2>/dev/null || true
    for _ in $(seq 40); do kill -0 -- "-$pgid" 2>/dev/null || break; sleep 0.5; done
    kill -KILL -- "-$pgid" 2>/dev/null || true
    wait "$pgid" 2>/dev/null || true
  fi
  echo "pull_g08: stopped ($why); no end timestamp written" >&2
}
trap 'cleanup signal; exit 4' INT TERM HUP

stop_present && die "STOP present before transfer" 3
date -u +%FT%TZ > "$G08/pull-start-utc.txt"
# Own process group for rsync and its ssh child (no job control: setsid execs in place).
setsid nice -n 19 ionice -c3 taskset -c 56-61 \
  rsync -rt --bwlimit=40000 \
  --rsync-path='nice -n 19 ionice -c3 rsync' \
  -e 'ssh -o BatchMode=yes -o ConnectTimeout=20' \
  "${inc[@]}" --exclude='*' \
  "127x08:$SRC/" "$G08/" &
pgid=$!
# rsync must lead its own group (unless it already exited; its status is checked by wait).
own=$(ps -o pgid= -p "$pgid" | tr -d ' ' || true)
if [[ -n $own && $own != "$pgid" ]]; then cleanup "no own process group"; exit 1; fi

while kill -0 "$pgid" 2>/dev/null; do
  if stop_present; then cleanup STOP; exit 3; fi
  sleep 5
done
set +e; wait "$pgid"; rc=$?; set -e
pgid=""
[[ $rc -eq 0 ]] || die "rsync exit $rc; no end timestamp written" "$rc"
stop_present && die "STOP appeared at transfer end; not marking success" 3
date -u +%FT%TZ > "$G08/pull-end-utc.txt"
