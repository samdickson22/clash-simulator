#!/usr/bin/env bash
# FSC launch bootstrap, run on the host by session.sh as `bash -c <this file> _ HOST MANIFEST_SHA256 STOP_AT`, with the
# bundle tar on stdin. Checks /mpac free space, then creates the fresh prefix atomically under /mpac/sdicks02/jobs-fsc (never
# /mpac/sdicks02/jobs/clasher, which is perception storage on 04), extracts the bundle, refuses any
# non-regular entry, verifies MANIFEST.json against the expected hash and every file against MANIFEST.json, then execs
# host_session.sh (which prints its own __RC). Every failure before that prints __RC=<nonzero>.
# MODE resume (epoch 2, COORDINATOR 7f93dbbf): the prefix must already exist; the bundle goes to a fresh J/bundle-e2.
set -euo pipefail
shopt -s inherit_errexit
export LC_ALL=C
trap 'echo "__RC=$?"' EXIT
host=${1:-}; msha=${2:-}; stop_at=${3:-}; mode=${4:-launch}
[[ $mode == launch || $mode == resume ]]
[[ $host == 127x03 || $host == 127x04 ]]
[[ $msha =~ ^[0-9a-f]{64}$ ]]
[[ $stop_at =~ ^20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z$ ]]
[ "$(hostname)" = "$host" ]
free=$(df -BG --output=avail /mpac | tail -n 1 | tr -dc 0-9)
[[ $free =~ ^[0-9]+$ ]]
[ "$free" -ge 20 ]
R=/mpac/sdicks02; P=$R/jobs-fsc; J=$P/fsc-${host#127x}-20261013; [ "$host" != 127x03 ] || J=${J}b   # 03: fresh leaf after the failed 02:52Z attempt (its prefix holds only bundle/, left untouched)
[ "$(realpath -e "$R")" = "$R" ]
if [ "$mode" = launch ] && [ ! -e "$P" ] && [ ! -L "$P" ]; then mkdir "$P"; fi
[ ! -L "$P" ]
[ "$(realpath -e "$P")" = "$P" ]
if [ "$mode" = launch ]; then mkdir "$J"; D=$J/bundle; else D=$J/bundle-e2; fi
[ "$(realpath -e "$J")" = "$J" ]
mkdir "$D"
[ "$(realpath -e "$D")" = "$D" ]
tar -x -f - -C "$D" --no-same-owner --no-same-permissions
cd "$D"
odd=$(find . ! -type f ! -type d)
[ -z "$odd" ]
got=$(sha256sum MANIFEST.json)
[ "${got:0:64}" = "$msha" ]
python3 -I -c '
import hashlib, json, pathlib
m = json.load(open("MANIFEST.json"))
files = {str(p) for p in pathlib.Path(".").rglob("*") if p.is_file()} - {"MANIFEST.json"}
assert files == set(m["files"]), "bundle file set differs from MANIFEST"
for rel, h in m["files"].items():
    assert hashlib.sha256(open(rel, "rb").read()).hexdigest() == h, rel
'
dl=$(cat fsc/DEADLINE)   # the single cap, from the verified bundle
[[ $dl =~ ^20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z$ ]]
[[ ! $stop_at > $dl ]]
cd /
trap - EXIT
exec nice -n 19 bash "$D/fsc/host_session.sh" "$mode" "$host" "$msha" "$stop_at"
