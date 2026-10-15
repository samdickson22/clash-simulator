#!/usr/bin/env bash
# 05-side driver for the LIVE loop helpers on the Mac. Every remote command is wrapped so that its output must END with
# exactly one `__RC=<0-255>` line (ssh macmini-fleet always exits 0); anything else is a failure (rc 255).
# Mac writes go only to ~/clasher-live/loop/.
#
#   mac.sh push              copy live/loop/{mac/*.swift,*.py} to ~/clasher-live/loop/src/ and verify sha256 remotely
#   mac.sh build [--check]   swiftc the helpers into ~/clasher-live/loop/bin/ (--check: typecheck only, writes nothing)
#   mac.sh rexec '<cmd>'     run one remote command (token-checked)
#   mac.sh shot <name>       read-only full-screen screencapture -> 05 $LL_SHOTS/<name>.png (+ a 1/3 preview)
#   mac.sh fetch <remote> <local>   scp a file/dir under ~/clasher-live/loop/ to 05
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
LOOP=$(dirname "$HERE")
REMOTE=${LL_REMOTE:-ssh -o BatchMode=yes -o ConnectTimeout=30 macmini-fleet}
SCP_HOST=${LL_SCP_HOST:-macmini-fleet}
SHOTS=${LL_SHOTS:-/mpac/sdicks02/scratch/live-loop/shots}
R='~/clasher-live/loop'
OUT=""

rexec() {
  local out n last
  out=$($REMOTE "setopt pipefail 2>/dev/null; { $1; }; printf '\n__RC=%s\n' \$?" 2>&1)
  OUT=$(printf '%s\n' "$out" | grep -v '^__RC=')
  printf '%s\n' "$OUT"
  n=$(printf '%s\n' "$out" | grep -c '__RC=')
  last=$(printf '%s\n' "$out" | sed '/^[[:space:]]*$/d' | tail -n 1)
  if [ "$n" -ne 1 ] || ! [[ "$last" =~ ^__RC=([0-9]{1,3})$ ]] || [ "${BASH_REMATCH[1]}" -gt 255 ]; then
    echo "mac.sh: invalid __RC token ($n token lines, last '$last')" >&2; return 255
  fi
  return "$((10#${BASH_REMATCH[1]}))"
}

files() { (cd "$LOOP" && ls mac/*.swift *.py 2>/dev/null); }

case "${1:-}" in
  push)
    rexec "mkdir -p $R/src/mac $R/bin $R/recordings $R/calib $R/logs" >/dev/null || exit 1
    (cd "$LOOP" && scp -q $(files | grep '^mac/') "$SCP_HOST:clasher-live/loop/src/mac/" \
      && { [ -z "$(files | grep -v '^mac/')" ] || scp -q $(files | grep -v '^mac/') "$SCP_HOST:clasher-live/loop/src/"; }) || exit 1
    want=$(cd "$LOOP" && sha256sum $(files) | sort -k2)
    rexec "cd $R/src && shasum -a 256 $(files | tr '\n' ' ')" >/dev/null || exit 1
    got=$(printf '%s\n' "$OUT" | sed '/^$/d' | sort -k2)
    [ "$want" = "$got" ] || { echo "mac.sh: pushed files differ"; diff <(echo "$want") <(echo "$got"); exit 1; }
    echo "pushed $(echo "$want" | wc -l) files, sha256 equal" ;;
  build)
    if [ "${2:-}" = --check ]; then
      for t in bsgrab bsclick; do
        rexec "cd $R/src/mac && swiftc -swift-version 5 -parse-as-library -typecheck bswin.swift $t.swift" || exit 1
      done
    else
      for t in bsgrab bsclick; do
        rexec "cd $R/src/mac && swiftc -swift-version 5 -parse-as-library -O bswin.swift $t.swift -o $R/bin/$t.new && mv $R/bin/$t.new $R/bin/$t && shasum -a 256 $R/bin/$t" || exit 1
      done
    fi ;;
  rexec) rexec "${2:?command}" ;;
  shot)
    name=${2:?name}; mkdir -p "$SHOTS"
    rexec "mkdir -p $R/shots && screencapture -x -t png $R/shots/$name.png" >/dev/null || exit 1
    scp -q "$SCP_HOST:clasher-live/loop/shots/$name.png" "$SHOTS/" || exit 1
    rexec "rm -f $R/shots/$name.png" >/dev/null
    python3 -c "from PIL import Image; im=Image.open('$SHOTS/$name.png'); im.resize((im.width//3, im.height//3)).save('$SHOTS/$name-small.png')"
    echo "$SHOTS/$name.png" ;;
  fetch) scp -rq "$SCP_HOST:clasher-live/loop/${2:?remote path under loop/}" "${3:?local}" ;;
  *) sed -n '2,12p' "$0"; exit 2 ;;
esac
