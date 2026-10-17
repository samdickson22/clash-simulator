"""Pre-stop check for the live-diag -wint/-K2 package (read-only; run on the Mac BEFORE stopping the running session,
AFTER the RESUME stage is installed into fullpool-r1 and fullpool-r1-wint was created from it with the 2 files added).
  ~/clasher-live/venv/bin/python -B verify_wint_manifest.py PKG_DIR
Same logic as the loop owner's verify_stage_manifest.py, for code dir loop/code/fullpool-r1-wint and
PKG_DIR/MANIFEST-fullpool-wint.json: every entry is either supplied by the package (FILES row with the manifest's sha) or
already on disk with that sha; FILES stage files match their sha; the launcher is executable. Exit 0 = PRECHECK-OK."""
import hashlib, json, os, sys
from pathlib import Path

B = Path.home()/'clasher-live'
CODE = B/'loop'/'code'/'fullpool-r1-wint'
pkg = Path(sys.argv[1]).expanduser()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
problems = []
rows = [l.split() for l in open(pkg/'FILES') if l.strip() and not l.startswith('#')]
supplied = {}
for src, dest, want in rows:
    if not (pkg/src).is_file():
        problems.append(f'package file missing: {src}')
    elif sha(pkg/src) != want:
        problems.append(f'package file sha mismatch: {src}')
    supplied[os.path.normpath(B/dest)] = want
man = json.loads((pkg/'MANIFEST-fullpool-wint.json').read_text())['files']
on_disk = from_pkg = 0
for rel, want in man.items():
    p = os.path.normpath(CODE/rel)
    if p in supplied:
        if supplied[p] != want:
            problems.append(f'package supplies {rel} with another sha than the manifest')
        from_pkg += 1
    elif not os.path.isfile(p):
        problems.append(f'MISSING on disk: {rel}')
    elif sha(p) != want:
        problems.append(f'CHANGED on disk: {rel}')
    else:
        on_disk += 1
src_of = {os.path.normpath(B/dest): src for src, dest, _ in rows}
for exe in (B/'loop'/'run-fullpool-wint.sh', B/'loop'/'bin'/'bsbounds'):
    target = pkg/src_of[os.path.normpath(exe)] if os.path.normpath(exe) in src_of else exe   # supplied: check the package copy
    if not (os.path.isfile(target) and os.access(target, os.X_OK)):     # a regular executable file (not a dir)
        problems.append(f'not executable: {target}')
print(f'manifest entries {len(man)}: on disk {on_disk}, from package {from_pkg}; problems {len(problems)}')
for x in problems[:40]:
    print('  ', x)
print('PRECHECK-OK' if not problems else 'PRECHECK-FAIL')
sys.exit(0 if not problems else 1)
