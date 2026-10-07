#!/usr/bin/env bash
# Linux: launch a resumable job, with a unique label and an exit receipt.
set -euo pipefail
base=/mpac/sdicks02
root=$base/repos/clasher
jobs=$base/jobs/clasher
case $(hostname -s) in 127x01|127x02|127x03|127x04|127x07|127x08) ;; *) echo "Not a Clasher fleet node" >&2; exit 2;; esac
mkdir -p "$jobs"
if [[ ${1:-} == --worker ]]; then
  shift; label=$1; shift
  exec 9>"$jobs/$label.lock"
  flock -n 9 || exit 75
  if [[ -e "$jobs/$label.exit" ]]; then exit "$(cat "$jobs/$label.exit")"; fi
  trap 'rc=$?; printf "%s\n" "$rc" > "$jobs/$label.exit.tmp"; mv "$jobs/$label.exit.tmp" "$jobs/$label.exit"' EXIT
  source "$base/env.sh"
  export TMPDIR="$base/tmp"
  mkdir -p "$TMPDIR"
  cd "$root"
  export PYTHONDONTWRITEBYTECODE=1 CLASHER_ROOT="$root"
  export PYTHONPATH="$root/engine-rs:$root/src"
  export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=2
  # Legacy harnesses use Path.home(); these small NFS-home links point at local NVMe.
  for spec in "clasher-engine-speed:clasher-engine-speed" "clasher-native-reference/decoded-logic-1e505767:decoded-logic-1e505767"; do
    link="$HOME/.cache/${spec%%:*}"
    target="$base/repos/clasher-local-data/${spec#*:}"
    mkdir -p "$(dirname "$link")"
    if [[ -L "$link" ]]; then
      [[ $(readlink "$link") == "$target" ]] || { echo "Unexpected link: $link" >&2; exit 2; }
    elif [[ -e "$link" ]]; then
      echo "Existing cache path requires inspection: $link" >&2; exit 2
    else
      ln -s "$target" "$link" 2>/dev/null || [[ $(readlink "$link") == "$target" ]]
    fi
  done
  date -u +%FT%TZ
  printf 'command:'; printf ' %q' "$@"; printf '\n'
  set +e
  /usr/bin/time -v "$@"
  rc=$?
  printf '%s\n' "$rc" > "$jobs/$label.exit.tmp"
  mv "$jobs/$label.exit.tmp" "$jobs/$label.exit"
  date -u +%FT%TZ
  exit "$rc"
fi
label=${1:?unique label required}; shift
[[ "$label" =~ ^[a-zA-Z0-9._-]+$ ]] || exit 2
[[ $# -gt 0 ]] || exit 2
if [[ -e "$jobs/$label.exit" ]]; then rc=$(cat "$jobs/$label.exit"); echo "completed exit=$rc"; exit "$rc"; fi
if ! flock -n "$jobs/$label.lock" true; then
  printf 'already running; pid record: '
  cat "$jobs/$label.pid" 2>/dev/null || true
  exit 0
fi
nohup setsid nice -n 10 bash "$0" --worker "$label" "$@" >> "$jobs/$label.log" 2>&1 < /dev/null &
printf '%s\n' "$!" > "$jobs/$label.pid"
printf 'pid=%s log=%s\n' "$!" "$jobs/$label.log"
