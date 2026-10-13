#!/usr/bin/env bash
# FSC session wrapper, run on 127x05 only (exploration, NEVER ADOPTABLE). The only way FSC contacts 03/04.
#   session.sh launch   HOST COMMIT MANIFEST_SHA256 STOP_AT   (STOP_AT <= DEADLINE; the coordinator's STOP time)
#   session.sh progress HOST COMMIT MANIFEST_SHA256      (refused within 2 h of the last session to HOST)
#   session.sh stop     HOST COMMIT MANIFEST_SHA256
# One SSH session per call: non-persistent (no ControlMaster/ControlPersist), batch mode, provisioned host keys only.
# The bundle is rebuilt from COMMIT and must match MANIFEST_SHA256 before anything is sent or executed. The call fails
# unless both the SSH exit status and the remote's last __RC line are 0; it prints its own __RC last.
# Refused after a successful stop session for HOST (no further contact); 04 launch is refused once 03 has been stopped.
set -euo pipefail
shopt -s inherit_errexit nullglob
export LC_ALL=C
trap 'echo "__RC=$?"' EXIT
die() { echo "session FAIL: $2" >&2; exit "$1"; }
cmd=${1:-}; host=${2:-}; commit=${3:-}; msha=${4:-}; stop_at=${5:--}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEADLINE=$(cat "$HERE/DEADLINE")   # the single cap (fsc/DEADLINE); the bundle's copy must be identical
[[ $DEADLINE =~ ^20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z$ ]] || die 2 "bad DEADLINE file"
[[ $cmd == launch || $cmd == progress || $cmd == stop ]] || die 2 "command"
[[ $host == 127x03 || $host == 127x04 ]] || die 2 "host"
[[ $commit =~ ^[0-9a-f]{40}$ ]] || die 2 "full 40-hex commit"
[[ $msha =~ ^[0-9a-f]{64}$ ]] || die 2 "manifest sha"
[[ $stop_at == - || $stop_at =~ ^20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z$ ]] || die 2 "STOP_AT"
if [ "$cmd" = launch ]; then
  [ "$stop_at" != - ] || die 2 "launch needs STOP_AT"
  if [[ $stop_at > $DEADLINE ]]; then die 2 "STOP_AT after $DEADLINE"; fi
fi
[ "$(hostname)" = 127x05 ] || die 2 "run on 127x05"
REPO=/mpac/sdicks02/repos/clasher
P=/mpac/sdicks02/jobs/clasher; S=$P/fsc-sessions; MIRROR=$P/fsc-mirror-20261013
J=/mpac/sdicks02/jobs-fsc/fsc-${host#127x}-20261013
SSH=(ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none -o ControlPersist=no -o StrictHostKeyChecking=yes
     -o UpdateHostKeys=no)
[ "$(realpath -e "$P")" = "$P" ] || die 3 "$P not canonical"
mkdir -p "$S"; [ "$(realpath -e "$S")" = "$S" ] || die 3 "$S not canonical"
# Fail-closed stop history: a stop log that is a link, unreadable or not a regular file, or a grep read error, aborts.
stopped() {
  local f r g
  for f in "$S/$1"-stop-*.log; do
    if [ -L "$f" ] || [ ! -f "$f" ] || [ ! -r "$f" ]; then die 4 "stop log $f is not a readable regular file"; fi
    set +e; r=$(grep '^__RC=' "$f"); g=$?; set -e
    case $g in 0|1) ;; *) die 4 "cannot read stop log $f (grep $g)";; esac
    if [ "${r##*$'\n'}" = __RC=0 ]; then return 0; fi
  done
  return 1
}
if stopped "$host"; then die 4 "$host already stopped: no further contact"; fi
if [ "$host" = 127x04 ] && [ "$cmd" = launch ] && stopped 127x03; then die 4 "04 launch needs 03 in contact (LAN copy)"; fi
prev=("$S/$host"-*.log)
if [ "$cmd" = launch ] && [ ${#prev[@]} -gt 0 ]; then die 4 "$host already has a launch/progress session"; fi
if [ "$cmd" = progress ]; then
  [ ${#prev[@]} -gt 0 ] || die 4 "no launch yet"
  last=$(stat -c %Y "${prev[@]}" | sort -n | tail -n 1); age=$(( $(date +%s) - last ))
  [ "$age" -ge 7200 ] || die 4 "last session to $host was ${age}s ago (< 2 h)"
fi
stamp=$(date -u +%Y%m%dT%H%M%SZ)
B=$S/bundle-$host-$cmd-$stamp
( cd "$REPO" && bash "$REPO/reports/explore/fsc/make_bundle.sh" "$commit" "$B" ) >&2
got=$(sha256sum "$B/MANIFEST.json"); [ "${got:0:64}" = "$msha" ] || die 5 "bundle manifest ${got:0:64} != $msha"
odd=$(find "$B" ! -type f ! -type d); [ -z "$odd" ] || die 5 "non-regular entries in bundle"
cmp "$HERE/DEADLINE" "$B/fsc/DEADLINE" || die 5 "bundle DEADLINE differs from $HERE/DEADLINE"
log=$S/$host-$cmd-$stamp.log
case $cmd in
launch)
  boot=$(cat "$B/fsc/remote_bootstrap.sh")
  set +e
  tar -C "$B" -cf - . | "${SSH[@]}" "$host" "bash -c $(printf %q "$boot") _ $host $msha $stop_at" > "$log" 2>&1
  st=("${PIPESTATUS[@]}"); set -e
  ;;
progress|stop)
  hs=$(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["files"]["fsc/host_session.sh"])' "$B/MANIFEST.json")
  f=$J/repo/reports/explore/fsc/host_session.sh
  remote="set -euo pipefail; trap 'echo \"__RC=\$?\"' EXIT; [ \"\$(hostname)\" = $host ]; [ ! -L $f ];
    [ \"\$(realpath -e $f)\" = $f ]; echo '$hs  $f' | sha256sum -c --quiet; trap - EXIT; exec nice -n 19 bash $f $cmd $host"
  if [ "$cmd" = stop ]; then
    # Coordinator-authorized 05 mirror (F6): exactly $MIRROR/<host>/, created fresh here, canonical, link-free.
    mkdir -p "$MIRROR"; [ "$(realpath -e "$MIRROR")" = "$MIRROR" ] || die 6 "$MIRROR not canonical"
    mkdir "$MIRROR/$host"
  fi
  set +e
  "${SSH[@]}" "$host" "bash -c $(printf %q "$remote")" < /dev/null > "$log" 2>&1
  st=(0 $?); set -e
  ;;
esac
cat "$log"
last=$(grep '^__RC=' "$log" | tail -n 1 || true)
[ "${st[0]}" = 0 ] || die 7 "local tar failed (${st[0]})"
if [ "${st[1]}" != 0 ] || [ "$last" != __RC=0 ]; then die 8 "remote failed: ssh=${st[1]} $last"; fi
if [ "$cmd" = stop ]; then python3 -I "$B/fsc/stage.py" nolinks "$MIRROR/$host" >&2; fi
