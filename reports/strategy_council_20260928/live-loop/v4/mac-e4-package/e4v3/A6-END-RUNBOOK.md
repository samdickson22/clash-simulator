# A6 END-phase handoff (review draft; no host access yet)

Coordinator assignment: **127x01** at T1 END before production references.
The actual19:45Z ruling supersedes the earlier 02–06Z projection: expect Oct11,
after perception serial and A2 finish, around B. The coordinator will explicitly
declare the clean window. The 04→03/08 transports must be gone and08's HTTP cache
service retired. Reference validity stays STRICT: SSH or dbus flags do not
qualify merely because OP-6 allows reporting to continue. T1 will provide the
reviewed own-tier300 bundle path/`tiers-pins.json` SHA, pinned
launcher, Python/runtime/native locations and final frozen guard/admission artifacts. The
projection is not permission to connect before the coordinator opens the window. Nothing in
this package polls, accesses, launches or reserves a timing host meanwhile.

Order: A6 staging and real smoke → sealed result committed → independent A1–A6
review of code plus result → coordinator confirmation → production host
references → pool/registration. No production reference may run before that
review. T1 owns reporting, the END completion/phase inventory, the window and
all outcome-release routes. E4 prepares and measures replay fixtures only.

`prepare_fleet_smoke.py` takes the approved **127x01 END bundle**. It verifies
the source manifest and every copied input SHA, current measurement-code pins,
the separate golden125, four own-tier300 sets, committed END evidence and nice10.
It writes an exclusive SHA-sealed staging directory with `bundle/` and a new
manifest. Original files, corpus IDs, frozen models, guard admissions and
runtime pins stay unchanged. It never unpickles fixtures, starts a backend,
opens a network connection or measures anything.

The smoke has a different plan SHA, `profile=e4v3-unpoolable-smoke` and
`kind=unpoolable-smoke`. It keeps the approved 127x01 slot layout and >=300s
warmup. Its synthetic reporting join uses the already pinned **full-occupancy
reporting clock numbers**, with source UTC/phase labels retained. This baseline
is fixed before measurement; a >5% failure is retained rather than rewritten
using smoke clocks. The production pool refuses this bundle and receipt.

After T1 supplies actual paths and the coordinator declares the clean window, run staging through T1's
approved mechanism; these variables must contain T1's supplied values:

```bash
"$E4_PINNED_PYTHON" -B "$E4_PACKAGE/prepare_fleet_smoke.py" \
  --source-bundle "$E4_T1_END_BUNDLE" \
  --source-manifest-sha256 "$E4_T1_END_MANIFEST_SHA" \
  --output "$E4_A6_NEW_STAGING_DIRECTORY"
```

Return `staging.json`, the staging receipt seal, and the new
`bundle/tiers-pins.json` SHA for the run binding. Verify runtime/native and guard
source/admission pins on the assigned host before using the bundle. Include
every dependency of the **reviewed reporting guard** in its pinned source tree;
unfinished shared-checkout guard changes are not qualified inputs. A6 uses the
same real `measure_tiers.py --fleet-reference`, `TierBackend`, spawned background
slots, full warmup, telemetry, strict exactness, deadline loops and sealing:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  nice -n 10 "$E4_PINNED_PYTHON" -B "$E4_PACKAGE/measure_tiers.py" \
  --fleet-reference \
  --bundle "$E4_A6_NEW_STAGING_DIRECTORY/bundle" \
  --manifest-sha256 "$E4_A6_STAGED_MANIFEST_SHA" \
  --runtime-root "$E4_T1_RUNTIME" \
  --native "$E4_T1_NATIVE" \
  --output "$E4_A6_NEW_MEASUREMENT_DIRECTORY"
```

Place the command inside **T1's supplied detached launcher**, with its approved
physical supervisor core. The launching SSH must close before admission. Use
only T1's approved health-only copier for observation; ordinary SSH inspections
during timing violate the guard. No launcher or copier is invented here.
Fresh output paths preserve earlier attempts; no launch or repeat is automatic.

On failure, preserve the full sealed result and use the committed classifier:

```bash
"$E4_PINNED_PYTHON" -B "$E4_PACKAGE/classify_failure.py" \
  --fleet-reference --receipts "$E4_A6_NEW_MEASUREMENT_DIRECTORY" \
  --output "$E4_A6_NEW_CLASSIFICATION_DIRECTORY"
```

Classification supplies evidence only. Exactness is never repeatable. A fresh
technical repeat still needs coordinator/T1 scheduling and retains the first
attempt; a second failure remains fail-closed. A passing smoke has
`fleet-complete.poolable=false` and EXACT native/belief checks. Commit the full
SHA-sealed result with explicit paths, scan before push, and return its commit
and manifest SHA for independent review. A6 does not qualify the production
clock profile, fleet ratios, Mac or outcomes by itself.

Current evidence: 69 local unit/integration tests; no A6 measurement exists.
The END source now also requires SHA-bound committed blind ledger and counted
inventory, accepting stopped phases verbatim. Stage all nine final frozen guard
modules, including OP-5 seed/08 join and OP-6 dependencies; older guard regimes
are refused. Pin `guard.seed_inputs` for both source receipts and the 08
server/client join, and keep `guard.job/FROZEN-T1.json` identical to the staged
freeze. The frozen seed method executes once before first census; its raw
admission receipt is retained. Do not refresh parent generations or source proof.
The smoke preserves original production sources and discloses its separate
synthetic, unpoolable host01 counting inventory. Inspect sample and work-block
SSH budgets and any console stops with the A6 result before reference approval.
The existing Linux05 receipts are separate reduced-count smoke evidence.
