#!/usr/bin/env bash
# PREREG-K4S: build the staging extras for one host's qualification job, from git only (run on a checkout):
#  - the frozen T1 reference runtime: `git archive ef4c073a reports/explore/t1` code files, with plan.json's
#    T1 job input paths rebound to $JOB (same SHAs; T1 run.initialize verifies them);
#  - the committed files read by reference by unchanged T1 OP-5 tests (reference-files.json).
# Usage: export_staging_extras.sh JOB OUT_TAR      then: tar -x -C $JOB/repo -f OUT_TAR (on the host)
set -euo pipefail
job=$1; out=$2
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
tmp=$(mktemp -d)
git -C "$root" archive ef4c073a4c69e85aea0b6f9af9c1118ca8888a59 reports/explore/t1 | tar -x -C "$tmp"
( cd "$tmp/reports/explore/t1" && rm -rf receipts corpora verifier ./*.md FROZEN-T1.json seed-audit.json )
sed -i "s#/mpac/sdicks02/jobs/clasher/t1-20261010-r1#$job#g" "$tmp/reports/explore/t1/plan.json"
python3 - "$root" "$tmp" <<'PY'
import hashlib, json, os, subprocess, sys
root, tmp = sys.argv[1:]
for f in json.load(open(os.path.join(root, 'reports/explore/k4s-confirm/reference-files.json')))['files']:
    raw = subprocess.check_output(['git', '-C', root, 'show', f['commit']+':'+f['path']])
    assert hashlib.sha256(raw).hexdigest() == f['sha256'], f['path']
    d = os.path.join(tmp, f['path']); os.makedirs(os.path.dirname(d), exist_ok=True); open(d, 'wb').write(raw)
PY
tar -C "$tmp" -cf "$out" reports
rm -rf "$tmp"
echo "$out"
