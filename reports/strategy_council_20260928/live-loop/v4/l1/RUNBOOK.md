# T6/T7 fleet runbook

Home-host commands run from `/mpac/sdicks02/repos/clasher` on **127x01**. Use only
`/mpac/sdicks02/envs/clasher-gpu/bin/python`; eager CUDA, no compile. Check `who`,
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
  /mpac/sdicks02/repos/clasher-v4-data/cache
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
logs to 05. No media or model files to 05. Keep total v4 fleet footprint <=40GB;
stop on space pressure instead of deleting data. Export plan: EXPORT.md.

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
The current per-match space allocation is conservative; use bounded batches
and explicit total cache budgets. No cache deletion is allowed.

The successful five-match pilot is under
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
The existing **40 GB total fleet footprint remains binding**; a storage-only
increase was requested but has not been approved. Do not silently decode a
subset and call it formal, exceed the budget, or discard originals to make room.

Use the live leased-host run.sh/env.sh from fleet/LEASED-HOSTS.md, never the home
fleet_run.sh on a borrowed host. Check leases/caps/GPU/RSS before every launch.
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
