"""Pre-stop check for a staged deploy (read-only; run on the Mac BEFORE stopping the running session).
  ~/clasher-live/venv/bin/python -B verify_stage_manifest.py STAGE_DIR
Every entry of STAGE_DIR/MANIFEST-fullpool.json (paths relative to ~/clasher-live/loop/code/fullpool-r1) must be either
supplied by the stage (a FILES row whose dest is that path, with the manifest's sha) or already on disk with that sha.
Also: every FILES row's stage file has its listed sha, and the launchers are executable. Exit 0 = PRECHECK-OK."""
import hashlib, json, os, sys
from pathlib import Path

B = Path.home()/'clasher-live'
CODE = B/'loop'/'code'/'fullpool-r1'
stage = Path(sys.argv[1]).expanduser()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
problems = []
rows = [l.split() for l in open(stage/'FILES') if l.strip() and not l.startswith('#')]
supplied = {}
for src, dest, want in rows:
    if not (stage/src).is_file():
        problems.append(f'stage file missing: {src}')
    elif sha(stage/src) != want:
        problems.append(f'stage file sha mismatch: {src}')
    supplied[os.path.normpath(B/dest)] = want
man = json.loads((stage/'MANIFEST-fullpool.json').read_text())['files']
on_disk = from_stage = 0
for rel, want in man.items():
    p = os.path.normpath(CODE/rel)
    if p in supplied:
        if supplied[p] != want:
            problems.append(f'stage supplies {rel} with another sha than the manifest')
        from_stage += 1
    elif not os.path.isfile(p):
        problems.append(f'MISSING on disk: {rel}')
    elif sha(p) != want:
        problems.append(f'CHANGED on disk: {rel}')
    else:
        on_disk += 1
for exe in (B/'loop'/'run-fullpool.sh', B/'loop'/'bin'/'bsbounds'):
    if not os.access(exe, os.X_OK):
        problems.append(f'not executable: {exe}')
print(f'manifest entries {len(man)}: on disk {on_disk}, from stage {from_stage}; problems {len(problems)}')
for x in problems[:40]:
    print('  ', x)
print('PRECHECK-OK' if not problems else 'PRECHECK-FAILED: do not stop the running session')
sys.exit(0 if not problems else 1)
