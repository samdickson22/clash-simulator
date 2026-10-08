# T6/T7 progress

Updated 2026-10-08 06:05Z. Phase A remains RUNNING; heldout payloads unopened.
Code/docs/compact receipts live on 127x05; all decode, training, tests and exports
run detached/nice on 127x01. No Mac/excluded host access, no commits/deletion.

## T6

83 training + 10 validation matches snapshotted and converted with the unchanged
producer converter; all 93 roundtrip checks pass. Corpus:
`127x01:/mpac/sdicks02/repos/clasher-v4-training/t6-shake-1`.
The separate adapter fills evaluator protocol-2 and private observation layout.
Frozen split/collector/T1 files were not changed.

One epoch x 40 steps completed, mean loss **7.15737**, optimizer-loop **5.31s**.
The full HUD/video preparation took minutes. Model and 563MiB allocated JPEG
cache: `.../clasher-v4-training/t6-run-2/model/`.

| Fleet label | Wrapper PID (historical; verify before reuse) | State |
|---|---:|---|
| t6-convert-shake-20261008-1 | 3454858 | complete, exit 0 |
| t6-shake-20261008-1 | 3459100 | stopped at original 450MiB cache guard, exit 1 |
| t6-shake-20261008-2 | 3469898 | fit complete; inference lacked dill, exit 1 |
| t6-shake-20261008-3 | 3475474 | fractional input timestamps rejected, exit 1 |
| t6-shake-20261008-4 | 3476418 | regular validation complete, exit 0 |
| t6-gap-20261008-1 | 3474941 | gap validation complete, exit 0 (worker 3474955) |

Inspect `/mpac/sdicks02/jobs/clasher/<label>.log`, `.pid`, `.exit` and result
`complete.json`; launch is not completion. Failed directories/receipts retained.
PyAV 16.0.1, pytest 8.4.2 and dill 0.4.0 added to GPU env; Torch unchanged.
Trusted local v1 YOLO checkpoint needs dill plus the documented weights-only env
workaround. Partial inference folder retained as `validation-inference-missing-dill`.

Regular validation: 10,698 frames, opponent R/P **8.494% / 52.381%** (22/259,
22/42); all-side **31.964% / 78.509%** (179/560, 179/228). Empirical-gap validation:
opponent **1.544% / 33.333%** (4/259, 4/12), all-side **10.714% / 41.958%**.
This is only 40 training steps, not convergence. Timing bracket p95 is 208ms under
the conservative unchanged matcher. See v3-control/RESULTS.md and l1/receipts/.
Both shakedowns are complete; no training/inference job remains queued or running.

Resume completed T6 stages via `l1/run_t6_shake.py --dataset .../t6-shake-1
--output .../t6-run-2`, new fleet label after confirming the old PID exited.
Do not overwrite a partial stage; preserve under an incident name first. T6
optimizer is intentionally unchanged and cannot resume mid-fit; restart that
stage into a fresh directory using the same seed if needed.

## T7

Compact v4 CNN plus body/HUD/temporal heads and streaming fusion implemented in
`src/clasher/vision/l1_v4.py`; training/data/export/guards under `v4/l1/`.
15 tests pass on 01 (`t7-final-tests-20261008`, wrapper 3485154, exit 0). TorchScript frame and
event export parity passes, exact in three variants per stage; no CoreML/Mac run.

Current shakedown: `.../clasher-v4-training/t7-shake-2`, label
`t7-shake-20261008-2`, wrapper **3463419**, exit **0**. 8 train matches, 64 steps,
2,422,997 parameters, 176.32 encoded frames/s compute, 1.282 windows/s with decode,
2,033.95MiB allocated / 2,526MiB reserved. `l1/RESULTS.md` gives scope/limitations.
Resume with identical train_v4.py arguments plus `--resume`, through a new label;
optimizer/RNG checkpoints every eight steps, manifests reject changed code/options.
The completed shakedown needs no resume and is not formal model initialization.
Measured source copies are preserved under l1/receipts/. Later changes improve
final-checkpoint recovery, runtime completion stamps and native-body aliases;
source-manifest.json identifies the final handoff. Export label
`t7-export-20261008-2`, wrapper 3469918, exited 0.

Body-label limitation: 19,473/153,902 object rows in eight training matches have
contradictory names/hints. Only 3,911 have conservative identity plus explicit
visible/nondeploying status. Those contradictions, projectiles and unknown
visibility are masked; collector data stays intact. Reviewed annotation audit
is needed before board-precision claims.

## Frozen registration and next runs

`l1/PREREG.md` and SHA256, prospective amendments 01 (body labels/sampling) and 02
(actual empirical gap source/cache disk guard), and registration-freeze.json are
sealed before heldout scoring. All §5.1 gates retain their original thresholds.
S1 did not lower 95/95; S3/T8 derived state and T5/Mac replay remain dependencies.

Formal commands are **prepared, not launched/scheduled**, in `l1/RUNBOOK.md` and
`formal_train.sh`: authentic T1 completion receipts + fixed split/registration
hashes + receipt-only coverage >=20 heldout matches/1,500 opponent events required.
Then fresh T6 24x400 and T7 24x400 fits. Selection remains validation-only; the full
v4 scorer, model-selection seal and later authorized Mac evaluation are pending.
There is no automatic heldout job. Export handoff is `l1/EXPORT.md`.
