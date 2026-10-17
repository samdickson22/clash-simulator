#!/bin/zsh
# ~/clasher-live/loop/resume_bluestacks.sh : bring BlueStacks + Clash Royale back after a Null's block (BlueStacks quit to free
# ~4 GiB). Read-mostly and fail-fast: any step that does not come back as expected -> RESUME-FAILED (exit 1) and nothing
# further; never retries in the GUI, never touches other apps or sessions. Steps (each timed, UTC):
#   1 open -a BlueStacks (skipped if already running)          4 launch CR (monkey -p com.supercell.clashroyale, LAUNCHER)
#   2 bsgrab info: window back, size == $WANT_W x $WANT_H pt     5 wait until CR is the resumed activity, then 25 s settle
#   3 adb connect 127.0.0.1:5555 via OUR server 5047, boot done  6 one frame -> $OUT/home.png (+ bsgrab info) for the Sol check
# Exit 0 = ready for the Sol home-screen check; the driver is launched separately after that check (not by this script).
# The "tap check" is adb `input keyevent 0` (KEYCODE_UNKNOWN: exercises the input path, changes nothing on screen).
#   resume_bluestacks.sh            env: WANT_W=554 WANT_H=960 (Sam's window)
set -u
B=$HOME/clasher-live; ADB=$B/tools/platform-tools/adb; BSG=$B/loop/bin/bsgrab; SER=127.0.0.1:5555
WANT_W=${WANT_W:-554}; WANT_H=${WANT_H:-960}
OUT=$B/tmp/resume-$(date -u +%Y%m%dT%H%M%SZ); mkdir -p $OUT
T0=$(perl -MTime::HiRes=time -e 'printf "%.1f", time')
to() { local t=$1; shift; perl -e 'alarm shift; exec @ARGV or exit 127' $t "$@"; }   # per-command timeout (no coreutils)
PY=$B/venv/bin/python
el() { perl -MTime::HiRes=time -e "printf '%.1f', time - $T0"; }
say() { echo "$(date -u +%FT%TZ) +$(el)s $*" | tee -a $OUT/resume.log; }
fail() { say "RESUME-FAILED: $*"; echo "RESUME-FAILED: $*" > $OUT/RESULT; exit 1; }
a() { to 15 $ADB -P 5047 -s $SER "$@"; }
past() { (( $(perl -MTime::HiRes=time -e "print int(time - $T0)") >= $1 )); }   # elapsed-time deadline (s since start)

say "start (out $OUT)"
if to 10 pgrep -x BlueStacks > /dev/null; then
  say "1 BlueStacks already running (pid $(pgrep -x BlueStacks)), not reopened"
else
  to 30 open -a /Applications/BlueStacks.app || fail "open -a BlueStacks rc=$?"
  say "1 open -a sent"
fi
info=""
while ! past 60; do info=$(to 10 $BSG info 2>/dev/null) && break; info=""; sleep 1; done
[[ -n $info ]] || fail "2 no BlueStacks window within 60 s"
echo $info > $OUT/bsgrab-info.json
wh=$(echo $info | $PY -c 'import json,sys; b=json.load(sys.stdin)["bounds"]; print(int(round(b[2])), int(round(b[3])))')
say "2 window $info"
[[ $wh == "$WANT_W $WANT_H" ]] || fail "2 window size $wh != $WANT_W $WANT_H (crop must be re-measured before play)"
ok=0
while ! past 240; do
  to 15 $ADB -P 5047 connect $SER > /dev/null 2>&1
  [[ $(a shell getprop sys.boot_completed 2>/dev/null | tr -d '\r') == 1 ]] && { ok=1; break; }
  sleep 2
done
(( ok )) || fail "3 adb $SER (server 5047) not booted by +240 s: $(to 10 $ADB -P 5047 devices | tr '\n' ' ')"
say "3 adb $SER booted"
a shell input keyevent 0 || fail "3 adb input keyevent 0 rc=$?"
say "3 input path ok (keyevent 0)"
top() { a shell dumpsys activity activities 2>/dev/null | grep -m1 topResumedActivity; }
if top | grep -q com.supercell.clashroyale; then
  say "4 CR already resumed"
else
  a shell monkey -p com.supercell.clashroyale -c android.intent.category.LAUNCHER 1 > $OUT/monkey.txt 2>&1 \
    || fail "4 CR launch rc=$? ($(tail -1 $OUT/monkey.txt))"
  say "4 CR launch sent"
fi
ok=0
T5=$(perl -MTime::HiRes=time -e "print int(time - $T0)")
while ! past $((T5 + 60)); do top | grep -q com.supercell.clashroyale && { ok=1; break; }; sleep 1; done
(( ok )) || fail "5 CR not the resumed activity within 60 s: $(top)"
say "5 CR resumed; settling 25 s for the home screen"
sleep 25
$PY -B - $OUT/home.png <<'PY' || fail "6 frame grab failed (or timed out)"
import subprocess, sys, cv2, numpy as np, json, os, signal
signal.alarm(30)                                    # the whole capture: a stalled stream ends in SIGALRM (exit != 0)
sys.path.insert(0, os.path.expanduser('~/clasher-live/loop/code/fullpool-r1/live/loop'))
import frames
b = json.load(open(os.path.join(os.path.dirname(sys.argv[1]), 'bsgrab-info.json')))['bounds']
w, h = int(b[2]), int(b[3])
p = subprocess.Popen([os.path.expanduser('~/clasher-live/loop/bin/bsgrab'), 'stream', '--crop', f'0,0,{w},{h}', '--size', f'{2*w},{2*h}',
                      '--frames', '1'], stdout=subprocess.PIPE)
try:
    fr = next(frames.read_frames(p.stdout), None)
finally:
    if p.poll() is None:
        p.terminate()
    p.wait(timeout=10)
if fr is None:
    sys.exit('no frame')
if not cv2.imwrite(sys.argv[1], fr.bgr):
    sys.exit('imwrite failed')
print('frame', fr.bgr.shape)
PY
to 10 $BSG info > $OUT/bsgrab-info-after.json 2>&1 || fail "6 bsgrab info after the grab failed: $(cat $OUT/bsgrab-info-after.json)"
[[ -s $OUT/home.png ]] || fail "6 no home.png"
say "6 frame $OUT/home.png -> Sol check (CR home screen, no prompt/login) before any driver launch"
echo "READY-FOR-SOL-CHECK total $(el) s" > $OUT/RESULT
say "done: READY-FOR-SOL-CHECK, total $(el) s"
