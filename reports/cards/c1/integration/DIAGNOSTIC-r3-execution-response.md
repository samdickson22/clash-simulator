# Actual c077 diagnostic FAIL and next scoped repair

R3 approved exactc077fe05cdb64466991f8f145a61abc0f2d91ff2 and525 inputs.
Its one-job recovery ran once, retaining the old prebuild FAIL and all original
modes/log/source. Recovered terminal SHA23101e281b8e1bc54f7320688aba0460af7c77a0d7d5c10a535349b382924ab0.
Actual subsequent job08/c1diag-20261016T154733Z-r2 ran PID/PGID539594,
buildchild540091 and sharedchild608754. Fresh offline Cargo1.97.1 -j4 build
passed in37.32s, yielding nativef42a84b3a8f7c61ca037ba9ee185a73206de5db481ec1b375ac5f8ac2ec07dce.
It is historical diagnostic evidence only, never a borrowed next-candidate binary.

The shared probe completed32/32 rows with all required witnesses observed:
22 rows reported FOCUSED_PASS; all10 Zap rows reported FOCUSED_FAIL. The phase
also independently failed source provenance. The worker retained its actual
module-after inventory and both semantic/provenance failures. Driver stopped
before the seven remaining phases, retained actual child exits0/1 and wrote
DIAGNOSTIC_FAIL/cleanup_complete=true at15:53:10.197884Z. Those seven phases are
NOT_RUN. Known wrapper/build/shared process groups and wrapper lease are absent
on final read-only receipt. This does not grant any accepted PASS coverage.

Exact raw outputs/controls/cache copies remain read-only outsideGit in
jobs/cards/c1/local-evidence/c1diag-20261016T154733Z-r2. SHA/path/size bindings,
final liveness and source inventory are in diagnostic-r2-execution-evidence.json.
Shared raw JSON179MiB SHA7431f33c29e57c80820987a518d9b211a6fb6d5340e38318328ca242ed2746b1.
Small field-only extracts are diagnostic-r2-shared-triage.json and
diagnostic-r2-zap-clock-witness.json; original full configs remain outsideGit.
The local nice15 JSON extraction took1.764s, no engine/simulation; all host
observations were standard read-only ps/stat/find/sha256sum/scp commands.

## Cache failure: retain strict source equality

All525 expected source/tool hashes remained exact. Numba's existing
`battle.py` njit(cache=True) added only two new files under source/__pycache__:
`battle._build_blocked_mask_numba-81.py312.nbi` SHA9a5525f39dedf77d1d20266ea767c64410cee60107f81c27de8e85f8bcde6a98 and
`.py312.1.nbc` SHA8e7f84d4d61401fdfe4b7429cf78c3230a945d364ff1d3653e1df2f66fe6c503.
PYTHONDONTWRITEBYTECODE does not prevent Numba caches. Source equality correctly
failed; the observed row-level PASSs cannot override it. No cache ignore/filter
is added. The proposed reviewed procedure creates another fresh private0700
job/numba-cache, requires it empty, passes its exact NUMBA_CACHE_DIR in the clean
child environment, records that environment before build and generated cache
hashes after phases. Existing source validation remains unchanged and still
rejects a simulated .nbc under src. No shared/global/older compiled cache is read.

## Confirmed forced-state cold Dash clock mismatch

The route/finalizer witnesses passed before the first semantic mismatch. In
both seats, ordinary variants first differ at offset10/tick30→31, external at
offset8/tick28→29, after the successful Dash hit/landing. Actor7 statsAssassin
has interval1000/load600 and clock_initialized=false. Both poses/HP/digest and
cooldown1.0 agree. Python exports clock.remaining600 and clock_reseed=null;
native exports remaining0 and reseed1000. All three native arms reproduce it.
Ordinary variants differ at one offset; external at two; observed later frames
converge. This is a retained full-state mismatch on constructed cold roots,
not evidence that normal gameplay reaches them or that damage/timing changed.

Bounded Astra-high source diagnostic is preserved in DASH-CLOCK-DIAGNOSTIC.md.
Adopt its small supported change: only a successful ordinary Dash hit with an
uninitialized clock projects the newly written full interval as timeline0,
remainingload, no pending seed and force_due=false. Keep initializationfalse,
finish/refund and unrelated state. Do not call consume_clock_reseed (which
initializes and has stop/refund/finish effects). Initialized actors keep their
old projection comparison/deferred seed unchanged. Lost target, no-hit arrival
and nonordinary cases retain existing behavior. No new schema or snapshot/
comparator normalization. Python/exporter and all original probes are unchanged.

Whole-class writer audit found Leap's similar full-interval write and Hook's
materially different interruption/max-deadline/preload logic. Neither is a
captured failure. Their source stays unchanged; do not generalize this Dash
projection repair or claim their cold states pass. Existing MegaKnight terrain
and focused coverage remain required; future actual failures drive fixes.

## New bounded controls and required execution

Add dash-clock12 (six modes×both seats) using legal deployment/warm-up followed
by explicit current-schema state. Modes: cold zero deadline (stale due flag),
cold already-full deadline, loaded differing/equal projection, frozen goal
arrival without hit and missing target termination. The first factory draft
used final diagnostic coordinates for deployment; source inspection corrected
it to unchanged legal setup coordinates before any execution. The near-own-bank
forced positions keep positive targets beyond tower range and avoid river
recovery, allowing40 ticks through landing, first ordinary initialization and
a subsequent ordinary hit. These placement/timing expectations are still
UNRUN and must be established by the real probe, not its local mocks.

The phase compares every frame using unchanged frozen semantic-v1, fresh Troop
template proof, Python clone and fresh native clone/reload at every pre-step
boundary. It retains initial/last-before/first-bad/landing paired roots, exact
clock/init/seed/finish/force/cooldown state and target HP. Hit witnesses require
actual configured Dash damage at landing and later ordinary damage; loaded
clock work stays unchanged with the expected pending/no-pending write; cold
stays uninitialized until legitimate ordinary work. Miss/missing controls must
not install the hit deadline or damage a recipient. No partial/error row counts
as a witness. New worker phase requires exactly12 distinct complete cases and
the exact native hash. Local AST negatives reject the captured old split,
eager initialization, finish/seed/due drift, invalid landing/completion and no
ordinary resume. This is contract validation, not actual parity.

Fresh full source/probe/procedure independent review must bind all506 engine
files plus20 extras526 inputs and the changed Dash line before any new host
execution. One new source-bound build then nine serial phases32/12/21/8/2/42/
6/2/4, no oldnative reuse/competing sweep. Both previous runs are terminal;
reviewed admission must freshly verify all known groups/leases before launch.
No additional recovery is requested or authorized by the next approval.
All previous D1–D3 repairs, exact0700/cleanup safety and after-import retention
remain. Five local suites PASS (stdlib/AST/mocks only); bindings in local-r4 JSON.
No new engine/native/compiler/host repair execution has occurred. Actual new
parity, broader generic-child/Spirit/fidelity/public coverage and eventual
reconciled-main full C56 remain pending. No main/pin/runtime promotion.

Rollback only new isolated commits, keeping frozen9fa, original11ff/C1 approvals,
old2ac/631ac/f42 natives, both failed jobs, all raw roots and source/provenance
FAILs intact. The whole diagnostic assignment remains OPEN until actual evidence
and reviewed repairs complete or a concrete parent-dependent blocker occurs.
