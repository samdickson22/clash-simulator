#!/bin/bash
# Offline, 127x05 only: (1) k4s_a6_builder.py build + self-check into ../builder-proof (must be ABSENT);
# (2) the INTEGRATION-AUDIT-r1 drivers frozen_job_drive.py / s9_equiv_drive.py (scratch paths substituted only)
# against that END-JOB on a scratch copy of repo-full/.git. Writes only ../builder-proof, this directory's *.out/X/
# driver copies, and /dev/shm/s567r4/audit (removed at the end). No network, no host.
set -euo pipefail
umask 022
export PYTHONDONTWRITEBYTECODE=1
HERE=$(cd "$(dirname "$0")" && pwd -P); PKG=$(dirname "$HERE")
RUNNER=/mpac/sdicks02/k4s-runner/run-r1; A=$RUNNER/end-staging/INTEGRATION-AUDIT-r1/runlog/drivers
PY312=/mpac/sdicks02/venvs/k4s-freeze/bin/python; E4V3=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python
P=98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb; REL=reports/explore/k4s-confirm/end/END-JOB.json
RUNTIME=$RUNNER/end-staging/runtime-98566c032d0b; RTM=4dd88461caa82f09bb27bc6adad1756f62dbc8d21aa041441f8c106ef9b80e04
test "$(sha256sum "$RUNTIME/runtime-manifest.json" | cut -c1-64)" = "$RTM"
OUT=$PKG/builder-proof; test ! -e "$OUT"
nice -n 19 taskset -c 16-23 $PY312 -I -B "$PKG/k4s_a6_builder.py" build \
  --declared-by "s5s6s7-r4 builder proof on 127x05 (scratch self-check only; NOT the A6 declaration)" --out "$OUT"
S=$(sha256sum "$OUT/END-JOB.json" | cut -c1-64)
nice -n 19 taskset -c 16-23 $PY312 -I -B "$PKG/k4s_a6_builder.py" self-check --out "$OUT" --job-sha256 "$S"
W=/dev/shm/s567r4/audit; rm -rf "$W"; mkdir -p "$W/code" "$W/home" "$W/eqclone"
cp -a $RUNNER/end-prep/s3s9s10-r3 "$W/code/"; (cd "$W/code/s3s9s10-r3" && sha256sum -c --quiet SHA256SUMS)
cp -a $RUNNER/end-prep/repo-full/.git "$W/eqclone/.git"
G="env -i PATH=/usr/bin:/bin HOME=$W/home LC_ALL=C GIT_CONFIG_NOSYSTEM=1 GIT_AUTHOR_NAME=audit-rerun GIT_AUTHOR_EMAIL=a@127x05 GIT_COMMITTER_NAME=audit-rerun GIT_COMMITTER_EMAIL=a@127x05 PYTHONDONTWRITEBYTECODE=1"
mkdir -p "$W/eqclone/$(dirname $REL)"; cp "$OUT/END-JOB.json" "$W/eqclone/$REL"
$G git -C "$W/eqclone" -c core.hooksPath=/dev/null add -- $REL
$G git -C "$W/eqclone" -c core.hooksPath=/dev/null commit -q -m "audit rerun: END-JOB alone (scratch)"
X=$($G git -C "$W/eqclone" rev-parse HEAD)
test "$($G git -C "$W/eqclone" diff-tree -r --name-only --no-renames $P $X)" = "$REL"
$G /usr/bin/python3 -I -B - "$W" "$P" <<'PYEOF'
import json, os, subprocess, sys
W, P = sys.argv[1:3]; repo = W + "/eqclone"
show = lambda c, r: subprocess.run(["git", "-C", repo, "show", c + ":" + r], capture_output=True, check=True).stdout
raw = show(P, "reports/explore/k4s-confirm/end-evidence.json"); ev = json.loads(raw)
items = [ev[k] for k in ("plan", "completion", "blind_ledger", "counted_inventory")]
items += [e[f] for e in ev["phases"] for f in ("launch", "supervisor_exit", "mhz", "census")]
os.makedirs(W + "/evidence"); open(W + "/evidence/end-evidence.json", "xb").write(raw)
for it in items:
    p = W + "/evidence/" + it["path"]; os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "xb").write(show(it["commit"], it["repository_path"]))
print("materialized", 1 + len(items))
PYEOF
sed -e "s#/dev/shm/ia-r1/eqclone#$W/eqclone#" \
    -e "s#/tmp/ia-r1-bundles-DQ3CBz/end-ref-127x03-pf00/k4s-end-evidence/end-evidence.json#$W/evidence/end-evidence.json#" \
    $A/frozen_job_drive.py > "$HERE/frozen_job_drive.py"
sed -e "s#/dev/shm/ia-r1/code/s3s9s10-r3#$W/code/s3s9s10-r3#" -e "s#/dev/shm/ia-r1/eqclone#$W/eqclone#" \
    $A/s9_equiv_drive.py > "$HERE/s9_equiv_drive.py"
echo "X=$X" > "$HERE/X"
(cd "$W" && $G nice -n 19 taskset -c 16-23 $E4V3 -I -B "$HERE/frozen_job_drive.py" --claim) > "$HERE/frozen_job_drive.out" 2>&1
(cd "$W" && $G nice -n 19 taskset -c 16-23 $E4V3 -I -B "$HERE/s9_equiv_drive.py" equivalence --out "$RUNTIME" \
  --manifest-sha256 $RTM --end-job-commit "$X") > "$HERE/s9_equiv_drive.out" 2>&1
test -z "$(ls -A "$W/home")"
chmod -R u+w "$W"; rm -rf "$W"
echo "rerun OK X=$X"
