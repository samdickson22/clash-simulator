#!/bin/bash
# Offline, 127x05 only (r5): (1) k4s_a6_builder.py build + self-check into ../builder-proof (must be ABSENT), bound to
# the ADOPTED S9 (s3s9s10-r5) and the PRODUCTION runtime manifest named by ../ADOPTED-S9-RUNTIME.json (every pin read
# from that record and re-verified against the bytes; nothing typed); (2) the INTEGRATION-AUDIT-r1 drivers
# frozen_job_drive.py / s9_equiv_drive.py (scratch paths and the S9 package substituted only) against that END-JOB on
# a scratch copy of repo-full/.git ONLY (never the work tree). Writes only ../builder-proof, this directory's
# *.out/X/driver copies, and /dev/shm/s567r5/audit (removed on every exit). No network, no host.
# r5: S9 comes from the S9-FINAL chain only (s9_end_runtime.py, end_prep_common.py, safe_input.py, each checked against
# its S9-FINAL row), so the audit S9 driver imports s9_end_runtime directly instead of through s10_stage_host (whose
# package was not final); that one import line is the only non-path substitution. `--audit-only` skips (1) and
# re-uses an existing ../builder-proof.
set -euo pipefail
umask 022
export PYTHONDONTWRITEBYTECODE=1
HERE=$(cd "$(dirname "$0")" && pwd -P); PKG=$(dirname "$HERE")
RUNNER=/mpac/sdicks02/k4s-runner/run-r1; A=$RUNNER/end-staging/INTEGRATION-AUDIT-r1/runlog/drivers
PY312=/mpac/sdicks02/venvs/k4s-freeze/bin/python; E4V3=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python
P=98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb; REL=reports/explore/k4s-confirm/end/END-JOB.json
rec() { /usr/bin/python3 -I -c 'import json,sys; r=json.load(open(sys.argv[1])); print(eval(sys.argv[2], {"r": r}))' \
        "$PKG/ADOPTED-S9-RUNTIME.json" "$1"; }
RUNTIME=$(rec 'r["runtime"]["path"]'); RTM=$(rec 'r["runtime"]["manifest_sha256"]')
S9=$(rec 'r["s9"]["path"]'); S9SHA=$(rec 'r["s9"]["sha256"]'); S9PKG=$(dirname "$S9"); S9NAME=$(basename "$S9PKG")
test "$(sha256sum "$RUNTIME/runtime-manifest.json" | cut -c1-64)" = "$RTM"
test "$(sha256sum "$S9" | cut -c1-64)" = "$S9SHA"
(cd "$PKG" && $PY312 -I -B tests/adopt_pins.py --check)
OUT=$PKG/builder-proof
if [ "${1:-}" = "--audit-only" ]; then
  test -f "$OUT/SELF-CHECK.json"
else
  test ! -e "$OUT"
  nice -n 19 taskset -c 16-23 $PY312 -I -B "$PKG/k4s_a6_builder.py" build \
    --declared-by "s5s6s7-r5 builder proof on 127x05 (scratch self-check only; NOT the A6 declaration)" --out "$OUT"
  S=$(sha256sum "$OUT/END-JOB.json" | cut -c1-64)
  nice -n 19 taskset -c 16-23 $PY312 -I -B "$PKG/k4s_a6_builder.py" self-check --out "$OUT" --job-sha256 "$S"
fi
W=/dev/shm/s567r5/audit; rm -rf "$W"; trap 'chmod -R u+w "$W" 2>/dev/null; rm -rf "$W"' EXIT
mkdir -p "$W/code/$S9NAME" "$W/home" "$W/eqclone"
grep -v '^#' "$S9PKG/S9-FINAL" | while read -r sha size name; do
  cp -p "$S9PKG/$name" "$W/code/$S9NAME/$name"
  test "$(sha256sum "$W/code/$S9NAME/$name" | cut -c1-64)" = "$sha"; test "$(stat -c %s "$W/code/$S9NAME/$name")" = "$size"
done
test "$(sha256sum "$W/code/$S9NAME/s9_end_runtime.py" | cut -c1-64)" = "$S9SHA"
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
sed -e "s#/dev/shm/ia-r1/code/s3s9s10-r3#$W/code/$S9NAME#" -e "s#/dev/shm/ia-r1/eqclone#$W/eqclone#" \
    -e "s#^import s10_stage_host as S10\$#import s9_end_runtime as S9#" -e "/^S9 = S10.S9\$/d" \
    $A/s9_equiv_drive.py > "$HERE/s9_equiv_drive.py"
echo "X=$X" > "$HERE/X"
(cd "$W" && $G nice -n 19 taskset -c 16-23 $E4V3 -I -B "$HERE/frozen_job_drive.py" --claim) > "$HERE/frozen_job_drive.out" 2>&1
(cd "$W" && $G nice -n 19 taskset -c 16-23 $E4V3 -I -B "$HERE/s9_equiv_drive.py" equivalence --out "$RUNTIME" \
  --manifest-sha256 $RTM --end-job-commit "$X") > "$HERE/s9_equiv_drive.out" 2>&1
test -z "$(ls -A "$W/home")"
echo "rerun OK X=$X"
