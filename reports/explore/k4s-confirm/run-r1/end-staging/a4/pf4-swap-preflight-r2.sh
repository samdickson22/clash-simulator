#!/bin/bash
# PF-4 host step r2 (COORDINATOR c14b40e8; Sol PF4-r1 N1). NOT RUN until coordinator GO after Sol review.
# Replaces exactly one staged file, <base>/tools/k4s_end_preflight.py, with the s5s6s7-r8 bytes. One ssh login per host
# from 05 (ControlMaster off); the new bytes travel on that login's stdin; the remote bash is started via
# `env -u BASH_ENV -u SHELLOPTS nice -n 19 /bin/bash -c`; body and EXIT handler begin with `set +e`.
# Remote guards before any write: hostname 90; tools is a real dir, not a symlink 91; realpath(tools) == expected 92;
# the old file is a regular single-link non-symlink 93 with the pinned OLD sha256 94 and size 95; the temp name is absent
# 96; tools has no write bits 97. A cleanup trap (EXIT, ERR->86, TERM/INT/HUP->87) is installed before writes are enabled:
# it first re-applies a-w to tools (independent of anything else), then, only for a temp file THIS run created and did
# not rename, reopens tools, removes the temp, re-applies a-w and verifies the temp is absent. A tools restore failure
# prints __CAUSE (+ __CLEANUP if any) and __RC=88; a removal/reopen failure or a surviving temp prints __CAUSE,
# __CLEANUP=<rm-failed|reopen-failed|temp-present> and __RC=85.
# Actions: chmod u+w tools 70; write stdin exclusively (noclobber) to the temp name 71; chmod 0444 temp 72; temp sha/size
# == NEW (sha probe 73, sha 74, size 75); mv -T temp -> final 76; chmod a-w tools 77. Verify after: final sha == NEW 78,
# size 79, regular single-link without write bits 80, tools without write bits 82, temp absent 83. Probe exit statuses
# are checked before use (stat 81, find 84). BEFORE/AFTER stat and sha are printed. Nothing else is written.
# Local: the new file on 05 must match NEW sha/size before any login; the status comes only from this invocation's
# captured output, parsed in Bash (exactly one __RC= line, decimal 0-255 without a leading zero) with ssh rc 0, else 255.
# Usage: pf4-swap-preflight.sh HOST     (127x03 | 127x04)
set -u
H=${1:-}
case "$H" in 127x03) BASE=/mpac/sdicks02/jobs/clasher/k4s-end-r1;; 127x04) BASE=/mpac/sdicks02/jobs-k4s/k4s-end-r1;;
  *) echo "usage: $0 127x03|127x04" >&2; exit 2;; esac
OLD_SHA=c779345116c1bf6c0ab28af8751a36489642c5b9c870326f516361f54bf115f5; OLD_SIZE=76609
NEW_SHA=09d747ac4c5ec5e92b74098ffb9996ddec00270fe489051050e134d4301b5c0b; NEW_SIZE=79878
SRC=/mpac/sdicks02/k4s-runner/run-r1/end-prep/s5s6s7-r8/k4s_end_preflight.py
T=$BASE/tools
LOG=/mpac/sdicks02/k4s-runner/run-r1/end-staging/a4/pf4-swap-$H.log
[ -f "$SRC" ] && [ ! -L "$SRC" ] && [ "$(sha256sum < "$SRC" | cut -c1-64)" = "$NEW_SHA" ] && [ "$(stat -c %s "$SRC")" = "$NEW_SIZE" ] \
  || { echo "pf4-swap: local new file does not match NEW sha/size" >&2; exit 2; }
REMOTE='set +e; set -u
T='"'$T'"'; H='"'$H'"'; OLD_SHA='"'$OLD_SHA'"'; OLD_SIZE='"'$OLD_SIZE'"'; NEW_SHA='"'$NEW_SHA'"'; NEW_SIZE='"'$NEW_SIZE'"'
F=$T/k4s_end_preflight.py; N=$T/.k4s_end_preflight.py.pf4-new
WRITABLE=0; MADE=0; STATUS=
fail(){ STATUS=$1; exit 0; }
on_exit(){
  set +e
  trap - EXIT ERR TERM INT HUP
  CLEAN=ok
  if [ "$WRITABLE" = 1 ]; then
    if chmod a-w -- "$T"; then WRITABLE=0; fi
  fi
  if [ "$MADE" = 1 ]; then
    if chmod u+w -- "$T"; then
      rm -f -- "$N"; rmrc=$?
      chmod a-w -- "$T" || WRITABLE=1
      [ "$rmrc" = 0 ] || CLEAN=rm-failed
    else
      CLEAN=reopen-failed
    fi
    if [ "$CLEAN" = ok ] && { [ -e "$N" ] || [ -L "$N" ]; }; then CLEAN=temp-present; fi
  fi
  if [ "$WRITABLE" = 1 ]; then
    echo "__CAUSE=${STATUS:-none}"; [ "$CLEAN" = ok ] || echo "__CLEANUP=$CLEAN"; echo "__RC=88"
  elif [ "$CLEAN" != ok ]; then
    echo "__CAUSE=${STATUS:-none}"; echo "__CLEANUP=$CLEAN"; echo "__RC=85"
  else
    echo "__RC=${STATUS:-86}"
  fi
}
trap on_exit EXIT
trap "fail 86" ERR
trap "fail 87" TERM INT HUP
hn=$(hostname -s) || fail 90; [ "$hn" = "$H" ] || fail 90
[ -d "$T" ] && [ ! -L "$T" ] || fail 91
rp=$(realpath -e -- "$T") || fail 92; [ "$rp" = "$T" ] || fail 92
[ -f "$F" ] && [ ! -L "$F" ] || fail 93
ln=$(stat -c %h -- "$F") || fail 81; [ "$ln" = 1 ] || fail 93
os=$(sha256sum -- "$F") || fail 73; [ "${os%% *}" = "$OLD_SHA" ] || fail 94
oz=$(stat -c %s -- "$F") || fail 81; [ "$oz" = "$OLD_SIZE" ] || fail 95
[ ! -e "$N" ] && [ ! -L "$N" ] || fail 96
perm=$(find "$T" -maxdepth 0 -perm /222 -print) || fail 84; [ -z "$perm" ] || fail 97
before=$(stat -c "%A %a %U %h %i %s %n" -- "$T" "$F") || fail 81; printf "BEFORE %s\n" "$before"; echo "BEFORE_SHA ${os%% *}"
WRITABLE=1
chmod u+w -- "$T" || fail 70
MADE=1
( set -o noclobber; cat > "$N" ) || fail 71
chmod 0444 -- "$N" || fail 72
ns=$(sha256sum -- "$N") || fail 73; [ "${ns%% *}" = "$NEW_SHA" ] || fail 74
nz=$(stat -c %s -- "$N") || fail 81; [ "$nz" = "$NEW_SIZE" ] || fail 75
mv -T -- "$N" "$F" || fail 76
MADE=0
chmod a-w -- "$T" || fail 77
WRITABLE=0
fs=$(sha256sum -- "$F") || fail 73; [ "${fs%% *}" = "$NEW_SHA" ] || fail 78
fz=$(stat -c %s -- "$F") || fail 81; [ "$fz" = "$NEW_SIZE" ] || fail 79
[ -f "$F" ] && [ ! -L "$F" ] || fail 80
fl=$(stat -c %h -- "$F") || fail 81; [ "$fl" = 1 ] || fail 80
perm=$(find "$F" -maxdepth 0 -perm /222 -print) || fail 84; [ -z "$perm" ] || fail 80
perm=$(find "$T" -maxdepth 0 -perm /222 -print) || fail 84; [ -z "$perm" ] || fail 82
[ ! -e "$N" ] && [ ! -L "$N" ] || fail 83
after=$(stat -c "%A %a %U %h %i %s %n" -- "$T" "$F") || fail 81; printf "AFTER %s\n" "$after"; echo "AFTER_SHA ${fs%% *}"
fail 0'
out=$(/usr/bin/ssh -T -o BatchMode=yes -o ControlMaster=no -o ControlPath=none -o StrictHostKeyChecking=yes \
  -o ConnectTimeout=20 -o ClearAllForwardings=yes -o RequestTTY=no -- "$H" \
  "env -u BASH_ENV -u SHELLOPTS nice -n 19 /bin/bash -c $(printf '%q' "$REMOTE")" < "$SRC" 2>&1)
ssh_rc=$?
{ echo "== $(date -u +%FT%TZ) pf4-swap-preflight-r2 $H"; printf '%s\n' "$out"; echo "__SSH_RC=$ssh_rc"; } | tee -a "$LOG"
m=0; n=0; tok=
while IFS= read -r line; do
  case "$line" in __RC=*) m=$((m + 1));; esac
  if [[ "$line" =~ ^__RC=(0|[1-9][0-9]{0,2})$ ]] && [ "${BASH_REMATCH[1]}" -le 255 ]; then n=$((n + 1)); tok=${BASH_REMATCH[1]}; fi
done <<< "$out"
if [ "$ssh_rc" -ne 0 ] || [ "$m" -ne 1 ] || [ "$n" -ne 1 ]; then
  echo "pf4-swap: fail closed (ssh_rc=$ssh_rc, __RC lines=$m, valid=$n)" >&2; exit 255
fi
exit "$tok"
