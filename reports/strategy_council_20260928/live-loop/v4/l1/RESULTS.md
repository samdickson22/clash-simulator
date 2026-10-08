# T6/T7 results — preparation complete only for a bounded pilot

## Pre-formal cache and label work, 2026-10-08

**Formal T6/T7 fits and heldout evaluation have not run.** At 07:04 UTC the
producer state is `phase-a`, with no phase-a exit receipt. Receipt-only counts:
145 train, 18 validation, 18 heldout matches; **437 heldout opponent events**;
15,961.24 recorded emulator-seconds (4.43 h). Neither stop rule is met. No
heldout payload has been opened. The bounded 15-minute check ends at 18:08 UTC.

| Cache/loader measurement | Result |
|---|---:|
| Historical on-the-fly shakedown, eight train matches | 1.282 windows/s |
| Lossless cache + single preparation thread, one train match | 3.277 windows/s |
| Lossless cache + six preparation threads, one train match / 128 steps | **12.476 windows/s** |
| Same run's isolated optimizer-loop rate | 16.803 windows/s; 268.85 encoded frames/s |
| Mean loading wait including transfer | 9.95 ms |
| Four-train-match resumed fit, 104 remaining steps | **11.513 windows/s**, GPU loop 15.501 windows/s |
| Five-match cache population | 4 train + 1 validation; 14,592 frames |
| Exact random 1% frame check | **149/149 identical**, zero mismatches |
| Full augmented cached/uncached sample check | **16/16 exact**, every input and target tensor |
| Historical sampler / parallel preparation regression | **32/32 exact**, tensors and RNG; 8 JPEG, 13 affine, 16 flip cases |
| Cache payload size (one copy) | 5,910,676,788 bytes |
| CUDA peak allocated / reserved, 128-step pilot | 2,033.58 / 2,526 MiB |
| Reclaim behavior test | SIGTERM at step 24; resume to 128, no skipped/duplicate steps |

The 12.476 rate is 9.73 times the old end-to-end rate and exceeds the old
176.32/16 = 11.02 GPU-bound windows/s estimate. It is 74% of the new measured
GPU-only rate including prefetch startup, logging and frequent checkpoint I/O;
mean GPU-plus-loading-wait time corresponds to about 14.40 windows/s. These are
engineering pilots on different populations/hosts, not a controlled accuracy or
identical-population speed comparison. Full-corpus throughput is not measured.
The resumed four-match run provides an additional population check.

The cache preserves JPEG-before-resize augmentation using a lossless source
pixel stream alongside resized uint8 arena/HUD blocks. A failed first equality
test found a real decoder defect: OpenCV frame-number seek returned frame 1,866
for requested 1,867, with 30,693 differing elements. The accepted cache/reference
uses exact sequential ordinal. Equality is against that corrected on-the-fly
reference, **not** against the old approximate-seek bug. The failed attempt is
retained. All successful blocks have file SHA256 and per-match indices.

The audit covered 121 train/15 validation matches, 2,074,211 object rows and
275,223 name/hint contradictions. Classified counts: 114,371 catalog-generation
disagreements resolved with a unique reachable payload and exact max HP;
14,321 legitimate parent/child differences; 56,921 non-hitpoint parent hints;
89,610 unresolved/masked. No observed native-ID changes or same-tick raw-join
mismatches explained the contradictions. The label cleaner and conservative
timing policy are documented in LABEL-AUDIT.md and amendment 03.

**Full cache expansion is blocked by storage authorization.** At measured
density the audited population alone needs about 97 GB before copies; the
runbook's 40 GB total footprint has not been lifted. The accepted pilot is on
16/18, with all five matches on GPU host 18 and the required hub cache path on
01. Hub transfer completed at 07:01 UTC after its interactive session cleared
and worker preflight passed; all ten payload hashes were verified on 01. No
formal subset substitution is permitted.

## Formal configurations and §5.1 verdicts

Prepared T6: seed 6107, unchanged v2 warm start/v3 model, 24x400 optimizer steps,
3-positive/1-negative sampling, fp32 AdamW lr 0.0005, weight decay 0.0001, clip
10, training-only HUD refit; epoch 24, validation thresholds. Prepared T7: fresh
random seed 6108, T16/batch 1, 24x400, bf16 eager AdamW lr 0.0003, weight decay
0.0001, clip 10, cleaned body targets and lossless cache with six CPU preparation
threads. Selection: validation opponent F1 at 500 ms, then precision, then
earlier epoch; preregistered thresholds/calibration sealed before heldout.

| §5.1 endpoint | Required | Formal measured value | Verdict |
|---|---|---|---|
| Opponent event recall / precision at 500 ms | ≥95% / ≥95%; both bootstrap LB ≥92% | Not measured | BLOCKED |
| L2-gap opponent recall | ≥90% | Not measured | BLOCKED |
| Every eligible card-side recall / precision | ≥80% / ≥70% | Not measured | BLOCKED |
| Matched execution-time error p95 | ≤150 ms | Not measured | BLOCKED |
| Troop/building placement within 1 tile | ≥90% of all true plays | Not measured | BLOCKED |
| Spell placement within 1.5 tiles | ≥85% of all true plays | Not measured | BLOCKED |
| Own hand-slot accuracy / tracked elixir MAE | ≥99.5% / ≤0.15 | Not measured | BLOCKED |
| Opponent elixir MAE / central-90% coverage / width | ≤0.5 / 85–95% / ≤2.0 | Not measured | BLOCKED |
| Concentrated opponent hand accuracy / query share after 60 s | ≥95% / ≥60% | Not measured | BLOCKED |
| Mac perception p95, emulator running | ≤40 ms | No Mac operation authorized/performed | BLOCKED |

Conjunctive verdict: **BLOCKED**, no gate passes claimed. Primary heldout replay
requires the later Mac/integration worker. The full v4 validation/evaluation
driver, model selection seal and T5/S3/T8 integration remain pending work;
training scripts do not silently substitute fleet timing for Mac endpoints.
Evidence is in `receipts/preformal-cache-20261008/` and `receipts/phase-polls/`.

## Historical T7 engineering shakedown (quality not claimed)

Completed on 127x01 A6000, eager Torch 2.7.1+cu118, bf16. Eight training matches,
254 fixed windows, one epoch / 64 sampled steps, seed 6108. No heldout payloads
opened. This starts T7; it does not qualify the §5.1 gates.

| Measurement | Result |
|---|---:|
| Total parameters | 2,422,997 |
| Shared backbone / body heads | 2,086,560 / 40,762 |
| HUD / temporal event head | 78,729 / 216,946 |
| Training compute | 11.02 windows/s; 176.32 encoded frames/s |
| End-to-end training, including video decode | 1.282 windows/s |
| Mean sample loading | 672ms |
| 64-step wall time | 49.92s |
| CUDA peak allocated / reserved | 2,033.95 / 2,526MiB |
| Warm-cache CUDA frame+event invocation p50 / p95 | 7.03 / 7.35ms |

The compute rate includes optimizer steps; each window encodes sixteen 448x832
arena frames, even padded frames. Initialization affects the mean. The runtime
probe includes one current-frame encode plus a T16 head with repeated cached
features, but excludes decode, tracking, fusion and the emulator. It is a shape
throughput measurement, not video replay accuracy or a Mac budget pass. Video
decode currently dominates training wall time; no heavy work ran on 127x05.

The implementation is a compact CNN candidate, below all parameter ceilings,
with a shared stem for the ordered own-HUD atlas. It provides body identity/owner,
weak boxes, masked HP, own HUD, temporal heatmaps, age/sigma, top-three card mass,
cast-origin scores, calibrated existence probability and execution-time NMS.
History persists across gaps. High/low-confidence tracking requires two hits to
admit a body and retains last seen HP. Birth features are pixel-derived, with v3
spawner suppression in the streaming adapter. Integration with T5/P2 is still
required; `PixelPerception.step` provides the reference dictionary ABI.

Fifteen focused tests pass on 01: shape/parameter ceilings, masked-token invariance
(including NaN padding), irregular time sensitivity, gap history, execution-time
NMS, own-spell corroboration, isotonic monotonicity, phantom filtering/HP retention,
tiny joint overfit, pixel allowlist, runtime gap handling, body-label quarantine,
train/heldout isolation and refusal of incomplete Phase A admission (some tests
cover multiple properties). TorchScript frame and event stages reload with zero
max absolute eager difference in three test variants each. CoreML is planned,
not converted; no Mac operation occurred. See EXPORT.md.

## Label limitation

The eight-match audit contains 153,902 object rows: 108,210 have conservatively
consistent body identity, 19,473 have contradictory name/hint metadata, and only
3,911 have consistent identity plus explicit visible/nondeploying status.
Projectiles/non-hitpoint objects and contradictions are excluded from positives;
unknown visibility/identity regions are masked, not treated as background.
This is necessary given S2's board-precision finding. The collector is unchanged.
These weak native labels cannot certify board precision without a reviewed
annotation audit. PREREG-AMENDMENT-01 records the prospective training rule.

## Pending formal work

Phase A completion; complete-population fresh fitting; validation checkpoint,
threshold and isotonic selection with a source/checkpoint seal; a full v4 heldout
scorer and T5/S3/T8 contract integration; authorized Mac CoreML conversion and
emulator-on replay. Every §5.1 gate remains UNMEASURED/BLOCKED. RUNBOOK.md prepares
fail-closed formal fitting commands, not an automatic heldout evaluation.

Post-shakedown changes only improve completed-checkpoint recovery and stamp runtime
availability after fusion/serialization and normalize native body aliases before
v3 spawner suppression. Exact measured model/trainer sources
are retained under receipts/, with hashes matching the shakedown manifest.
