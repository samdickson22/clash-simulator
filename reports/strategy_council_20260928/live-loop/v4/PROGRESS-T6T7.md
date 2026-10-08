# T6/T7 progress

Updated 2026-10-08 07:40Z. Snapshot decode complete; cache copies RUNNING; heldout payloads unopened.
Code/docs/compact receipts live on 127x05; new decode/audit/tests/training pilots
run detached/nice on leased 16/18. No Mac/excluded host access, commits or deletion.

## Current continuation: cache and label cleaning

Formal work is **not launched**. Latest receipt-only poll (07:32 UTC): 163 train,
20 validation and 20 heldout matches; heldout 504 opponent events; 5.01 recorded
emulator-hours. Producer state `phase-a`; phase-a exit receipt absent. Neither
the ≥20/1,500 coverage stop nor the 36-hour cap is verified complete.

07:10–07:12 UTC scheduled continuation: deadline not reached. The one-shot
correctly skipped a duplicate poll (<15 minutes since 07:04:36); counts above
remain that snapshot, not a new observation. Existing 15-minute schedule verified
enabled, next trigger 07:27:24 UTC. No cache expansion or duplicate jobs launched;
the storage limit and all unmeasured formal gates remain blocking.
07:14:46 UTC continuation likewise remained before deadline and skipped the
duplicate receipt read. Latest actual observation is still 07:04:36 UTC; no
new remote Phase A read, payload access, or compute launch occurred.

07:15 UTC continuation also skipped the duplicate receipt poll. Independent
scorer preparation then completed: `l1/scoring_v4.py` implements availability-
time assignment, conservative bracket sensitivity, separate champion counts,
all-truth placement denominators, paired match bootstrap (10,000, seed 6110),
and exact registered threshold/epoch tie-breaks. No dataset-opening entry point.
Synthetic tests: **135 checks pass**, including 120 exhaustive assignment-oracle
comparisons. Lease 16 label `v4-scoring-tests-20261008-r2`, supervisor 3444011,
child 3444026, exit 0 / wrapper PASS at 07:20:09; peak 2 processes / 33,492,992
bytes RSS. Initial r1 syntax failure is retained in receipts/INCIDENTS.
Live 16 lease now permits 96 processes, no console user; this tiny test used two.
This is scorer infrastructure only: replay/tick mapping, calibration fitting,
full-population selection and seal remain pending; no gate was measured.

Lossless predecoded cache implemented in `l1/{pixel_cache,build_cache}.py`:
uint8 BGR arena/HUD and sanitized source pixels, indexed Zstd/XOR blocks,
per-file SHA256, atomic per-match commits, retained partial attempts and exact
random 1% checks. Source pixels preserve JPEG-before-resize augmentation.
Five-match pilot: **14,592 frames, 5,910,676,788 bytes, 149/149 equality checks**.
16 has four completed matches; GPU host 18 has all five checksum-verified.
Path on both: `/mpac/sdicks02/repos/clasher-lease/cache/v4-pixels-r2/`.
All five were copied to 01 at 07:01 UTC, with ten payload hashes and all five
indices verified. The hub cache was subsequently renamed, preserving bytes, to
**01:/mpac/sdicks02/repos/clasher-v4-cache/** at 07:31 UTC (migration exit 0).

Throughput: old **1.282 windows/s** → cached single-thread 3.277 → six preparation
threads **12.476 windows/s**, GPU-only 16.803, loading wait 9.95 ms. Four-train-
match resumed pilot: **11.513 windows/s**, GPU-only 15.501. Full-corpus rate is
not measured. Exact augmented-sample parity: 16/16. Historical sampler/parallel
RNG and tensor parity: 32/32. SIGTERM at step 24 checkpointed/exited, then resumed
to step 128 without duplicate/missing steps. All are engineering pilots.

The first equality test exposed OpenCV VFR frame-seek drift: requested frame
1,867 equals sequential frame 1,866 (30,693 differing elements). Failed cache
retained. Reference loading now uses exact sequential frame ordinal. This is
documented, not disguised as equality with the original buggy seek path.

Label audit: **275,223 contradictions / 2,074,211 rows** in 121 train + 15 validation
matches. 114,371 resolved catalog disagreements, 14,321 legitimate parent/child
differences, 56,921 non-hitpoint hints, 89,610 unresolved/masked. No observed
rich-ID changes or contradictory same-tick join mismatches. `labels_v4.py`
uses unique reachable payload + exact max HP, with coherent same-tick flags;
ambiguous repeated same-tick snapshots remain masked. Original collector/split/
payloads unchanged. See `l1/LABEL-AUDIT.md` and dated amendment 03.

**2026-10-08 07:22 UTC coordinator decision — storage APPROVED.** See
[COORDINATOR.md](../../COORDINATOR.md), entry “v4 perception storage approved,”
and the coordinator's explicit decision in this thread. The frozen acquisition
cap remains 40 GB for hub raw collected matches. Derived, regenerable caches
have a separate **300 GB per-host** allowance, with **at least 200 GB free** on
`/mpac`. Approved homes: `clasher-v4-cache/` on 01/03/04/08; leased cache root:
`clasher-lease/data/v4-cache/` on 11/13/14/16/18. Move retained pilot caches out
of `clasher-v4-data/cache/` without deletion. Leased caches must move off or be
deleted by 2026-10-10 05:30 UTC (within one day of the current lease end), earlier
if a changed lease/reclaim requires it. Prefer moving/retaining evidence.
Use `~/.local/bin/fleet-console-users`, which excludes our own SSH fleet monitor,
for console-cap checks. The earlier 03 watcher stop remains historical evidence.
Full admitted train/validation cache construction is now authorized; no heldout
payload access or frozen registration change is authorized by this decision.

Current pilot density projects ~97 GB for the audited population per copy.
Per-host budget/free-space guards, frame-weighted match allocations, atomic
checksum-verified fan-out and completed-match resume are implemented. Budget
tests passed 20 checks on 16, wrapper 3446999 / child 3447001, exit 0.
**Full-cache decode jobs**, both launched 07:32 UTC through lease wrappers:

| Host / label | Supervisor / child | Work |
|---|---|---|
| 16 / v4-cache-full-20261008-16r1 | 3447257 / 3447259 | PASS / exit 0 at 07:36:02; partition 0/2 |
| 18 / v4-cache-full-20261008-18r1 | 974710 / 974712 | PASS / exit 0 at 07:35:13; partition 1/2 |

Both migrate retained pilots into `clasher-lease/data/v4-cache/`, reuse all five
pilot checksums, and retain failed attempts inside that budgeted root. 18 stages
the full admitted train/validation source; 16 stages partition media. Source
stage receipts and final build receipts use each label under `clasher-lease/jobs/`.
Together these cover the **183-match, 325,999-frame** staged snapshot. Each used
24 decoders, peaked at 26 total processes and about 10.2 GB RSS. Each uses a 280 GB build ceiling, the approved
300 GB host ceiling for copying, and a 200 GB free-space floor. SIGTERM stops new
match submissions and lets current commits finish; completed matches resume with
checksums under a fresh label. Aggregate equality and full-replica verification
are pending the copy manifests.

Active gather jobs: **01 / v4-cache-gather-20261008-01r1**, wrapper **3536190**,
started 07:37:36, imports 16 then 18; **18 / v4-cache-gather-20261008-18r1**,
supervisor **977063**, child **977066**, started 07:38:23, imports 16. These copy
only complete immutable matches, checksum each destination, and then verify the
entire 183-match snapshot manifest. Do not duplicate a gather or write its cache.
18's follow-on label audit **r6** passed at 07:36:48 (976542 / 976544): 411,626
contradictions / 2,918,547 rows in 163 train + 20 validation; no new cleaning-code
change. See LABEL-AUDIT.md extension. Full-population GPU throughput remains pending.

01 has 88 owned Python workers, so avoid
adding bulk decode there while imitation occupies it. Hub transfer initially waited
for its `who` session to clear, then passed the runbook's Python-worker check
and completed via fleet_run (label `v4-cache-hub-copy-20261008-r1`, wrapper
3521392, exit 0). Do not assume that headroom persists for the next job.
01/03 are busy with imitation CPU work; do not stop another worker's processes.

Recent labels below use the host-local `clasher-lease/jobs/` log, launch PID and
`.exit.json` receipts. PIDs are historical: verify start/command before signals.

| Host / label | Supervisor PID | State |
|---|---:|---|
| 16 / v4-stage-audit-20261008-r1 | 3411060 | complete, exit 0 |
| 16 / v4-label-audit-20261008-r3 | 3428394 | complete, exit 0 |
| 16 / v4-cache-pilot-20261008-16r1 | 3422308 | complete, exit 0, four processes decoding |
| 18 / v4-cache-pilot-20261008-r1 | 944143 | equality failed, retained |
| 18 / v4-cache-pilot-20261008-r2 | 946906 | complete, exit 0 |
| 18 / v4-cache-verify-train-20261008-r3 | 952025 | complete, parity + 64-step pilot |
| 18 / v4-cache-parallel-benchmark-20261008-r1 | 955747 | complete, 128 steps |
| 18 / v4-prefetch-parity-20261008-r1 | 959531 | complete, 32 exact cases |
| 18 / v4-cache-copy-resume-20261008-r1 | 962887 | complete, five caches on 18; resume test passed |
| 16 / v4-label-audit-20261008-r5 | 3434454 | complete, exit 0; 62,697 coherent visible/nondeploying rows |
| 16 / v4-final-label-cache-tests-20261008-r1 | 3439357 | complete, exit 0; 14 assertions |

Resume cache construction through a fresh lease label with the same completed
cache root; completed files are checked, partial attempts retained. Budget
includes incomplete bytes. Resume T7 via identical flags plus `--resume`, only
after old process exit. Checkpoint/source/options must match. Latest tested
four-match checkpoint: `18:.../data/v4-resume-test-r1/model/`; do not use it to
initialize formal fitting. All formal initializations remain unchanged.

T3 schedule **Clasher v4 Phase A: bounded 15-minute checks** is bound to this
thread, next initially 06:42:19 UTC, deadline **18:08:27 UTC** (12 h from first
inspection). It must delete itself at deadline/completion. Receipt-only one-shot
checks live in `l1/phase_watch.py --once` and `l1/receipts/phase-polls/`; they skip
duplicate polls within 15 minutes. A briefly launched 03 watcher, label
`v4-phase-watch-20261008-r1`, wrapper 3494170 / worker 3494183, was stopped by
SIGTERM to the verified owned worker after noticing its interactive-session cap;
exit 0, 06:26:58 UTC. No standalone fleet watcher remains.

Remaining: extend/fan out the approved full cache as admitted
matches arrive, verify T1 completion, fresh T6/T7 24x400 fits, validation-only
selection/calibration and seal, complete the v4 scorer, then the one authorized
heldout opening. Mac/T5/T8 endpoints remain external dependencies. `l1/RESULTS.md`
contains every §5.1 gate with **BLOCKED / not measured**, not fabricated numbers.
The synthetic formal-admission assertions also passed (five checks, child exit
0); its lease wrapper marked `stopped` on a post-exit descendant check, so this
is recorded separately rather than called a clean wrapper completion.

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
hashes + evidence of either coverage (>=20 heldout matches/1,500 opponent events)
or the registered collection cap are required; cap-only coverage remains FAIL.
Then fresh T6 24x400 and T7 24x400 fits. Selection remains validation-only; the full
v4 scorer, model-selection seal and later authorized Mac evaluation are pending.
There is no automatic heldout job. Export handoff is `l1/EXPORT.md`.
