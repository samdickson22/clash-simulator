# T6/T7 results — formal evaluation remains blocked

## Pre-formal cache and label work, 2026-10-08

**Formal T6/T7 fits and heldout evaluation have not run.** At 08:57:54 UTC the
producer state is `phase-a`, with no phase-a exit receipt. Receipt-only counts:
224 train, 27 validation, 27 heldout matches; **661 heldout opponent events**;
24,867.16 recorded emulator-seconds (6.91 h). Neither stop rule is met. No
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
| Full staged training population, 163 matches / 5,112 candidate windows / 128 steps, six threads | **10.713 windows/s**; GPU loop **15.362 windows/s**, 245.80 encoded frames/s |
| Same full-population run, mean loading wait / CUDA allocated / reserved | **16.818 ms** / 2,034.31 MiB / 2,534 MiB |
| Eight-thread comparison, same population / seed / 128 steps | **10.501 windows/s**; GPU loop 15.729; mean loading wait 20.650 ms |
| Full staged cache snapshot | **163 train + 20 validation; 325,999 frames; 149,926,468,048 payload bytes** |
| Full-cache equality and destination integrity on 01 and 18 | **3,334/3,334 exact random-1% frames**, zero mismatches; **366 file hashes** verified on each destination |
| Incremental snapshot verified on 18 at 08:16 and 01 at 08:23 UTC | **185 train + 23 validation; 373,198 frames; 171,139,010,394 payload bytes** |
| Incremental equality and destination integrity on 01 and 18 | **3,817/3,817 exact random-1% frames**, zero mismatches; **416 file hashes** per destination |

The 12.476 rate is 9.73 times the old end-to-end rate and exceeds the old
176.32/16 = 11.02 GPU-bound windows/s estimate. It is 74% of the new measured
GPU-only rate including prefetch startup, logging and frequent checkpoint I/O;
mean GPU-plus-loading-wait time corresponds to about 14.40 windows/s. These are
engineering pilots on different populations/hosts, not a controlled accuracy or
identical-population speed comparison. The later full staged population measures
10.713 windows/s: 8.36x the historical decode-limited rate, within 3% of the
historical 11.02 windows/s GPU estimate, but only 69.7% of its own measured
15.362 windows/s GPU loop rate. Loading wait, prefetch startup, logging and
eight-step checkpoints remain overhead. Both full-population probes ran while
the hub was copying from 18, so the copy load is a limitation. Eight preparation
threads did not improve performance; retain six. These are engineering fits,
not formal models or heldout accuracy measurements. One-time full payload
verification/data initialization is outside the measured optimizer-loop wall time.

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

**Derived-cache storage was approved at 07:22 UTC:** 300 GB per permitted host,
with >=200 GB free on /mpac, plus the subsequently approved 1 TB aggregate cap.
The 40 GB frozen acquisition cap remains unchanged.
Both 24-worker decode partitions passed by 07:36 UTC, covering the staged
**163 train + 20 validation matches, 325,999 frames**. Full-replica gathering and
SHA256 verification are running on 01 and GPU host 18 in the new approved cache
roots. Host 18's full snapshot manifest passed at 07:49 UTC; hub verification
passed at 08:04 UTC. Full-population throughput is reported separately above. Incremental
builds continue as admitted matches arrive. No formal subset substitution is permitted.

The same label audit extended to this snapshot: 2,918,547 object rows and 411,626
contradictions (169,501 catalog-generation disagreements resolved, 20,938 parent/
child hints, 87,027 non-hitpoint hints, 134,160 unresolved/masked). Zero native-ID
changes or same-tick raw-join mismatches; 86,475 coherent visible/nondeploying
rows. No additional cleaning-code change. Synthetic scorer/selection primitives
passed 135 checks. Validation calibration primitives passed 80 additional synthetic
checks at 08:21 UTC on leased 16; real-data replay/calibration and selection sealing
remain pending. No formal metric follows from these synthetic checks.

The next **225-match / 404,396-frame** snapshot finished disjoint decoding on
16/18 at 08:25/08:26 UTC. Full verification passed on 18 at **08:36:42**:
**185,265,622,912 payload bytes; 450 hashes; 4,137/4,137 exact random-1% frames,
zero mismatches**. Hub gather also exited 0 and independently verified this
225-match snapshot by 08:44 UTC. The r7 label audit was refused
before child launch by the host-wide wrapper lock; the sequential r8 retry
passed at **08:37:42**, covering **200 train + 25 validation**. It found **501,159
contradictions / 3,635,665 rows**: 210,896 catalog disagreements resolved,
24,419 parent/child hints, 105,669 non-hitpoint hints, 160,175 unresolved/masked.
Zero changing rich IDs or same-tick ID/field mismatches. No cleaner change.

Gap-source correction at 08:35 UTC: **amendment 02 explicitly specifies public
frame logs**, superseding the base registration's decision-log path. The 08:27
audit of 48 decision files / 23,546 intervals / 830.632 ms p95 was an incorrect
source choice; its hashes and intervals are retained as diagnostic evidence.
No formal model replay used it. The helper now uses public-frame timestamps as
amended; the fresh audit passed at **08:36 UTC: 60,586 intervals, p95 exactly
610 ms, range 7–2,075 ms**, reproducing the historical summary. **24 synthetic
source/schedule checks passed.** The decision-source measurements remain incident
evidence and are not formal gap inputs. No
final-population schedule seal or gap replay metric exists. All formal gate
verdicts remain unchanged.

At 08:43 UTC, the next **239-match / 427,062-frame** stage snapshot finished
disjoint decoding; full-copy gathers on 01/18 are pending. Its label audit passed:
**213 train + 26 validation; 538,227 contradictions / 3,856,644 rows**. Counts by
cause: 227,653 catalog-generation disagreements resolved, 27,060 parent/child
hints, 113,855 non-hitpoint hints, 169,659 unresolved/masked. No rich-ID changes
or same-tick ID/field mismatches; cleaner unchanged. Selection evidence guard
tests passed 23 synthetic checks with child exit 0, but the lease wrapper marked
the short test stopped on its descendant-exit race. No formal fitting/replay or
validation selection was performed.

The **239-match / 427,062-frame** snapshot subsequently passed full verification
on 18 at **08:53:29** and 01 at **09:00:14**: **196,055,910,677 payload bytes,
478 hashes, 4,369/4,369 exact random-1% frames, zero mismatches** per copy.
The next **253-match / 453,896-frame** snapshot has passed disjoint decode and
label audit; its full-copy gathers are active. Its unchanged cleaner audited
**225 train + 28 validation**: 576,358 contradictions / 4,107,659 rows;
247,456 catalog-generation disagreements resolved, 30,548 parent/child hints,
120,234 non-hitpoint hints, 178,120 unresolved/masked. No native-ID changes or
same-tick ID/field mismatches. File-backed validation admission passed seven
synthetic integrity checks with clean wrapper PASS at 09:01 UTC. It did not
validate a real formal fit, run replay, select weights, or open heldout payloads.

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
