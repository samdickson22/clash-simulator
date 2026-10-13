#!/usr/bin/env bash
# FSC: build the host bundle on 05 from committed bytes only. Usage: make_bundle.sh COMMIT OUTDIR
#   OUTDIR/fsc/   = reports/explore/fsc at COMMIT
#   OUTDIR/x4s2/  = the X4S2 files installed unchanged, from git 1501be97f
#   OUTDIR/MANIFEST.json = {commit, files: {path: sha256}}
set -euo pipefail
c=${1:?COMMIT}; out=${2:?OUTDIR}
[ ! -e "$out" ]; mkdir -p "$out/x4s2"
git archive "$c" reports/explore/fsc | tar -x -C "$out" --strip-components=2
for f in anchor_x.py sdefault.py runtime.sh detach.sh plan.json plan-ext.json reduce.py leftover.py; do
  git show "1501be97f:reports/explore/x4s2/$f" > "$out/x4s2/$f"
done
python3 -I - "$out" "$(git rev-parse "$c")" <<'EOF'
import hashlib, json, sys
from pathlib import Path
out = Path(sys.argv[1])
files = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file()}
(out/'MANIFEST.json').write_text(json.dumps(dict(commit=sys.argv[2], files=files), indent=1)+'\n')
print(json.dumps(dict(commit=sys.argv[2], files=len(files), manifest_sha256=hashlib.sha256((out/'MANIFEST.json').read_bytes()).hexdigest())))
EOF
