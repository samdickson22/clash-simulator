"""Fake live driver for supervisor_test.sh: holds LOOP/driver.lock like drive.py, writes runs/<name>/m01/events.jsonl.
env FAKE_MODE: battle (match_start, then 'battles' every FAKE_BATTLE_S s; exits at a battle end if RESTART-AT-BOUNDARY
exists, taking it like drive.py), crash (match_start then exit 1 after FAKE_CRASH_S), refuse (exit 3 at once, status REFUSED)."""
import fcntl, json, os, signal, sys, time
from pathlib import Path
loop, name = Path(sys.argv[1]), sys.argv[2]
mode = os.environ.get('FAKE_MODE', 'battle')
signal.signal(signal.SIGTERM, lambda s, f: sys.exit(143))
fd = open(loop/'driver.lock', 'a+'); fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
fd.seek(0); fd.truncate(); fd.write(f'pid {os.getpid()} out {name}\n'); fd.flush()
if mode == 'refuse':
    (loop/'status.txt').write_text('REFUSED (deployment check): fake\n'); sys.exit(3)
d = loop/'runs'/name/'m01'; d.mkdir(parents=True, exist_ok=True)
ev = open(d/'events.jsonl', 'a', buffering=1)
ev.write(json.dumps(dict(ev='match_start', marker=os.environ.get('FAKE_MARKER'))) + '\n')
if mode == 'crash':
    time.sleep(float(os.environ.get('FAKE_CRASH_S', 2))); sys.exit(1)
b = loop/'RESTART-AT-BOUNDARY'
while True:
    time.sleep(float(os.environ.get('FAKE_BATTLE_S', 2)))
    ev.write(json.dumps(dict(ev='match_end')) + '\n')
    if b.exists():
        b.rename(b.with_name(f'{b.name}.taken-{os.getpid()}')); ev.write(json.dumps(dict(ev='restart_at_boundary')) + '\n'); sys.exit(0)
