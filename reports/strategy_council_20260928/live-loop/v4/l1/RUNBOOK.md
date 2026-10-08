# T6/T7 fleet runbook

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
current reservations are 300 GB each for 01/16/18, total 900 GB. Reassign within
the aggregate cap before admitting another cache host. See STORAGE-AMENDMENT-20261008.md.
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
`cache_batch.sh build LABEL PARTITION PARTITIONS WORKERS` stages only admitted
train/validation files, reuses checksum-verified pilot matches, and decodes its
disjoint seed partition. Run through the appropriate fleet/lease wrapper.
Initial plan: partitions 0/2 and 1/2 on 16/18 with 24 workers each. Host 18 stages
all train/validation payloads for subsequent T7; 16 stages its media partition.
`sync_pixel_cache.py` imports only completed matches through unique temporary
directories, verifies SHA256/equality evidence, then atomically publishes them.
It checks host budget/free space before each import and retains interrupted copies.
Never substitute a cache subset for the formal population or discard originals.

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
