# T6/T7 progress

Updated 2026-10-08 08:39Z. 225-match snapshot verified/audited on 18; hub gather RUNNING; heldout unopened.
Code/docs/compact receipts live on 127x05; new decode/audit/tests/training pilots
run detached/nice on leased 16/18. No Mac/excluded host access, commits or deletion.

## Current continuation: cache and label cleaning

Formal work is **not launched**. Latest receipt-only poll (08:23:55 UTC): 200 train,
25 validation and 24 heldout matches; heldout 572 opponent events; 6.16 recorded
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
Historical five-match pilot: **14,592 frames, 5,910,676,788 bytes, 149/149 equality checks**.
Originally 16 had four matches and 18 had all five under
`clasher-lease/cache/v4-pixels-r2/`; both have since migrated into the approved
`clasher-lease/data/v4-cache/` roots and expanded, as recorded below.
All five were copied to 01 at 07:01 UTC, with ten payload hashes and all five
indices verified. The hub cache was subsequently renamed, preserving bytes, to
**01:/mpac/sdicks02/repos/clasher-v4-cache/** at 07:31 UTC (migration exit 0).

Throughput: old **1.282 windows/s** → cached single-thread 3.277 → six preparation
threads **12.476 windows/s**, GPU-only 16.803, loading wait 9.95 ms. Four-train-
match resumed pilot: **11.513 windows/s**, GPU-only 15.501. The full staged training
snapshot is now measured separately: **163 train matches**, 128 steps / six threads,
**10.713 windows/s**, GPU loop **15.362**, loading wait **16.818 ms**. Eight-thread
comparison was slower: **10.501 windows/s**, GPU loop 15.729, loading wait 20.650 ms.
Keep six threads. Hub copying from 18 overlapped both probes; both were engineering
fits with one-time data/hash initialization excluded from training-loop rate.
Exact augmented-sample parity: 16/16. Historical sampler/parallel
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
`/mpac`. Subsequent user approval additionally caps **aggregate caches at 1 TB**;
both limits apply. Current reservations: 300 GB each on 01/16/18 (900 GB total,
100 GB headroom); no fourth writer host before reassignment. The dated
`l1/STORAGE-AMENDMENT-20261008.md` records the storage-only authorization.
Approved homes: `clasher-v4-cache/` on 01/03/04/08; leased cache root:
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

Completed hub gather: **01 / v4-cache-gather-20261008-01r1**, wrapper **3536190**,
started 07:37:36, **exit 0 at 08:04:25**, imported 16 then 18; **18 / v4-cache-gather-20261008-18r1**,
supervisor **977063**, child **977066**, started 07:38:23, imported 16 and **PASS /
exit 0 at 07:49:20**. Host 18's full snapshot manifest verifies **183 matches,
325,999 frames, 149,926,468,048 payload bytes, 366 payload hashes, 3,334 exact
random-1% frames, zero mismatches**. Its full cache-root size is 152,319,323,681
bytes including the retained failed pilot. The hub independently verified the
same 183 matches / 325,999 frames / 366 hashes / 3,334 equality samples, with
149,930,334,386 bytes in its cache root. These jobs copied
only complete immutable matches, checksum each destination, and then verify the
entire 183-match snapshot manifest. Both gather jobs are complete; their output
manifests remain the immutable snapshot evidence. New incremental gathers require
fresh labels and their new stage inventories after the active builders exit.
18's follow-on label audit **r6** passed at 07:36:48 (976542 / 976544): 411,626
contradictions / 2,918,547 rows in 163 train + 20 validation; no new cleaning-code
change. See LABEL-AUDIT.md extension.

Completed engineering benchmark: **18 / v4-full-cache-benchmark-20261008-r1**,
supervisor **982534**, fresh output `clasher-lease/data/v4-full-cache-benchmark-r1`,
163 staged training matches, 128 steps, six preparation threads; **PASS / exit 0
at 07:55:22**, child 982556, peak RSS 11,878,289,408 bytes. The full snapshot
verification passed first; this is not formal fitting or selection. Concurrent
hub copying is recorded as a throughput-environment limitation if still active.
Eight-thread benchmark **r2** (986937 / 986954) also passed at 08:01:10, peak RSS
12,494,827,520 bytes; no performance improvement, retained in RESULTS.md.
Incremental **16 / v4-cache-extend-20261008-16r2** (3464944 / 3464947) passed at
07:52:48: nine new matches / 16,590 frames, cache-root bytes 89,989,166,950.
Completed incremental jobs, launched 08:03 UTC through lease wrappers: **16 /
v4-cache-extend-20261008-16r3**, supervisor **3467500**, partition 0/2; **18 /
v4-cache-extend-20261008-18r2**, supervisor **989422**, partition 1/2. Both use
24 workers; both **PASS / exit 0**, 16 at 08:04:51 and 18 at 08:05:18. Their
union covers every match in the new staged snapshot: **208 matches / 373,198
frames**, zero missing episodes. Cache roots before gathering: 16 = 94,076,176,088
bytes; 18 = 161,786,622,604 bytes.

Completed hub gather **01 / v4-cache-gather-20261008-01r2**, wrapper
**3546963**, exit 0; manifest at **08:23:26 UTC** independently verifies the same
208 matches / 373,198 frames / 416 hashes / 3,817 exact equality samples, with
171,143,435,254 cache-root bytes. GPU-host gather **18 /
v4-cache-gather-20261008-18r2**, supervisor **990718**, child **990720**, completed
**PASS / exit 0 at 08:16:26 UTC**. Its manifest verifies **185 train + 23 validation
matches, 373,198 frames, 171,139,010,394 payload bytes, 416 file hashes, 3,817/3,817
exact random-1% checks, zero mismatches**. Total cache-root bytes on 18 are
173,532,676,879 including retained attempts. Both gathers target
`v4-cache-extend-20261008-18r2-stage.json`; launched after both builders exited.
Do not duplicate those jobs or start a writer against their cache. Preserve the
183-match manifests as the fully verified snapshot used for throughput. After
gather exits, mirror compact manifests/exit receipts and extend later matches
through fresh labels. Full-population formal fits still wait for genuine T1 stop.

08:13–08:22 UTC continuation: receipt one-shots skipped duplicate polls; latest
actual Phase A observation remains 08:07:07 UTC. No heldout payload access or
duplicate cache job. Independent preparation added `l1/calibration_v4.py`:
one-to-one availability matches supply binary existence labels, duplicate
predictions are negative, per-card isotonic fits require 20 predictions, and
smaller/unseen cards use the pooled both-seat validation fit. Empty predictions,
non-validation episode declarations, malformed scores and mixed-in abilities
are rejected. It consumes the final selected/thresholded card-play stream;
authenticated replay, threshold selection orchestration and seal remain pending.
Synthetic checks **80/80 PASS**, including an exhaustive least-squares isotonic
oracle and the 19/20 support boundary: 16 / `v4-calibration-tests-20261008-r1`,
supervisor **3472679**, child **3472681**, exit 0 at **08:21:55**, peak two processes /
379,707,392 bytes RSS. No data opened for these tests. A direct wrapper invocation
was refused by filesystem execute permissions before launch; invoking the same
script through bash launched the sole test job. Frozen PREREG/split hashes remain
unchanged. Formal gates remain BLOCKED; these helpers do not authenticate input
provenance or create a selection seal.

08:24–08:33 UTC continuation: disjoint 24-worker extensions **16 /
v4-cache-extend-20261008-16r4** (3473473 / 3473475) and **18 /
v4-cache-extend-20261008-18r3** (994563 / 994565) passed at **08:25:40 / 08:26:36**.
16 staged/built 125 even-partition matches; 18 built 100 odd-partition matches
against a full **225-match / 404,396-frame** stage inventory. Each peaked at
26 processes and less than 7.5 GB RSS. Root bytes before gathering: 16
100,942,096,068; 18 180,794,101,591. These remain within the 300 GB/host and
1 TB aggregate budgets. Console helper returned zero and /mpac free space
exceeded 1.4 TB on each involved host at launch.

**Current active job:** gather **01 / v4-cache-gather-20261008-01r3**, wrapper
**3552321**, live at 08:37 UTC. Gather **18 / v4-cache-gather-20261008-18r3**,
supervisor **995614**, child **995616**, **PASS / exit 0 at 08:36:42 UTC**.
Both target `v4-cache-extend-20261008-18r3-stage.json`, launched 08:28 UTC after
builders exited. 18 verifies **200 train + 25 validation matches, 404,396 frames,
185,265,622,912 payload bytes, 450 file hashes, 4,137/4,137 exact random-1% frames,
zero mismatches**. Total cache-root size 187,659,839,436 bytes. Preserve the
208-match receipts; the new hub full-replica verification remains pending.
Attempted expanded label audit **18 / v4-label-audit-20261008-r7**, supervisor
995832, was refused by the wrapper's host-wide workload lock before any child
started (exit 1). **Resume under a fresh label only after gather exit.** Last
completed label audit at that point remained the 183-match r6; no cleaning-code
change. Sequential retry **18 / v4-label-audit-20261008-r8**, supervisor **998522**,
child **998526**, **PASS / exit 0 at 08:37:42**, 18 processes / 850,276,352 bytes
peak RSS. All 225 matches audited: **501,159 contradictions / 3,635,665 rows**;
210,896 catalog-generation disagreements resolved, 24,419 parent/child hints,
105,669 non-hitpoint hints, 160,175 unresolved/masked. Zero rich-ID changes and
zero ID/field mismatches among 31,472 contradictory same-tick joins. Same cleaner;
no new amendment or heldout access. See LABEL-AUDIT.md r8 extension.

Historical 08:27–08:33 gap preparation (source choice **superseded below**):
the base L1 PREREG names `l2/native/*/decisions.jsonl`. The new
`gap_schedule_v4.py` reads only those registered decision files, verifies finite
chronological capture-production timestamps and refuses missing/duplicate rows.
Source audit on 16 (3474269 / 3474272, PASS at 08:27:26) found **48 files,
23,546 intervals, p95 830.6318 ms**, minimum 41.1601, maximum 2,019.3520 ms.
This differs from the historical 610 ms public-frame summary; retain both facts,
do not replace the measured distribution with that summary or a Gaussian.
`gap_t6.py` now uses this source and seed-6109 cumulative arrivals. Schedules
retain original timestamps and arrivals for reuse on each arm's 20/10 FPS grid;
the existing v3 integer-ms boundary adapter is preserved separately. Final
schedule helper tests **19/19 PASS** on 16 (3476850 / 3476852, 08:31:56,
30,846,976 bytes peak RSS). Syntax compilation of the T6 adapter exited 0,
but the lease wrapper marked both short compile jobs stopped due to its
descendant-exit race; retained in INCIDENTS. No model replay or gap endpoint
was measured. Final population schedules, timing mapping, replay admission,
full selection and seal remain pending.

**08:35 UTC correction:** the preceding source interpretation overlooked
`PREREG-AMENDMENT-02.md`, which explicitly supersedes the base source path with
`native/pair-*/public-frames.jsonl.gz`. The amendment remains unchanged and
binding. The 830.632 ms sparse-decision measurement is **diagnostic only**;
it is not the registered gap distribution. No model replay or formal metric
used it. `gap_schedule_v4.py`, `audit_gap_sources.sh`, and the T6 diagnostic now
use all public-frame `timestamp_ms` intervals as amended; malformed/duplicate
frames fail closed. Raw interval/source hashes and the shared seed-6109 arrival
plan are retained before predictions. Audit/test label **16 /
v4-gap-source-audit-20261008-r3**, supervisor **3477942**, child **3477944**,
**PASS / exit 0 at 08:36:16**, five processes / 147,996,672 bytes peak RSS.
The amended source has **60,586 intervals, p95 exactly 610 ms**, range 7–2,075 ms;
**24/24 synthetic source/schedule tests passed**. This reproduces the historical
summary without changing the distribution. The mistaken decision-source receipts
remain preserved in INCIDENTS; they are not formal schedule inputs.
The 08:35 Phase A one-shot skipped the duplicate; latest actual receipt poll
remains 08:23:55 UTC. No new receipt read or heldout access.

Space planning: a full 183-match replica is 149.93 GB. Monitor actual growth;
the final collection is not guaranteed to fit a 300 GB full-frame replica.
The per-host/aggregate guards must stop before the approved limits; any further
storage optimization must preserve all training samples and exact parity.
Aggregate-budget regression r2 passed 22 checks (16, 3462490 / 3462492, exit 0).

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
