# T6/T7 fleet runbook

## Shared-host storage ownership, 2026-10-08 15:19 UTC

Coordinator ownership notice, **2026-10-08 15:19 UTC**: roader is rebuilding
its backups on 09/15 (approximately 30 GB per host), with temporary LAN/disk I/O
contention and then idle storage. This is coordinator-reported context, not an
inspection of roader data. **Never read, write, traverse or delete**
`/mpac/sdicks02/repos/roader-mirror*`, `roader-code-127x05-mirror`, or
`roader-mirror-trash`. V4 files on leased hosts stay under the exact
`/mpac/sdicks02/repos/clasher-lease/` footprint. Any future approved cache cleanup
must use explicit, validated per-match paths within its `data/v4-cache/` root;
no repository-parent cleanup glob, symlink traversal or roader path access.
09/15 caps and existing storage reservations remain unchanged. Keep current
transfer concurrency; account for contention in completion estimates rather than
launching duplicate copies. No jobs, Phase A polls or cleanup launched for this
notice; it does not approve the pending duplicate-cache retirement proposal.

## Current GPU assignment and lease exit, 2026-10-08 15:14 UTC

This section supersedes the historical home01 launch templates and GPU-only09/15
caps below. **01 GPU is reserved for T5; 11 is offline. T7 runs on09, T6 on15.**
09/15 have verified CPU+GPU qualification, 96-process leases (16 with console),
64 GB PSS limit and ≥8 GiB GPU reserve. Actual launch still requires live checks
and authentic Phase A completion/full preparation. 04/08 only after T5 releases.

Launch formal T6 through the leased wrapper and lifecycle supervisor, using
actual authenticated producer receipts and fresh paths:

```bash
source /mpac/sdicks02/repos/clasher-lease/env.sh
bash "$CLASHER_LEASE_ROOT/run.sh" t6-formal-UNIQUE \
  "$CLASHER_LEASE_ROOT/envs/clasher-gpu/bin/python" -B \
  "$CLASHER_ROOT/reports/strategy_council_20260928/live-loop/v4/l1/lease_lifecycle_v4.py" \
  --arm t6 --phase-state REAL_T1_STATE --phase-exit REAL_T1_EXIT \
  --output "$CLASHER_LEASE_ROOT/data/t6-formal-UNIQUE" \
  --journal "$CLASHER_LEASE_ROOT/jobs/t6-formal-UNIQUE-backups" --backup-host 127x01
```

T7's full-union admission/trainer/replay path is implemented and covered by
synthetic rejection/provenance tests. Pass **--cache-union RUNTIME_JSON** to the
lifecycle supervisor: schema `clasher.v4.formal-union.v1`, exact saved-admission
SHA, every authenticated train/validation receipt SHA, and disjoint local/remote
shards with pinned inventories/manifests. Never pass09's local71-match cache as
the full population. Runtime connections/private tokens stay off05; stable index
snapshots live in model/cache-indices and are checkpoint-backed. Remote services
must remain alive for the bounded job and be re-established for later replay
batches; their current maximum lifetime is one hour. Actual full-union fitting,
connection setup and final-population preparation still pending.09/15 now have559
pinned source sets;09 retains71 verified cache shards,01 retains349,03 extension
139 fully verified (559 total,10,085 exact checks,zero mismatches). Refresh on genuine T1 completion.

T6 cache storage: formal wrapper passes --pixel-cache-directory under the approved
lease data/v4-cache/t6-RUN root. Exclusive cache lock,4096 MiB maximum growth plus
2 GB reserve and fresh-directory check apply before fitting. Historical default
path, sampling and training behavior are unchanged.

Lifecycle: immutable SHA-verified checkpoint snapshots to01 every30 minutes and
on exit (04 optionally); start stopping at **2026-10-09 04:30 UTC**, exit before
**05:00**, lease expires05:30. Failed transfer stops the run; no deletion of failed
snapshots. T7 checkpoint includes optimizer/RNG; unchanged T6 saves epoch weights
only and needs a fresh fit after interruption. 14 lifecycle checks and a real
synthetic15→01 transfer passed. No real formal checkpoint exists yet.

**Current reservations:**01=291,18=293,16=215,03=120,09=60,15=10 GB, total989 GB.
03 operating cap118 GB;16 helper215 GB still reserves2 GB per allocation. Preserve
≥200 GB free. Retiring the duplicate18 base is a documented proposal awaiting
explicit approval; no copy may be deleted merely because this plan names it.

Home-host commands run from `/mpac/sdicks02/repos/clasher` on **127x01**. Use only
`/mpac/sdicks02/envs/clasher-gpu/bin/python`; eager CUDA, no compile. Check `~/.local/bin/fleet-console-users`,
Python worker count and `nvidia-smi` before each launch: total <=96 (<=16 with
console user), leave >=12GiB GPU headroom. `fleet_run.sh` applies nice 10 and
thread limits. Use distinct labels; inspect `.exit`, not just launch acceptance.
Only copy owned source paths with `rsync -cR`; never sync the whole checkout.

Formal commands are PREPARED, not running or automatically scheduled. T1 has not
provided Phase A completion. Do not create completion receipts yourself. Once its
authentic `pipeline-state.json` (`stage=complete`) and `phase-a-exit.json`
(`code=0`) are mirrored, run the following sequentially through the fleet helper
(substitute real receipt paths and a fresh output path):

```bash
bash reports/strategy_council_20260928/fleet/fleet_run.sh t6-formal-UNIQUE \
  bash reports/strategy_council_20260928/live-loop/v4/l1/formal_train.sh \
  t6 /path/from/T1/pipeline-state.json /path/from/T1/phase-a-exit.json \
  /mpac/sdicks02/repos/clasher-v4-training/t6-formal-UNIQUE

bash reports/strategy_council_20260928/fleet/fleet_run.sh t7-formal-UNIQUE \
  bash reports/strategy_council_20260928/live-loop/v4/l1/formal_train.sh \
  t7 /path/from/T1/pipeline-state.json /path/from/T1/phase-a-exit.json \
  /mpac/sdicks02/repos/clasher-v4-training/t7-formal-UNIQUE \
  /mpac/sdicks02/repos/clasher-v4-cache
```

T6: 24x400 steps, seed 6107, unchanged v2 warm start, 3-positive/1-negative
sampling, losses, LR and clip, fp32 control. Only CUDA plumbing and an explicit
4096MiB cache disk allowance differ operationally. All converter payloads remain
retained. The adapter supplies only missing evaluator layout/protocol-2 metadata.
T7: 24x400 steps, seed 6108, fresh random weights, bf16, batch one T16 window,
AdamW 0.0003, six ordered CPU preparation threads, no worker subprocesses. Epoch checkpoints and optimizer/RNG state
are written. Training populations are snapshotted before decoding.

Resume T7 with identical arguments and `--resume` through a new fleet label,
after verifying the old PID has exited. Source/options must match its manifest.
It resumes from the last eight-step checkpoint; inspect the training JSONL for
an uncheckpointed tail before aggregating metrics. T6's unchanged trainer is not
optimizer-resumable: preserve partial output, use a fresh run directory and
replay the deterministic fit. Complete stages are reused by run_t6_shake.py;
partial stages deliberately refuse overwrite. Conversion resumes complete
per-match roundtrip outputs and refuses to overwrite partial matches.

No heldout scoring entry point is enabled by these commands. Formal model
selection/calibration must finish on validation and be sealed. The full v4
heldout evaluator and T5/T8 integration/Mac replay remain follow-on work; all
§5.1 endpoints are registered, but this implementation shakedown does not certify
them. T6 validation is available through the unchanged evaluator. Gap diagnostic:

```bash
bash reports/strategy_council_20260928/fleet/fleet_run.sh t6-gap-UNIQUE \
 /mpac/sdicks02/envs/clasher-gpu/bin/python \
 reports/strategy_council_20260928/live-loop/v4/l1/gap_t6.py \
 --dataset /path/to/t6/dataset --run /path/to/t6/run \
 --l2 reports/strategy_council_20260928/live-loop/l2/native \
 --output /mpac/sdicks02/repos/clasher-v4-training/t6-gap-UNIQUE
```

Retain all source/data/weights on 01; mirror only code, docs, JSON receipts and
logs to 05. No media or model files to 05. The 40 GB frozen acquisition cap applies
to hub raw collection. Coordinator approval (2026-10-08 07:22 UTC, COORDINATOR.md)
permits a separate 300 GB derived-cache budget per allowed host, with >=200 GB
free on /mpac. Subsequent user approval sets a 1 TB aggregate cache ceiling;
current reservations are 300 GB each for 01/18, 230 GB for 16 and 150 GB for 03,
total 980 GB (14:15 UTC reassignment of 70 GB from idle 16 cache allowance to 03). The remaining
20 GB covers retained T6/shakedown caches. Reassign within the aggregate cap
before admitting another cache host. See STORAGE-AMENDMENT-20261008.md.
Approved cache roots are `clasher-v4-cache/` on home hosts and
`clasher-lease/data/v4-cache/` on leased CPU/GPU hosts; no new cache in the
acquisition tree. Leased caches must move off or be deleted within one day of
lease end (currently by 2026-10-10 05:30 UTC). Preserve evidence by moving it.
Stop on space pressure. Export plan: EXPORT.md.

## Predecoded cache and labels, 2026-10-08

Read LABEL-AUDIT.md and prospective PREREG-AMENDMENT-03.md. Do not edit the
original PREREG, split, collector, or producer payloads. `labels_v4.py` is the
single downstream cleaner for every split, including later authorized heldout.
The uncached T7 reference now decodes exact sequential frame ordinals: OpenCV
frame-number seek was measured one frame early on this VFR source.

`stage_training.py` admits train/validation receipts against the frozen split,
then copies exactly their allowlisted files directly from 01. It never copies
heldout media/labels. `--heldout-receipts-only` additionally stages byte-identical
receipt JSON for formal count admission. Formal leased runs require
`stage-inventory.json` with `complete_population=true`; partial/pilot inventories
are refused. Do not set a match limit/partition for the final full staging pass.

`build_cache.py --source SOURCE --split SPLIT --cache CACHE --workers N
--budget-gb GB --receipt FRESH_JSON` writes lossless raw and model-resolution BGR
blocks plus per-match indices/SHA256 and independent random 1% equality receipts.
It refuses heldout, verifies source hashes, keeps incomplete attempts, commits
each completed match atomically and verifies completed matches on restart.
Frame-weighted per-match allocations bound concurrent growth, including retained
partial attempts, with metadata/free-space reserves. Default build budget is
280 GB, below the approved 300 GB ceiling. A cache-root writer lock prevents
concurrent builders/copies. SIGTERM/SIGUSR1 stops new submissions and finishes
only current match commits, then exits 75; resume with a fresh job/receipt label.

The original successful five-match pilot was under
`127x16,127x18:/mpac/sdicks02/repos/clasher-lease/cache/v4-pixels-r2/`.
18 has all five matches; 16 has four. The five-match pilot was also copied to
`127x01:/mpac/sdicks02/repos/clasher-v4-data/cache/` at 07:01 UTC after `who`
cleared and the runbook's worker-cap check passed. Ten payload SHA256s and all
five indices were verified on 01. Copy only complete directories, checksum every
file against each index on the destination, and retain the equality receipt.
Mirror only compact receipts/source/docs to 05.

The cache is **5,910,676,788 bytes for 14,592 frames**, including raw pixels needed
for identical JPEG-before-resize augmentation. At that measured density, even
the 240,291-frame audited population needs about 97 GB for one complete cache.
The derived-cache increase is now approved; frozen acquisition accounting is
unchanged. `cache_batch.sh migrate LABEL` moves these historical roots into the
approved locations without deleting data. On leased 18, the failed pilot moves
into `data/v4-cache/retained-legacy-failed/` and counts against its budget.
`cache_batch.sh build LABEL PARTITION PARTITIONS WORKERS [BUDGET_GB]` stages only admitted
train/validation files, reuses checksum-verified pilot matches, and decodes its
disjoint seed partition. Run through the appropriate fleet/lease wrapper.
The optional build budget defaults to 280 GB; 18 used 295 GB for its 10:59
extension, inside the existing 300 GB approved ceiling. Budget validation, the
2 GB allocation reserve and 200 GB free-space floor remain enforced. Never
raise the host or aggregate ceiling to accommodate more replicas.
Initial plan: partitions 0/2 and 1/2 on 16/18 with 24 workers each. Host 18 stages
all train/validation payloads for subsequent T7; 16 stages its media partition.
`sync_pixel_cache.py` imports only completed matches through unique temporary
directories, verifies SHA256/equality evidence, then atomically publishes them.
It checks host budget/free space before each import and retains interrupted copies.
Never substitute a cache subset for the formal population or discard originals.

11:32 storage continuation: the full 349-match replicas occupy 289.44 GB on 01
and 291.83 GB on 18. Further full copies cannot grow past the approved host cap.
On 16, invoke `cache_unique_batch.sh LABEL VERIFIED_BASE_MANIFEST BASE_INVENTORY`
through the lease wrapper. The script stages only train/validation, pins the
verified manifest to the base inventory, refuses changed/missing base receipts,
and uses `build_cache.py --inventory EXTENSION_PLAN` for new episodes only.
Existing local completed matches in that extension are checksum-reused. The
build retains the 280 GB allowance, writer lock, independent 1% equality checks
and all partial evidence. Final manifest verifies this extension only, not a
complete local training population. Seventeen synthetic planner checks passed
(child exit 0, wrapper stopped on the known descendant-exit race).

Do not run `cache_batch.sh` or another writer concurrently with this script.
Keep original 01/18 replicas and source receipts. Reservations remain 900 GB
on 01/16/18; no fourth writer is enabled. A full cache union, a reader that can
access its remote shards and measured sample/throughput parity remain required
before formal fitting. No existing formal command automatically uses this union.
Never substitute the local subset for the complete formal population.

`cache_transport_v4.py` is a prepared read-only block server/client, not yet used
by training. Server arguments: `--source --cache --split --inventory --manifest
--token-file --ready [--port]`; run only under the fleet/lease wrapper with all
files in its owned footprint. The token file must be private (no group/other
permissions). Do not print or mirror tokens. It authenticates the pinned subset,
verifies full payload SHA/equality, holds a shared cache writer lock and listens
only on IPv4 loopback. Clients must use an SSH loopback tunnel owned by their
wrapper process tree, never a public listener or independent background tunnel.
Stop the server through its verified owned PID when testing ends; lease reclaim
also terminates the supervised service. A server occupies the host's workload
lock, so it cannot run concurrently with a builder there.

`RemotePixelCache` pins remote indices and validates receipt identity/ABI/equality;
only fixed indexed raw/model blocks can be requested. Bytes are decoded in RAM,
with no disk replica. Sixteen synthetic loopback exactness/refusal tests pass on
18. Real cross-host transport, source-equality parity, multi-shard training access,
throughput, resume/reclaim integration and formal admission remain untested.
No existing formal command uses this transport automatically. The 25-match unique
extension needed a verification-only repair because `cache_manifest.py` was not
initially deployed to 16; deploy the complete script dependencies, and preserve
that failed exit alongside the successful final manifest.

Use the live leased-host run.sh/env.sh from fleet/LEASED-HOSTS.md, never the home
fleet_run.sh on a borrowed host. Check leases/caps/GPU/RSS before every launch.
The lease wrapper holds a **host-wide workload lock**: run one workload per
leased host even when its process cap would allow more. Wait for its final exit
receipt before launching another wrapper job. Never bypass that lock.
`formal_train.sh` now accepts the allowed leased GPU hosts with these arguments:
`ARM PHASE_STATE PHASE_EXIT FRESH_OUTPUT [PIXEL_CACHE] [PRECONVERTED_T6_DATASET]`.
Leased source is `clasher-lease/data/v4-matches`; executable and all outputs stay
inside the footprint. GPU-only 09/15 require a complete preconverted T6 corpus
from an authorized CPU host; the wrapper verifies its full training population.
The lease wrapper remains responsible for reclaim, expiry and process/RSS caps.
T7 now saves and exits on SIGTERM; it passed a stop at step 24 and an identical-
configuration resume through step 128 with no missing/duplicate steps.

The formal guard verifies amendment 03 as well as the earlier registration. An
authentic cap-complete producer may admit training with a **FAIL coverage gate**;
this is not permission to collect more data or pass any heldout endpoint.
Fresh formal training, validation selection/calibration, the full v4 evaluation
driver and selection seal are still pending. No prepared command opens heldout.

## Scorer preparation

Scorer preparation is in `scoring_v4.py`, with synthetic regressions in
`test_scoring_v4.py` (135 checks, 16 lease wrapper PASS, 2026-10-08 07:20 UTC).
It has no dataset I/O or heldout entry point. Prediction timestamps must be
actual completion on the same production clock as explicitly mapped truth;
never feed backdated execution estimates as availability. It computes maximum
cardinality then minimum latency assignment within 500ms and separately supports
the historical conservative bracket sensitivity. Champion abilities are separate;
duplicates are false positives; unmatched truth remains in placement denominators.
Provide the complete admitted episode list, including empty matches, for paired
10,000-resample seed-6110 cluster bootstrap. An undefined denominator leaves its
interval null. Threshold selection requires all nine registered grid points;
epoch selection requires all 24 formal epochs. These primitives do not establish
input provenance, calibrate models, create a selection seal, or certify gates.
The guarded replay/selection driver remains to be connected and tested.

`selection_guard_v4.py` checks full T7 fit evidence before replay: registered
24x400/seed-6108 options, the frozen split, exact admitted training receipt set,
cache/source/vocabulary provenance, all 9,600 finite-loss steps in order and all
24 epoch checkpoint metadata. The caller must independently authenticate admission
and recompute checkpoint/source hashes; this pure helper has no I/O, does not
authenticate caller declarations, and never authorizes heldout or seals selection.
Do not substitute pilot weights or manually assembled metadata for formal output.
Synthetic rejection checks passed 23 cases on 16 (child exit 0, wrapper `stopped`
on its descendant-exit race; retained as such, not a clean wrapper PASS).

`validation_admission_v4.py` connects this guard to actual formal run files.
After authentic Phase A completion and formal T7 fitting, run through the fleet
or lease wrapper with `--run FORMAL_OUTPUT --source MATCH_ROOT --split SPLIT
--phase-state T1_STATE --phase-exit T1_EXIT --output FRESH_READINESS_JSON`.
It re-runs `formal_guard.admit` first, requires the saved admission to match,
checks source snapshots/current source bytes and cache indices, verifies the
last checkpoint hash, and loads all 24 epoch checkpoint metadata using
`torch.load(weights_only=True, map_location='cpu')`. The returned validation
receipt population is full and fixed. Relocated/changed source paths or receipts
must not be silently accepted. This command opens no heldout payload, selects
no model, and creates no selection seal. Validation pixels/labels and exact timing
still require guarded replay. Seven synthetic file-integrity checks passed on 16
at 09:01 UTC with clean wrapper PASS; tiny fixture weights remain on 16 only.

`validation_replay_v4.py` accepts the same six paths as validation admission,
plus `--epoch 1..24 --threshold 0.1..0.9`. Run only after real formal fitting,
through the wrapper, into a fresh output directory. It authenticates admission
first, verifies the entire validation cache, and streams all original frames in
fp32 CUDA through PixelPerception. It reads no native labels for inference.
The per-episode `*-completion.jsonl` is the authoritative availability clock:
each duration includes cache loading, model/fusion work, JSON writing and flush;
FIFO backlog is carried across frames. Ignore the payload's inner compute-only
availability when scoring. Cache blocks load once, with cost charged to their
first frame. This is a fleet diagnostic, not Mac latency certification.
Nineteen synthetic timing/order/refusal checks passed (child exit 0; wrapper
descendant-exit race recorded as stopped). The full GPU command is not yet run.
Truth timing mapping, scoring adapter, per-card/body selection, calibrated replay
and the selection seal remain pending; this command supplies none of those.

The pure `completed_predictions` adapter now joins payloads to their completion
journal for the scorer ABI. Require the complete admitted frame count, authenticate
both files first, and pass the replay's actual calibration map. Only an empty map
is accepted for raw-score calibration input. Missing/reordered frames, episode or
clock mismatches, nonfinite values and an invalid FIFO recurrence fail closed.
Expanded replay/adapter tests pass 33 synthetic checks (child exit 0, wrapper
stopped on the recorded descendant-exit race). File-backed scoring orchestration
and truth mapping remain pending; the adapter alone authenticates no provenance.

Timing preparation is in `execution_clock_v4.py` and train/validation-only
`audit_execution_clock_v4.py --source MATCH_ROOT --split SPLIT --output FRESH_JSON`.
The point estimate is the midpoint of the empirical enclosing-frame interval:
last non-extrapolated upper tick < execution, first non-extrapolated lower tick
>= execution. Preserve that interval for conservative scoring and the explicit
uncertified status. Do not infer exact production time from an exact native tick.
The helper has 32 passing synthetic checks. The first 287-match audit found
14 accepted events without such bounds (12 train, 2 validation); these remain
in the population. Resolve boundary evidence before full scoring; never silently
drop them or extrapolate timestamps. This helper does not alter the frozen
registration or the T6 converter's historical uncertainty intervals.

10:02 boundary correction: leading clamped frames retain an observed upper tick;
trailing clamped frames retain an observed lower tick. The opposite side remains
unsupported. The mapper accepts these one-sided bounds only when the edge clamp
is constant and monotone with the interior frame ledger, as implied by the
unchanged collector's searchsorted logic. It records which bound types enclosed
each event, keeps the midpoint/empirical interval and uncertified status, and
still rejects unenclosed events. Native samples can advance between screenshots,
so adjacent-frame equality is not required. Final tests pass 41 cases; repeated
audit on the identical 287-match population maps all 14,393 accepted events,
zero omissions. Preserve r1's 14-unenclosed diagnostic and r2's failed strict
check as historical evidence. This resolves coverage only, not timing accuracy.

`validation_score_v4.py` accepts admission's six paths plus `--replay REPLAY_DIR`.
Use the wrapper only after formal fitting and a completed full-validation replay.
It repeats admission first, checks driver/completion/output hashes and complete
episode/frame populations, then verifies receipt-pinned frame/event files. It
joins completion-journal availability and maps all accepted truth events; an
unmappable event fails the cell rather than leaving its denominator. Canonical
card type controls placement, retaining flight/underground as strata and abilities
separately. Output contains point and conservative scores and source provenance.
It creates no selection seal or heldout authority and does not certify Mac gates.
Twelve synthetic file-integrity/scoring checks passed with clean wrapper PASS on
16 at 10:16 UTC. A real model replay/scoring cell remains unrun. The file-backed
selection/calibration orchestration is still pending.

10:47 UTC pre-training selection preparation: `selection_matrix_v4.py` consumes
all 216 authenticated score cells (24 epochs x nine global thresholds). It
requires common formal readiness/checkpoints, scorer hashes, full validation
receipt/truth provenance and fixed per-match truth denominators. It proposes
the best global threshold per epoch, then the best epoch, with the registered
F1/precision and higher-threshold/earlier-epoch ties. The helper is pure: the
caller must recompute cells through `validation_score_v4.score_run`; consistent
JSON declarations alone are not authentication. Twenty-eight synthetic rejection/
ranking checks pass with clean wrapper PASS on 16. No real ranking performed.
This supplies neither per-card/body thresholds, calibrated final replay nor the
selection seal, and cannot authorize heldout access. Score receipts now retain
readiness evidence so different formal runs cannot silently share one grid.

`validation_select_v4.py` connects scoring and threshold proposals. After a real
full formal fit and all replays, run via the wrapper with admission's five input
paths, `--grid GRID_JSON --output FRESH_DIRECTORY`. Grid schema is
`clasher.v4.validation-grid-input.v1`, with exactly 216 `cells`, each containing
`epoch`, `threshold`, and `replay` (absolute or relative to the grid JSON).
The command authenticates admission first, recomputes every replay score rather
than trusting saved metrics, and checks the declared cell and common readiness.
It writes per-cell evidence and `event-selection-proposal.json`; `complete.json`
means this proposal computation completed, never heldout authority or a selection
freeze. Body thresholds, final mixed-threshold replay and calibration must follow.
Interrupted output is retained; retry uses a fresh directory. Every cell repeats
full run/checkpoint admission, so plan for the verification cost. Fourteen
synthetic orchestration checks passed on 16; the actual formal command is unrun.

`card_thresholds_v4.py` is a pure proposal helper for the selected epoch's nine
full validation cells. Per-card counts pool both native seats because EventFusion
uses one threshold per card, and require at least 10 true validation events;
otherwise use the selected global threshold. Fixed card-side truth denominators
and agreement with full per-seat totals are mandatory. Ties retain the registered
F1, precision, higher-threshold order. Seventeen synthetic checks pass on 16,
including 9/10 support and unseen-card fallback. The caller must authenticate
all cells first. Replay the final combined threshold map to measure actual FIFO
availability before fitting calibration; independently timed grid cells cannot
be spliced into a certified final timing stream. No real thresholds or seal exist.

`calibration_v4.py` fits the runtime isotonic knots from the selected model's
final thresholded/suppressed validation card-play stream. One-to-one 500ms
availability matches label positives; unmatched/duplicate predictions label
negatives. Both native seats contribute. Per-card fits need 20 predictions;
otherwise runtime uses the pooled `default` fit. Empty streams fail closed.
Pass the complete validation episode list and frozen split membership mapping;
the helper checks those declarations, but the eventual driver must authenticate
their provenance. Champion abilities are separate and refused in this input.
Synthetic checks passed 80 cases on leased 16 at 08:21 UTC, including an exhaustive
isotonic least-squares oracle, support boundary, malformed scores and split
rejection. No replay, real-data calibration, selection seal or gate measurement
has been performed by these tests.

Registered gap preparation uses `gap_schedule_v4.py` and
`l2/native/pair-*/public-frames.jsonl.gz`, field `timestamp_ms`, as explicitly
corrected by **PREREG-AMENDMENT-02.md**. That amendment supersedes the base
registration's decisions.jsonl path. It fails closed on missing/nonfinite/
nonchronological timestamps or duplicate frame identities. The 08:27 sparse
decision-source audit (23,546 intervals; 830.632 ms p95) was based on an incorrect
reading of the base registration alone; retain it as diagnostic evidence only.
Do not use it for the formal gap cell. Amendment 02 and all gates stay unchanged.
The schedule samples cumulative arrivals with seed 6109, then selects the first
frame at/after each arrival without duplicating frames. Freeze shared arrival
sequences before predictions and apply them to each arm's frame grid through
`select_arrivals`. Original timestamps remain in the plan. The T6 validation
adapter preserves its required integer-ms public contract with original times
in `source_timestamp_ms`; it uses the amended public-frame sources.
Schedule/source tests passed 24 synthetic cases on 16; the updated T6 adapter has only
syntax validation, not end-to-end replay. Final-population schedule generation
and sealing remain pending; this does not certify the gap recall gate. The
amended source audit and expanded frame-source tests passed under
`v4-gap-source-audit-20261008-r3` on 16 at 08:36 UTC: **60,586 intervals, p95 610 ms**,
range 7–2,075 ms. Its `-source.json` receipt pins each gzip SHA256 and the exact
interval vector. Use that amended-source receipt; r1's sparse-decision receipt
is retained for incident evidence only.

## Bounded Phase A checks

T3 schedule `Clasher v4 Phase A: bounded 15-minute checks` is bound to this
implementation thread, first due 2026-10-08 06:42:19 UTC. It must delete itself
at 2026-10-08 **18:08:27 UTC** or genuine Phase A completion. Do not start another
watcher. The short-lived 03 watcher was stopped after the interactive-session
cap was noticed; its exit receipt is retained. App-owned checks add no persistent
fleet worker. The schedule was updated after preparation; consult its live
`nextRunAt` rather than treating the initial due time as current.

A check may run `python3 l1/phase_watch.py --once --output
l1/receipts/phase-polls --deadline 1791482907` from the v4 directory on 05. This is
a lightweight SSH receipt read, not compute/media work. It skips a second read
within 15 minutes and does not write any T1 file. Match receipts, T1 progress,
producer state and producer exit are the only remote inputs. Never infer
completion from receipt counts, a launch PID, or a stale progress sentence.

## Cross-host cache probe, 2026-10-08 12:06 UTC

The 390-match union exceeds 300 GB; retain the 349-match base on 01/18 and the
verified extension on 16. `cache_transport_v4.py` can serve a pinned extension
manifest/inventory under its lease wrapper, after complete payload SHA validation.
It binds loopback only and holds the cache writer lock shared, so stop it before
another builder. Private token file mode must be 0600; never mirror it. Use fresh
`--ready`, `--probe-reference`, `--stop-file`; `--max-seconds` defaults to 600 and
caps at 3600. The local stop sentinel ends the service cleanly; the lease wrapper
also remains authoritative on reclaim. Keep SSH tunnels attached to client jobs.

`probe_cache_transport_v4.py --server-label LABEL --output FRESH_JOB_DIRECTORY`
on 18 uses direct 16→18 metadata/token transfer, an owned SSH loopback tunnel,
checks a new random 1% in raw/model form, then times six-thread loading. Its finally
block stops its own tunnel and this server's sentinel, with all receipts retained.
The first real probe passed 1,366 sample comparisons (683 frames), 33.245273
T16 windows/s at 50% raw inputs. No client disk cache, GPU training or selection.
Do not copy its entire output directory: it contains a private token; mirror only
`result.json` and wrapper exit receipts. Full trainer/admission integration across
the union and augmented/GPU throughput checks are still pending.

## Exact cache union preparation, 2026-10-08 12:19 UTC

`cache_union_v4.UnionPixelCache(receipts, shards)` checks that the entire declared
train/validation receipt population is covered exactly once before loading pixel
payloads. Each shard supplies inventory/manifest paths; local shards also supply
`kind=local, cache`, remote shards `kind=remote, ready, token_file, endpoint`.
Full local SHA verification and shared cache writer locks remain mandatory;
remote readiness must match the manifest/inventory/index hashes. Use as a context
manager or close explicitly. The helper does not establish authentic producer
completion or formal population admission: its caller must do that first.
Stable provenance contains manifest/inventory/index hashes, never tokens/ports.
Thirty-nine synthetic checks passed, including real local/loopback exact routing.

The engineering `probe_cache_transport_v4.py` accepts all five optional union
arguments together: `--union-local-cache`, `--union-base-inventory`,
`--union-base-manifest`, `--union-source`, `--union-remote-prefix`. The latter
names the verified `v4-cache-unique-...` job on 16; its plan/manifest are copied
directly to 18. Remote receipts come from the hash-pinned service reference and
local receipts must match the base inventory. This performs no model fitting.
The 404-match real union probe is pending; full trainer/admission integration,
augmented parity, resume and end-to-end GPU rate are still required. No formal
command switches to this helper automatically.

## Union training engineering follow-up, 2026-10-08 12:36 UTC

Real 404-match union data probe passed 1,840 sample comparisons, 98.489652 T16
windows/s in a short 128-window warm test; initialization/full local hashes took
423.130113 seconds. This does not measure augmented or GPU training throughput.

`train_v4.py --engineering-union RUNTIME_JSON` admits only the entire staged
train/validation snapshot, one epoch and at most 128 steps, with no match limit
or alternative cache. Four negative bound checks passed on 01. It pins the
union helpers and stable index/manifest provenance and checks 8 local + 8 remote
augmented samples, historical RNG equivalence and six-thread tensor equality
before training. Those real parity/GPU checks are pending. Formal admission still
refuses this engineering-only path; no subset/pilot weights may initialize formal.

When both host locks are free, run a fresh 16 transport service on the verified
extension with `--max-seconds 1800` (allow time for the 7-minute local SHA pass),
fresh token/ready/reference/stop files. On 18, through its lease wrapper:
`benchmark_union_v4.py --server-label FRESH_SERVER_LABEL --extension-prefix
v4-cache-unique-20261008-16r4 --output FRESH_JOB_DIRECTORY`. The helper stages
exactly the 349-base + 71-extension episodes (420 matches), checks receipt pins,
creates an attached SSH tunnel and runs the fresh 128-step engineering fit.
It forwards stop signals to its active child and closes its tunnel/server sentinel
in finally. Retain interrupted outputs; optimizer resume support of the union
orchestrator and formal reader/admission remain pending. Runtime files contain
private token paths; never mirror its whole output directory or any weights.
Mirror only named compact result/parity/exit receipts and source snapshots.

At 12:35 T11 holds both lease workload locks (`t11-v2-store-copy-127x16-v1`,
`t11-v2-store-copy-127x18-v1`). Do not duplicate or bypass those jobs. The first
18 bounds-test and 16 audit-r19 attempts failed before child launch; retain them.
The subsequent 01 bounds test passed. Benchmark/helper import smoke also passed on 01 (wrapper 3616129). Actual driver
execution, new-population label audit, augmented/GPU test and formal gates remain pending.

## Body threshold runtime option, 2026-10-08 12:49 UTC

`PixelPerception(..., body_threshold=.5)` now accepts only the registered
0.1..0.9 grid and applies it to BodyTracker's high-confidence threshold on every
episode reset. Low-confidence association remains .1; default .5 is unchanged.
Fifteen synthetic real-pixel stream checks passed on 01, including confirmed-track
behavior above/below the configured threshold. No body threshold was fitted.
The validation driver still uses the default; body matching/scoring, fitting and
passing its selected option into replay remain pending. Changes to this threshold
affect tracks/birth maps and therefore event fusion: use the final body/event
configuration in the combined validation replay before calibration and sealing.
Deploy the updated owned model source to 18 before its next engineering GPU run.

Hub timing audit r7 maps all 21,273 accepted train/validation events in a 435-match
snapshot, with zero omissions; empirical interval p95 256.981707 ms remains
uncertified. Label audit r20 covers the earlier 433-match snapshot. Neither audit
reads heldout payloads or establishes any formal endpoint.

## Explicit replay body configuration, 2026-10-08 13:02 UTC

`validation_replay_v4.py --body-threshold VALUE` validates the registered 0.1..0.9
grid, passes it to PixelPerception and pins it as `body_threshold` in the replay
manifest. Default remains .5. `validation_score_v4.py` refuses missing/invalid
body settings and carries the field into scores. The complete 24x9 event grid and
selected-epoch per-card sweep must each use one common body setting; mixed cells
are refused. Ranking, per-card and final event-proposal receipts retain that value.
This is comparison provenance, not evidence that a body threshold was fitted.
Body truth matching/F1 fitting and final combined replay/calibration still follow
before sealing. Rebuild old synthetic manifests rather than assuming an omitted
body field was .5; no real formal replay exists to migrate.

The focused suite `test_body_selection_pipeline.sh FRESH_FIXTURE_DIR`, through
01's fleet wrapper, passed **120 checks** (33 replay, 16 scorer, 33 grid, 22
per-card, 16 proposal). Current runtime/validation source changes are on 05/01;
deploy only the owned updated files to leased hosts after checking their active
work. Formal producer/full-fit admission still precedes all real replay reads.
At 13:01 T11 still holds both 16/18 workload locks; cache/GPU extensions remain
pending. No substitute subset fitting, extra replica, or lock bypass is allowed.

## Home03 CPU fallback, 2026-10-08 13:23 UTC

T11 owns the 16/18 workload locks with GPU fits through its configured 04:20Z
stop. Do not bypass the lease wrapper. Home03 is CPU-only, with a dedicated
`/mpac/sdicks02/repos/clasher-v4-cpu/.venv` (setup_cpu_cache_03.sh). Run
`cache_home_03.py --label FRESH --admitted PINNED_TRAIN_VALIDATION_INVENTORY`
through the existing home fleet_run.sh. Eight workers and a 78 GB operating
ceiling fit its 80 GB reservation; at launch check console users/processes/RSS
and free space. The current helper explicitly excludes the verified 349+71
shards before staging only the 37 additional episodes in the 13:12 snapshot.
It copies no heldout receipts/payloads and does not poll producer completion.
Inspect the .exit and final -manifest.json before counting completed coverage.
On resumption use a fresh label only after verified old PIDs exit; completed
shards are SHA-checked and reused. Never start a concurrent writer. Additional
populations require a fresh pinned inventory; this job is not a watcher.

This operation does not solve formal fitting across shards: the augmented union
GPU benchmark remains unrun, and formal admission/selection still requires full
producer completion and the frozen preparation gates.

## Combined threshold replay preparation, 2026-10-08 13:34 UTC

After formal fit admission, the validation replay driver accepts
`--threshold-map MAP.json` for a fresh combined per-card/body replay. MAP.json is
an object with `default` plus card overrides, every value on the registered
0.1..0.9 grid. Its default must equal `--threshold`; cards must belong to the
fitted vocabulary. Pass the chosen `--body-threshold` explicitly. The driver
pins the map SHA and complete map, marks `replay_mode=combined`, and measures the
normal complete FIFO stream again. This option supplies configuration, not proof
of threshold fitting or a selection seal. Actual full validation body fitting,
combined replay, calibration and seal still must precede heldout.

The scorer supports these uncalibrated combined replays and returns their exact
configuration. `rank_validation_grid` and `select_card_thresholds` accept only
`replay_mode=grid` with exactly one default threshold; combined cells cannot be
substituted into the 24x9 epoch grid or nine-point per-card sweep. Replay manifests
must explicitly declare mode/options. No old real formal replay exists. The
focused pipeline passed 147 checks on 01 (v4-combined-replay-20261008-01r2).

Home03 cache extension r2 is now complete: 50 episodes beyond the 349+71 shards,
including 37 reused and 13 newly built; its plan/manifest supersede r1 in a union.
470 matches total are verified for the13:29 snapshot; this is not formal admission.
Keep the 80 GB reservation and 78 GB operating cap; completed indices are reused
by later fresh-label batches only after previous PIDs exit.

## File-backed calibration candidate, 2026-10-08 13:47 UTC

`calibration_candidate_v4.py` takes the same `--run`, `--source`, `--split`,
`--phase-state`, `--phase-exit`, `--replay` arguments as the authenticated scorer,
plus a fresh `--output` directory. Run through the 01 fleet wrapper only after
formal fitting and a complete combined-threshold validation replay. The shared
`load_replay` authenticates producer/full-fit admission and complete source/replay
provenance before fitting; grid-only, calibrated, incomplete or modified replays
are refused. Champion abilities are excluded from card-play isotonic fitting.
The existing registered support and pooled fallback rules remain unchanged.

It writes `calibration-candidate.json` and a SHA-pinned `complete.json`, retaining
exact epoch, body/event options, full validation receipts/truth, raw replay and
source hashes. These are **unsealed candidates**. Their explicit
`selection_provenance_verified=false` means the driver has not authenticated
which epoch or thresholds won selection. The eventual selection verifier must
match its authenticated choices to this exact replay/configuration before sealing.
No candidate or completion receipt authorizes heldout. Failed output is retained;
use a fresh directory on retry. Actual full-validation calibration is unrun.
Nineteen candidate checks and 147 replay/selection regression checks passed on 01;
formal/Mac/T5/T8 gates remain BLOCKED.

## Event-selection verification, 2026-10-08 14:04 UTC

`verify_event_selection_v4.py` accepts admission's five paths, `--grid GRID.json`,
`--selection ORIGINAL_SELECTION_DIR`, and `--output FRESH_DIRECTORY`. It repeats
formal admission before reading selection evidence, verifies the original 216
stored score hashes and completion, then invokes select_run to recompute every
actual validation cell. Original files remain read-only; recomputation goes to
`OUTPUT/recomputed-selection`. Any difference in scores, selected checkpoint,
ranking, thresholds/support or provenance fails, retaining diagnostic output.

Only a successful exact comparison writes `event-selection-verified.json` and
its hashed completion receipt. These verify epoch/global/per-card EVENT selection,
not body-threshold fitting or a final seal. `body_selection_verified=false`,
`selection_seal=false`, and `heldout_opening_authorized=false` remain explicit.
The current scorer repeats full formal checkpoint admission for each cell; allow
for that cost. Seventeen synthetic orchestration/rejection checks passed on 01.
No real validation selection or verification has run.

Home03 r3 is complete: 72 episodes beyond 349+71, with 50 reused and 22 new. Use its
plan/manifest instead of r1/r2 in union plans. Total 492 matches are verified for
13:58 admission. Root 56.817 GB is below the 80 GB reservation/78 GB operating cap;
reassign reservations within 1 TB before raising any limit. No current v4 job.

## Cache reservation reassignment, 2026-10-08 14:15 UTC

Live cache metadata verified 16=213.910 GB and 03=56.817 GB before reallocating
70 GB from 16 to 03. Current reservations: 01=300, 18=300, 16=230, 03=150 GB (980 GB
aggregate plus 20 GB headroom). No data moved/deleted; all free-space floors hold.
The budget helper enforces the new ceilings; 31 boundary checks passed on 01.
03 helper now uses 148 GB, eight workers; 16 unique helper uses 225 GB and must
still wait for its lease lock. Default 280 GB commands on 16 will correctly fail
the reservation guard; choose an explicit budget within 230 GB. No T11 job changed.
Do not use the historical 80 GB /78 GB 03 caps as current reservations.

## Home01/03 engineering union fallback, 2026-10-08 14:36 UTC

While T11 occupies16/18, benchmark_union_v4.py also supports client01/server03.
The home service is launched through fleet_run with `cache_server_home03.sh
FRESH_SERVER_LABEL VERIFIED_EXTENSION_PREFIX`. It creates a private0600 token,
verifies cache payloads and serves loopback-only under a shared writer lock for
at most1800 seconds after readiness. Use a fresh service label and wait for its
ready.json. No concurrent03 cache builder while the service holds its read lock.

Launch the home01 client through fleet_run with the same server label, extension
prefix and a fresh output path. The client uses stage_engineering_view_v4.py to
make verified immutable-input hardlinks for exactly its two cache shards. It owns
its SSH tunnel and requests service stop in finally. Do not bulk-mirror output:
it contains a private token and model weights. The code permits only01/03 or18/16.

Current pilot:349 base +84 home03 matches =433 matches,770,568 frames. The71
matches on16 are excluded, so this cannot substitute for the formal population.
Train1x128 fresh steps only after the16-sample augmentation/RNG/parallel parity
check. Formal selection rejects this fit. This measures an engineering union;
full-population integration, resume and full preparation gates remain pending.
The12 synthetic input-view checks passed on01; actual parity/GPU result pending.

Home01/03 pilot completed at 14:45:24 UTC, both wrappers exit 0; no resume needed.
16 augmented samples passed historical RNG and six-thread tensor parity. Measured
10.054579 training windows/s (78.23% of same-run GPU rate) over 128 steps, excluding
full SHA/metadata/parity startup. Named compact receipts are mirrored under
preformal-cache-20261008. The 433-match engineering subset excludes 71 on 16;
full formal union/admission integration remains pending. Service stopped and its
read lock released; inspect jobs again before the next 03 cache extension.

## Calibration verification preparation, 2026-10-08 14:52 UTC

`verify_calibration_v4.py` takes the formal admission paths plus `--grid`,
`--selection`, `--replay`, `--candidate` and fresh `--output`. Authentic producer
completion and full fit are checked before candidate reads. It repeats the full
216-cell event-selection verification, requires identical checkpoint, event map
and body setting in the calibration replay, then recomputes calibration from
that authenticated combined replay. Original candidate/configuration/provenance
must match exactly, including a final unchanged-file check. Failed recomputation
outputs are retained; use a fresh output for retry. Run through the fleet wrapper.

This verifies event-selection binding and calibration only. Body threshold
selection is not yet authenticated; `body_selection_verified=false`,
`selection_provenance_verified=false`, `selection_seal=false`, and
`heldout_opening_authorized=false` remain explicit. No real candidate has run.
Twenty-seven synthetic orchestration checks passed on 01 (label
`v4-calibration-verify-20261008-01r1`, wrapper 3652899, exit 0), including altered
choices, internally rehashed calibration edits, wrong checkpoint, failed event
verification and candidate mutation. Real scoring/admission use existing suites.

Home03 r5 completed at 14:52:05 UTC (wrapper 3618307, exit 0). Use its 113-match
plan/manifest in place of r4; 84 reused +29 new. Total disjoint coverage is 533
matches for the 14:47 receipt snapshot. Root 89.095 GB, 148 GB operating cap within
150 GB reservation; 1.699 TB remains free. No active 03 writer/service. Do not
expand from an old admission or bypass leased-host locks. No full formal union yet.
