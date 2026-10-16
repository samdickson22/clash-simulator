#!/usr/bin/env bash
# Offline live-path regression: one capture process per battle; background references use the main recording.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
R=$(cd "$HERE/../../.." && pwd)
T=$(mktemp -d)
VPY=/mpac/sdicks02/scratch/live-loop/venv/bin/python
export PYTHONPATH=$R:$R/src:$R/live/perception:/mpac/sdicks02/scratch/live-loop/pydeps
export CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1
export CLASHER_LIVE_FAST=student:/mpac/sdicks02/scratch/live-loop/rl5/policy-00010.pt@0.5375
export CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/live-macbench/lopp-models
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
export LL_LOCK_FILE=$T/lock LL_DECK_FILE=$T/deck LL_PAUSE_FILE=$T/PAUSE
export FAKE_IMAGES=/mpac/sdicks02/scratch/live-loop/runs/s24/m01/video/000700.jpg FAKE_HOLD=1000
export CAPTURE_TEST_LOG=$T/capture-commands.jsonl
cat > "$T/bsgrab" <<EOF
#!/bin/sh
printf '%s\n' "\$*" >> "\$CAPTURE_TEST_LOG"
exec $VPY $HERE/fake_bsgrab.py "\$@"
EOF
chmod +x "$T/bsgrab"
nice -n 19 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B "$R/live/loop/drive.py" \
  --out "$T/run" --source live --bsgrab "$T/bsgrab" --tap none --overlay-port 0 --seconds 3 --matches 2 \
  --export /mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-r5e3 > "$T/driver.log" 2>&1
"$VPY" -B - "$T" <<'PY'
import hashlib, json, sys
from pathlib import Path
t = Path(sys.argv[1])
d = t/'run/m01'
commands = (t/'capture-commands.jsonl').read_text().splitlines()
streams = [c for c in commands if c.startswith('stream ')]
assert len(streams) == 1, streams
assert '--frames 3' not in streams[0] and '--fps 4' not in streams[0], streams
e = [json.loads(l) for l in (d/'events.jsonl').read_text().splitlines()]
bg = [r for r in e if r.get('ev') == 'arena_bg']
assert len(bg) == 1 and bg[0]['source'] == 'main_stream_recording', bg
r = bg[0]
assert r['writer_pending'] is True and 'unverified' in r['availability']
assert 'files' not in r, r  # never claim queued/dropped frames were successfully stored
assert r['frames'] is None and r['requested_frames'] == len(r['candidate_files']) == 3
assert r['dir'] == 'video' and r['path_base'] == 'event_directory'
assert r['frame_metadata'] == 'frames.jsonl'
assert r['native_resolution'] is False and (r['width'],r['height']) == (720,1280)
assert all((d/r['dir']/n).is_file() for n in r['candidate_files']), r
frames = {r['n']: r for r in map(json.loads, (d/'frames.jsonl').read_text().splitlines())}
assert all(int(Path(n).stem) in frames for n in r['candidate_files'])
assert any(r.get('ev') == 'match_start' for r in e)
assert not any(r.get('ev') == 'arena_bg_error' for r in e)
assert json.loads((d/'session.json').read_text())['restarts'] == 0
# Reproduce the false-match rename/reopen operation without another driver or capture process.
before = {n: hashlib.sha256((d/r['dir']/n).read_bytes()).hexdigest() for n in r['candidate_files']}
metadata = (d/r['frame_metadata']).read_bytes()
preserved = d.with_name('m01-false-probe')
d.rename(preserved)
(d/'video').mkdir(parents=True)
for n in r['candidate_files']:
    (d/'video'/n).write_bytes(b'new battle; must not resolve here')
relocated = next(x for x in map(json.loads, (preserved/'events.jsonl').read_text().splitlines()) if x.get('ev') == 'arena_bg')
assert relocated == r
assert (preserved/r['frame_metadata']).read_bytes() == metadata
for n in r['candidate_files']:
    evidence = preserved/r['dir']/n
    assert hashlib.sha256(evidence.read_bytes()).hexdigest() == before[n]
    assert evidence.resolve() != (d/'video'/n).resolve()
print('PASS one capture stream, 3 existing JPEG references with frame metadata, no restart')
print('PASS false-match rename/reopen: relative references remain with preserved m01 evidence')
print('logs:', t)
PY
