# T6/T7 formal L1-v4 evaluation registration

Frozen before heldout scoring. This document registers evaluation, not completion
of the model or Mac qualification. Source/selection seals are separate receipts.
Population: Phase A only, frozen split SHA256
`3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258`.
No heldout media or labels may be opened until T1 explicitly reports Phase A
complete and a producer completion receipt is recorded. Receipt counts alone may
be inspected. Require >=20 heldout matches and >=1,500 accepted opponent plays;
a shortfall is a failed coverage gate, not permission to extend or resplit.

## Arms and selection

T6: v3 architecture, initialization (local v2 checkpoint), optimizer, loss,
sampling and 24 epochs x 400 steps unchanged. Only device selection is ported.
The producer's unchanged timestamp converter supplies ~10 FPS video. A separate
adapter supplies protocol-2 metadata (v4 retains the same 700ms terminal tail)
and the evaluator's private observation layout. Preserve all original payloads.
Use the existing v1 body detector and training-only refitted HUD. The unchanged
v3 evaluator selects thresholds on validation; its native-time uncertainty
interval matching remains the historical control. Report the domain shift
against published recall 180/280 and 90 false positives, with match bootstrap
intervals rather than claiming numerical equivalence.

T7: shared CNN <=12M parameters, HUD <=0.5M and temporal head <=4M;
448-wide x 832-high arena, stride-16 64-channel cache, T=16 valid past frames,
36-wide x 64-high tile heatmaps, explicit irregular ages/masks, no gap reset.
Bodies use owner/identity, weak calibrated boxes and masked normalized HP.
Unknown body identity/visibility is never relabelled as background. HUD reads
only own slots, next card, elixir, visible clock and phase. Events regress
execution age and sigma over the preceding 1.5s, with cast-origin and birth
features. Champion abilities are reported separately, not counted as card plays.
No native labels enter inference, including native birth counts or true time.

Formal training begins only after Phase A completion. Start from fresh random
T7 weights (seed 6108); shakedown weights are discarded for formal fitting.
AdamW lr 0.0003, weight decay 0.0001, clip 10, bf16 eager CUDA, batch 1,
24 epochs x 400 steps, uniform training windows with explicit negatives.
Save each epoch; select by opponent validation F1 at 500ms, tie: higher
precision, then earlier epoch. T6 uses epoch 24. Training-only augmentation:
irregular 5-30 FPS subsets (never synthesize missing 30 FPS observations from
20 FPS video), gaps <=1.2s, timestamp jitter, color/gamma/compression, modest
arena scale/translation and horizontal flips, with spatial labels transformed;
HUD is never flipped. All per-card thresholds, isotonic calibration and body
thresholds are fitted on validation and sealed before heldout. Threshold grid
0.1..0.9 step 0.1, maximize F1, tie higher precision then higher threshold;
per-card override needs >=10 validation events, else global threshold. Isotonic
fit requires >=20 predictions, else pooled validation fit. Do not fit on test.
Body threshold selection maximizes validation F1; also report phantom/drop rates.
Before heldout, seal exact checkpoint/source hashes, thresholds, calibration,
training population, label vocabulary and all options in selection-freeze.json.
Any necessary model/training amendment must be dated before heldout scoring;
none can change gates after outcomes are inspected.

## Replay and endpoints

Primary evaluation is heldout replay through the pipelined runtime on the Mac
with the emulator idle-running. This task performs no Mac work. Fleet replay is
a diagnostic and cannot pass the Mac latency gate. Reuse the same heldout matches
in every arm. Nominal v4 20 FPS and v3 ~10 FPS; additionally report both at 10 FPS.
For the gap cell, precompute a schedule from all chronological frame intervals
in `live-loop/l2/native/*/decisions.jsonl` (the L2 empirical p95 is 610ms), seed
6109, sampled independently of labels. Replay selects the first frame after each
scheduled arrival; retain original timestamps and no duplicated frames. Freeze
the resulting schedules before predictions. If those raw intervals cannot be
reconstructed unambiguously, mark the cell blocked; do not substitute a Gaussian.

Availability is output completion, including FIFO backlog, not frame capture or
backdated execution time. Correct card+side, one-to-one minimum-cost assignment
within [execution, execution+500ms]. Exact exec_tick maps to production time via
the enclosing frame tick brackets; publish interval sensitivity using the v3
conservative bracket rule. Never score a backdated time as availability.
Duplicates and unmatched predictions are false positives. Report both seats,
opponent primary (native owner 0), per-card-side, spell/flight/underground and
spawner-adjacent strata. Temporal NMS: same card+side, <=1.5 tiles, execution
estimates <=300ms; own spells require causal own-HUD corroboration.

All §5.1 gates are conjunctive; unmeasured is BLOCKED, never PASS:

| Endpoint | Required value |
|---|---|
| Opponent event recall and precision at 500ms | each >=95%, each bootstrap lower bound >=92% |
| L2-gap opponent recall | >=90% |
| Each card-side with >=10 heldout events | recall >=80%, precision >=70% |
| Absolute backdated execution-time error, matched events | p95 <=150ms |
| Placement among all true troop/building plays | >=90% within 1 tile |
| Placement among all true spell plays | >=85% within 1.5 tiles |
| Own hand slot accuracy / tracked elixir MAE | >=99.5% / <=0.15 |
| Derived opponent elixir MAE / central-90% coverage / width | <=0.5 / 85-95% / <=2.0 |
| Exact opponent hand when concentrated / query share after 60s | >=95% / >=60% |
| Mac perception latency with emulator running | p95 <=40ms |

S1 failed to justify lowering the provisional 95/95 gate. S3 is in progress;
its tracker remains an integration dependency. Report raw model HUD separately
from T8 own-state and opponent-state gates; a detector alone cannot certify them.
Concentration means top hypothesis mass >=0.9, not branch unanimity. Query state
once per native second using only outputs available by that time.

95% percentile intervals: 10,000 match-cluster bootstrap resamples, RNG seed
6110, both sides retained together. Compute micro counts after resampling;
paired arm differences use identical match indices. All eligible heldout matches
are scored once after selection; no outcome-based stopping, subset selection,
retuning or removal of difficult cards. Infrastructure failure reruns use the
same seed/input/checkpoint and retain failed receipts with INCIDENT notes.
Learning-curve 25/50/100% training fractions, if run, are deterministic hash-ranked
nested training populations and all models must be frozen before one joint
heldout opening. Phase B is a later coordinator decision, not automatic tuning.

## Artifacts and operations

Store source hashes, split/receipt hashes, producer completion evidence,
selection seal, predictions, per-match counts, full gate table and metrics.json.
Keep data and weights on 127x01; mirror code/docs/compact receipts to 127x05.
GPU jobs eager, nice 10, detached via fleet/fleet_run.sh, <=96 host workers
(<=16 with console user), no torch.compile, leave >=12GiB GPU headroom.
Never access excluded hosts or the Mac in this task. No commits or deletion.
Heldout tooling must fail closed when either freeze or producer completion is
missing. Current shakedown entry points accept train/validation only.
