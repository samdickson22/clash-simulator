#!/usr/bin/env bash
# Phase B staging for the TIERS Mac session (no timing, no measurement). r4 after Sol pre-run reviews r1-r3.
# Runs on 127x05 and drives the Mac over `ssh macmini-fleet`. All Mac filesystem mutations go through macfs.py
# (confined to $S, symlink-free path walk, exclusive mkdir, O_EXCL|O_NOFOLLOW writes, atomic renamex_np RENAME_EXCL).
# Each step builds in a fresh $S/.staging-tmp-* directory, verifies there, then promotes atomically; a final path is
# never replaced or merged into. Runs are serialized by a local flock. 05 sources are only read.
#   runtime : git archive $COMMIT + 33 uncommitted runtime-pin files + E1 native source -> $S/runtime-a5
#   helper  : stage_nocopy.py (A4 erratum E2, 166a1636) -> $S/helpers/mac-registration-e2/stage_nocopy.py
#   fixture : states.pkl + states-rows.{json,bin} (pigz -> ssh -> gunzip, SHA-verified) -> $S/inputs/fixture-a4
#   packet  : T1 sealed A5 registration packet -> $S/inputs/reference-packet-a5 (127 pinned files verified)
#   stage   : under the session lock, into a temp dir: stage_nocopy.py --e4v3 ... -- <frozen prepare_bundle args>,
#             --verify-bundle, frozen validate_bundle(dry_run=False); then promote to $S/staged-a5 (bundle at
#             $S/staged-a5/bundle-a5, receipts beside it). The session itself must re-take the lock, re-run
#             --verify-bundle, check the approved manifest SHA and build fresh (separate, reviewed command).
# Recovery: a failed step leaves only $S/.staging-tmp-* (operator-owned, safe to delete) and a per-run receipt dir.
# Usage: stage_phase_b.sh STEP...
set -euo pipefail
shopt -s inherit_errexit
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=/mpac/sdicks02/repos/clasher
COMMIT=2e2753120a768ec03d0354e47650c61c8fd34820
RUN=$(date -u +%Y%m%dT%H%M%SZ)
BASE=$REPO/reports/explore/mac-e4-session/receipts/phase-b-staging-20261012
OUT=$BASE/run-$RUN
S=/Users/sam/Desktop/code/clasher-mac-e4-tiers-20261011
PY=/Users/sam/Desktop/code/clasher/.venv/bin/python
E4V3_REL=reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3
MACREG=/mpac/sdicks02/jobs/clasher/mac-registration-20261011
PACKET=/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-release-r1/source/reports/explore/t1/private-registration-a5-20261012-r1/packet
DURABILITY=reports/explore/t1/receipts/END-A5-private-registration-durability-r1.json
STAGING05=/mpac/sdicks02/jobs/clasher/mac-e4-session-staging
OVERLAY33=$STAGING05/macE4-overlay33.tar; OVERLAY33_SHA=f0268966199bf67c9b5be1897b92bc47da5102cc6211b7670a129d59c645dea9
E1TAR=$STAGING05/macE4-e1.tar; E1TAR_SHA=d8d897589ad6821fd1bb8481efc5ad9a1dbb6db931b0dcee1066a17495373c57
SMOKE_RT=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1
MAC=(ssh -o BatchMode=yes macmini-fleet)
declare -A FIXTURE_SHA=(
  [states.pkl]=afdbd237d65897816b2683335c823fdf2557fa1640256acc892ee967368684a7
  [states-rows.json]=49cbe56ce9c3df18ae85616d09a481f5113cf7aa29bbed2c8aaca4fcb329f63d
  [states-rows.bin]=dc92bf459a337410b53cc5b2313286121542d7137b190493789126af6739b353)
declare -A FIXTURE_SRC=(
  [states.pkl]=$MACREG/assembly/states.pkl
  [states-rows.json]=$MACREG/state-rows/states-rows.json
  [states-rows.bin]=$MACREG/state-rows/states-rows.bin)
declare -A FIXTURE_DST=(
  [states.pkl]=inputs/fixture-a4/states.pkl
  [states-rows.json]=inputs/fixture-a4/state-rows/states-rows.json
  [states-rows.bin]=inputs/fixture-a4/state-rows/states-rows.bin)
mkdir -p "$BASE"
exec 9> "$BASE/.stage.lock"
flock -n 9 || { echo "another staging run holds $BASE/.stage.lock" >&2; exit 1; }
mkdir "$OUT"
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$OUT/staging.log" >&2; }
die() { log "FAIL $*"; exit 1; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
mac() { "${MAC[@]}" "$@"; }
MACFS_B64=$(base64 -w0 "$HERE/macfs.py")
MACFS_SHA=$(sha "$HERE/macfs.py")
MACFS="/usr/bin/python3 -I -c \"import base64;exec(base64.b64decode('$MACFS_B64'))\" '$S'"
macfs() { mac "$MACFS $*"; }          # args must be simple relative paths (no spaces/quotes)
state() { local st; st=$(macfs state "$1"); printf '%s' "$st"; }
need_absent() { local st; st=$(state "$1"); [[ $st == absent ]] || die "$1 is '$st' on the Mac (refusing to replace)"; }
need() { local st; st=$(state "$1"); [[ $st == "$2" ]] || die "$1 is '$st', expected $2"; }
ensure_dir() { local st; st=$(state "$1"); if [[ $st == absent ]]; then macfs mkdir "$1"; st=$(state "$1"); fi; [[ $st == dir ]] || die "$1 not a dir"; }
mktmp() { local t=".staging-tmp-$1-$RUN"; macfs mkdir "$t"; printf '%s' "$t"; }
remote_sha() { local out; out=$(mac "shasum -a 256 '$S/$1'"); printf '%s' "${out%% *}"; }

log "run $RUN commit $COMMIT macfs $MACFS_SHA"
HELPER_SHA=$(git -C "$REPO" show "$COMMIT:reports/explore/mac-registration/stage_nocopy.py" | sha256sum | cut -d' ' -f1)
[[ $HELPER_SHA == 166a1636* ]] || die "helper at $COMMIT is not 166a1636: $HELPER_SHA"
need . dir

step_runtime() {
  need_absent runtime-a5; need_absent runtime-a5-commit.txt
  [[ $(sha "$OVERLAY33") == "$OVERLAY33_SHA" && $(sha "$E1TAR") == "$E1TAR_SHA" ]] || die "overlay tar SHA"
  local t pin listing links; t=$(mktmp runtime)
  git -C "$REPO" archive --format=tar "$COMMIT" | mac "tar -x -C '$S/$t'"
  mac "tar -x -C '$S/$t'" < "$OVERLAY33"
  mac "tar -x -C '$S/$t/engine-rs'" < "$E1TAR"
  listing=$(mac "cd '$S/$t' && find . -type f ! -name '._*' -print0 | xargs -0 shasum -a 256"); printf '%s\n' "$listing" > "$OUT/mac-runtime-listing.txt"
  links=$(mac "cd '$S/$t' && find . -type l | while read l; do printf '%s\t%s\n' \"\$l\" \"\$(readlink \"\$l\")\"; done"); printf '%s\n' "$links" | sed '/^$/d' > "$OUT/mac-runtime-symlinks.txt"
  python3 -I "$REPO/reports/explore/mac-e4-session/verify_runtime_staging.py" --repo "$REPO" --commit "$COMMIT" \
    --smoke-runtime "$SMOKE_RT" --mac-listing "$OUT/mac-runtime-listing.txt" --mac-symlinks "$OUT/mac-runtime-symlinks.txt" \
    --output "$OUT/runtime-verify.json" || die "runtime verify"
  if grep -q '^94d0e7f2' "$OUT/mac-runtime-listing.txt"; then die "runtime contains 94d0e7f2"; fi
  for pin in "6066228b $E4V3_REL/measure_tiers.py" "0775b704 $E4V3_REL/fleet_validity.py" "02e2139f $E4V3_REL/tier_backend.py" \
             "3899276b $E4V3_REL/state_rows.py" "a1c59fa3 $E4V3_REL/prepare_bundle.py"; do
    grep -qF "  ./${pin#* }" <(grep "^${pin%% *}" "$OUT/mac-runtime-listing.txt") || die "pin $pin"
  done
  macfs rename "$t" runtime-a5
  printf '%s\n' "$COMMIT" | macfs write runtime-a5-commit.txt
  log "runtime OK $(python3 -c "import json;print(json.load(open('$OUT/runtime-verify.json'))['expected_manifest_sha256'])")"
}

step_helper() {
  ensure_dir helpers
  need_absent helpers/mac-registration-e2
  local t got; t=$(mktmp helper)
  git -C "$REPO" show "$COMMIT:reports/explore/mac-registration/stage_nocopy.py" | macfs write "$t/stage_nocopy.py"
  got=$(remote_sha "$t/stage_nocopy.py"); [[ $got == "$HELPER_SHA" ]] || die "helper SHA on Mac: $got"
  macfs rename "$t" helpers/mac-registration-e2
  log "helper OK $HELPER_SHA"
}

step_fixture() {
  local name src dst got t st
  ensure_dir inputs; ensure_dir inputs/fixture-a4; ensure_dir inputs/fixture-a4/state-rows
  for name in states-rows.json states.pkl states-rows.bin; do
    src=${FIXTURE_SRC[$name]}; dst=${FIXTURE_DST[$name]}
    st=$(state "$dst")
    if [[ $st == file ]]; then
      got=$(remote_sha "$dst"); [[ $got == "${FIXTURE_SHA[$name]}" ]] || die "$dst exists with SHA $got"
      log "fixture $name already present OK"; continue
    fi
    [[ $st == absent ]] || die "$dst is '$st'"
    [[ $(sha "$src") == "${FIXTURE_SHA[$name]}" ]] || die "05 source SHA $name"
    t=$(mktmp "fixture-${name%%.*}")
    log "fixture $name transfer start ($(stat -c %s "$src") B)"
    nice -n 19 pigz -p 4 -c "$src" | mac "gunzip -c | $MACFS write $t/$name"
    got=$(remote_sha "$t/$name"); [[ $got == "${FIXTURE_SHA[$name]}" ]] || die "Mac SHA $name: $got (temp $t kept)"
    mac "chmod a-w '$S/$t/$name'"
    macfs rename "$t/$name" "$dst"
    mac "rmdir '$S/$t'"
    log "fixture $name OK"
  done
}

step_packet() {
  ensure_dir inputs
  need_absent inputs/reference-packet-a5
  local t listing links; t=$(mktmp packet)
  tar -C "$PACKET" -cf - . | mac "tar -x -C '$S/$t'"
  listing=$(mac "cd '$S/$t' && find . -type f ! -name '._*' -print0 | xargs -0 shasum -a 256"); printf '%s\n' "$listing" > "$OUT/mac-packet-listing.txt"
  git -C "$REPO" show "origin/main:$DURABILITY" > "$OUT/durability.json"
  python3 -I - "$OUT/durability.json" "$OUT/mac-packet-listing.txt" > "$OUT/packet-verify.json" <<'EOF' || die "packet verify"
import json, sys
pins = json.load(open(sys.argv[1]))["private_files"]
prefix = "reports/explore/t1/private-registration-a5-20261012-r1/packet/"
want = {k[len(prefix):]: v["sha256"] for k, v in pins.items() if k.startswith(prefix)}
have = {}
for line in open(sys.argv[2]):
    if not line.strip(): continue
    digest, path = line.rstrip("\n").split("  ", 1)
    path = path[2:] if path.startswith("./") else path
    if path in have: raise SystemExit("duplicate " + path)
    have[path] = digest
bad = sorted(k for k in set(want) | set(have) if want.get(k) != have.get(k))
print(json.dumps(dict(files=len(want), mismatched_or_extra=bad, passes=bool(want) and not bad), indent=1))
sys.exit(1 if bad or not want else 0)
EOF
  links=$(mac "find '$S/$t' -type l -print")
  [[ -z $links ]] || die "symlink inside packet copy: $links"
  mac "chmod -R a-w '$S/$t'"
  macfs rename "$t" inputs/reference-packet-a5
  log "packet OK $(grep -c . "$OUT/mac-packet-listing.txt") files"
}

step_stage() {
  local e4v3=$S/runtime-a5/$E4V3_REL p t st receipts
  need_absent staged-a5; need_absent build-a5
  for p in runtime-a5 helpers/mac-registration-e2/stage_nocopy.py inputs/fixture-a4/states.pkl \
           inputs/fixture-a4/state-rows/states-rows.json inputs/fixture-a4/state-rows/states-rows.bin \
           inputs/reference-packet-a5/registration.json inputs/topology.json inputs/load-config.json session.lock; do
    st=$(state "$p"); [[ $st != absent ]] || die "missing $p"
  done
  t=$(mktmp stage)
  mac "cd '$S' && PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 '$PY' -B -" > "$OUT/stage-stdout.txt" <<EOF || die "stage (see stage-stdout.txt; temp $t kept)"
import fcntl, subprocess, sys
lock = open("$S/session.lock", "r+")
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
bundle = "$S/$t/bundle-a5"
subprocess.run([sys.executable, "-B", "$S/helpers/mac-registration-e2/stage_nocopy.py", "--e4v3", "$e4v3", "--",
    "--runtime-root", "$S/runtime-a5", "--native", "$S/build-a5/clasher_core.cpython-312-darwin.so",
    "--states", "$S/inputs/fixture-a4/states.pkl", "--state-rows", "$S/inputs/fixture-a4/state-rows",
    "--reference-packet", "$S/inputs/reference-packet-a5",
    "--student", "$S/inputs/artifacts/R3a.pt", "--calibration", "$S/inputs/artifacts/R3a-calibration.json",
    "--v1", "$S/inputs/artifacts/v1.pt", "--load-config", "$S/inputs/load-config.json",
    "--topology", "$S/inputs/topology.json", "--output", bundle], check=True)
subprocess.run([sys.executable, "-B", "$S/helpers/mac-registration-e2/stage_nocopy.py", "--verify-bundle", bundle], check=True)
sys.path.insert(0, "$e4v3")
from tier_backend import validate_bundle
manifest = validate_bundle(bundle, "$S/runtime-a5", dry_run=False)
print('{"validate_bundle": "PASS", "profile": "%s"}' % manifest["profile"])
EOF
  macfs rename "$t" staged-a5
  receipts=$(mac "cd '$S/staged-a5' && cat bundle-a5.nocopy-receipt.json && cat bundle-a5/tiers-pins.sha256 && cat bundle-a5.nocopy-verify-*.json")
  printf '%s\n' "$receipts" > "$OUT/staging-receipts.txt"
  log "stage OK tiers-pins $(mac "cut -d' ' -f1 '$S/staged-a5/bundle-a5/tiers-pins.sha256'")"
}

for step in "$@"; do log "step $step begin"; "step_$step"; log "step $step end"; done
