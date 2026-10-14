#!/bin/bash
# RO-1 host step r3 (COORDINATOR 02656d67; fixes SOL-REVIEW-RO1-r1 #1-#3 and RO1-r2 #1-#3). NOT RUN until coordinator GO.
# Creates the EMPTY directory <runtime>/reports/strategy_council_20260928/engine-speed/results inside the staged,
# read-only runtime (frozen es_common.py:20 mkdirs it at import). One ssh login per host from 05 (ControlMaster off);
# the remote body runs under nice 19.
# Remote, in order: guards (hostname 90; real dir, not a symlink 91; realpath == expected 92; results absent 93; parent
# without write bits 94); a cleanup trap (EXIT, ERR, TERM, INT, HUP) is installed BEFORE writes are enabled and always
# re-applies a-w to the parent (and results if it exists) when writes may be enabled; chmod u+w parent (95); mkdir
# results (96); chmod a-w parent IMMEDIATELY (98); chmod a-w results (97); verify: neither has write bits (99), results
# empty (89). Every probe's exit status is checked before its output is used (stat 81, post-find 82, ls 83, pre-find 84,
# realpath 92, hostname 90). Other codes: 86 unexpected command failure (ERR), 87 signal; 88 = a failure for which
# restoring the parent to a-w ALSO failed (the cause is printed as __CAUSE). Exactly one `__RC=<n>` line is printed.
# Local: the status comes ONLY from this invocation's captured output, parsed in Bash: exactly one line starting __RC=,
# a decimal 0-255 without a leading zero, and ssh exit 0; else fail closed (exit 255). The remote bash is started via
# `env -u BASH_ENV -u SHELLOPTS` and its body and EXIT handler begin with `set +e`. The log on 05 is append-only evidence.
# Usage: ro1-results-r2.sh HOST     (127x03 | 127x04)
set -u
H=${1:-}
case "$H" in 127x03) BASE=/mpac/sdicks02/jobs/clasher/k4s-end-r1;; 127x04) BASE=/mpac/sdicks02/jobs-k4s/k4s-end-r1;;
  *) echo "usage: $0 127x03|127x04" >&2; exit 2;; esac
P=$BASE/runtime-98566c032d0b/reports/strategy_council_20260928/engine-speed
LOG=/mpac/sdicks02/k4s-runner/run-r1/end-staging/a4/ro1-results-$H.log
REMOTE='set +e; set -u
P='"'$P'"'; H='"'$H'"'
WRITABLE=0; STATUS=
fail(){ STATUS=$1; exit 0; }
on_exit(){
  set +e
  trap - EXIT ERR TERM INT HUP
  if [ "$WRITABLE" = 1 ]; then
    if chmod a-w -- "$P"; then WRITABLE=0; fi
    if [ -d "$P/results" ] && [ ! -L "$P/results" ]; then chmod a-w -- "$P/results"; fi
  fi
  if [ "$WRITABLE" = 1 ]; then echo "__CAUSE=${STATUS:-none}"; echo "__RC=88"; else echo "__RC=${STATUS:-86}"; fi
}
trap on_exit EXIT
trap "fail 86" ERR
trap "fail 87" TERM INT HUP
hn=$(hostname -s) || fail 90; [ "$hn" = "$H" ] || fail 90
[ -d "$P" ] && [ ! -L "$P" ] || fail 91
rp=$(realpath -e -- "$P") || fail 92; [ "$rp" = "$P" ] || fail 92
[ ! -e "$P/results" ] && [ ! -L "$P/results" ] || fail 93
perm=$(find "$P" -maxdepth 0 -perm /222 -print) || fail 84; [ -z "$perm" ] || fail 94
before=$(stat -c "%A %a %U %h %i %n" -- "$P") || fail 81; echo "BEFORE $before"
WRITABLE=1
chmod u+w -- "$P" || fail 95
mkdir -- "$P/results" || fail 96
chmod a-w -- "$P" || fail 98
WRITABLE=0
chmod a-w -- "$P/results" || fail 97
perm=$(find "$P" "$P/results" -maxdepth 0 -perm /222 -print) || fail 82; [ -z "$perm" ] || fail 99
listing=$(ls -A -- "$P/results") || fail 83; [ -z "$listing" ] || fail 89
after=$(stat -c "%A %a %U %h %i %n" -- "$P" "$P/results") || fail 81; printf "AFTER %s\n" "$after"
fail 0'
out=$(/usr/bin/ssh -T -o BatchMode=yes -o ControlMaster=no -o ControlPath=none -o StrictHostKeyChecking=yes \
  -o ConnectTimeout=20 -o ClearAllForwardings=yes -o RequestTTY=no -- "$H" "env -u BASH_ENV -u SHELLOPTS nice -n 19 /bin/bash -c $(printf '%q' "$REMOTE")" 2>&1)
ssh_rc=$?
{ echo "== $(date -u +%FT%TZ) ro1-results-r3 $H"; printf '%s\n' "$out"; echo "__SSH_RC=$ssh_rc"; } | tee -a "$LOG"
# r3: count and parse in Bash only (no external command): exactly one line starting __RC=, and it must be a valid
# decimal 0-255 without a leading zero; anything else, or ssh rc != 0, fails closed with 255.
m=0; n=0; tok=
while IFS= read -r line; do
  case "$line" in __RC=*) m=$((m + 1));; esac
  if [[ "$line" =~ ^__RC=(0|[1-9][0-9]{0,2})$ ]] && [ "${BASH_REMATCH[1]}" -le 255 ]; then n=$((n + 1)); tok=${BASH_REMATCH[1]}; fi
done <<< "$out"
if [ "$ssh_rc" -ne 0 ] || [ "$m" -ne 1 ] || [ "$n" -ne 1 ]; then
  echo "ro1-results-r3: fail closed (ssh_rc=$ssh_rc, __RC lines=$m, valid=$n)" >&2; exit 255
fi
exit "$tok"
