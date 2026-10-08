# T6/T7 results — formal evaluation remains blocked

## Current formal fitting status, 2026-10-08 17:34 UTC

Both formal fits have completed: T6 epoch24, seed6107; T7 all24x400 updates,
seed6108, all513 training matches. Both have SHA-verified checkpoint backups on04.
T7 final checkpoint SHA `e5d1acd124158dc9410a1f10bb1aaa51b180bc2abd9547da27e66a8da62f7e9c`.
T6 validation inference is complete (53392 frames,33.721860 fleet FPS,
p9534.168273ms excluding capture); validation scoring/selection remains active.
T7 passed full fit admission and launched its first complete-validation cell
(epoch1,event0.5,body0.1) at17:43:30; it is initializing the cache union. Selection, calibration and a selection seal are still
pending. No heldout payload has been opened; every unmeasured §5.1 gate remains
BLOCKED. Historical preparation notes below are superseded by this status.

| Training data rate | Measured windows/s |
|---|---:|
| Historical on-the-fly H.264 baseline | 1.282 |
| Full formal cached9600-step loop | 13.862772 |
| Same-run GPU optimizer steps alone | 19.769086 |

Cache speedup10.813x; full loop70.12% of same-run GPU rate. Mean loader wait and
transfer10.105862ms. The692.502169s loop includes periodic checkpoint writes and
logs but excludes initial source/cache verification and final backup. Parameter
population differs from the historical baseline; same-run GPU ratio is reported
separately. All577 train/validation caches retain10,420 exact1% checks with zero
mismatches and1,154 payload SHA checks. Evidence: receipts/formal-20261008/
t7-formal-throughput.json, t7-fit-complete.json and t7-fit-exit-backup.json.
The4.435532ms repeated-feature CUDA p95 excludes the full runtime and emulator;
it cannot pass the Mac gate.

## Historical pre-formal cache and label work, 2026-10-08

Final population preparation (16:06): **577 train/validation matches,1,019,054
frames,1,154 payload hashes,10,420 exact checks,zero mismatches**. Matching final
label audit:1,307,222 contradictions;544,623 generation disagreements resolved,
72,684 parent/child hints,276,020 non-HP hints,413,895 masked. Same cleaner.
28,123 accepted train/validation events mapped;zero unenclosed;empirical bracket
p95 255.849433 ms is uncertified and is not model execution-error p95.
Coordinator confirms collection stopped on coverage:641 receipts,64 heldout,
1,520 opponent events. Poll schedule deleted. Genuine producer completion
artifacts arrived in the coordinator pool mirror at16:44; formal admission
now passes01/09/15. T6
conversion completed577/577 with exit0 at16:36:25. Corpus relocation under the
approved15 cache root passed, including1,154 internal aliases and19.733 GB
projected use within20 GB. All failed attempts retained. Body scorer preparation
passes45 synthetic checks; no real body threshold is selected. T6 formal fit15r2 completed24 epochs; its weights were SHA-verified on04.
Validation failed before predictions on missing dill; exact dependency installed
and validation-only continuation launched (19001/53392 frames at17:26). T7
formal training is active on09 (4144/9600 updates at17:26). No completed formal selection,calibration,seal or heldout evaluation.

15:45 preparation completion: **559 train/validation matches,986,361 frames,
1,118 payload hashes,10,085 exact checks,zero mismatches**.03 retry exit0; all
failed attempts retained. Matching559-label audit:1,266,027 contradictions,
528,009 generation disagreements resolved,70,622 parent/child hints,269,157
non-HP hints,398,239 masked. No same-tick ID/field or rich-track identity changes.
Same cleaner/amendment03. Both09/15 have all559 inputs. Fresh formal fits and real
selection/calibration still pending; all formal gates BLOCKED. No new throughput
measurement: prior433-match pilot remains10.054579 windows/s versus1.282 uncached.

15:41 preparation: both09/15 now have559 pinned train/validation input sets.
03 cache extension retry active after a per-match space-guard failure; prior
successful full verification remains533/9,655 exact checks, no partial count
substitution. Aggregate allocation guard fixed and7 concurrent tests passed;
formal-union admission/provenance22 checks, file-backed admission11 checks and
replay/scoring/selection147 regressions passed. No real formal fit or new GPU/
quality/gate measurement. Latest labels536/timing496 unchanged.989 GB reserved;
all failed data/receipts retained. All formal gates BLOCKED; heldout unopened.

15:14 GPU reassignment preparation: T7→09, T6→15;01 GPU reserved forT5.
Both533-match source snapshots staged and verified.09 additionally has71 copied
cache shards,53.915 GB,142 payload hashes and1,235 existing equality checks preserved.
15's converter staging retry passed after handling an optional observation-skip
file; failed attempt retained.37 budget +13 allowlist +14 lifecycle tests passed;
a tiny15→01 checkpoint backup passed destination SHA verification. No formal fit
or new quality/gate metric. Checkpoint/exit supervisor is prepared; full T7 union
integration remains pending. Heldout unopened; all formal gates still BLOCKED.

14:52 preparation: cache **533 matches /944,416 frames /9,655 exact checks /
zero mismatches**, 1,066 file SHA checks; 29 newly decoded on 03, 84 reused.
Label audit **536 matches**, 1,217,041 contradictions: 507,460 generation issues
resolved, 69,424 parent/child hints, 258,568 non-HP hints, 381,589 unresolved/masked.
Same amendment03 cleaner; no new label rule. Calibration verification preparation
passed **27 synthetic checks**, with no real calibration or body-selection seal.
All jobs exited 0; T11 still occupies 16/18. Every unmeasured formal gate BLOCKED.

14:45 engineering union GPU pilot **PASS**, 433 matches (349 local +84 remote;
71 on busy 16 excluded). Fresh 1×128 steps: **10.054579 windows/s**, versus
1.282 uncached (**7.843×**), and **78.23%** of the same run's 12.853232 GPU-only
windows/s (205.651710 encoded frames/s). Exact augmented/RNG/parallel parity:
**16/16 samples**, 8 local +8 remote. Mean loader wait/transfer 11.035985 ms.
Training-loop wall time 12.730518 s excludes roughly 10 minutes of initial full
SHA verification, metadata/parity preparation and other wrapper work; wrapper
wall time about 652 s. Both client/service exits 0. This is an engineering subset,
not a full-population formal result. Cache 504 / exact checks 9,111 / mismatches 0;
labels/timing 496 unchanged. No additional Phase A poll after the 14:27 skip.
All §5.1 formal/Mac/T5/T8 gates remain **BLOCKED**, with no heldout payload access.

**Formal T6/T7 fits and heldout evaluation have not run.** Final receipt-only
verification **15:45:24 UTC**:513 train,64 validation,64 heldout matches;
**1,520 heldout opponent events**,56,008.247 emulator-seconds (15.56 h).
Coordinator confirms collection stopped on coverage. Coverage count passes;
formal producer-artifact admission is still blocked because01's pipeline-state
is stale and its completion report/exit receipt are absent. The Phase A polling
schedule was deleted at15:45 UTC. Heldout payloads remain unopened.

14:19 preparation: **504 cached train/validation matches / 891,013 frames /
9,111 exact 1% checks / zero mismatches**, with 1,008 file hashes. Storage reservation
reassigned within 980 GB: 01/18 each 300, 16=230, 03=150 GB. Boundary tests 31 PASS.
No new GPU/validation or formal gate measurement. Label/timing audits 496 unchanged;
T11 still holds 16/18 locks. Current verified cache covers the 14:13 receipt snapshot.

14:04 preparation: **492 cached train/validation matches / 870,541 frames /
8,901 exact 1% checks / zero mismatches**, with 984 file hashes. Label audit 496
matches: 1,123,813 contradictions, cleaner unchanged. Timing audit maps all 24,246
accepted events without omission; empirical interval p95 **256.078362 ms** is
uncertified and is not prediction error. Event-selection verification preparation
passed 17 synthetic checks. No real selection/verification, combined replay,
calibration, new GPU rate or formal gate measured. T11 still holds 16/18 locks.

13:47 preparation: receipt-only poll **skipped** (<15 minutes since 13:29), so
counts above are unchanged observations. File-backed calibration candidate
preparation passed **19 new checks + 147 regression checks**. Candidate outputs
authenticate complete combined validation data but explicitly leave selection
provenance unverified and grant no seal or heldout authority. No actual model
replay/calibration or formal gate measured. Cache 470 / label audit 472 unchanged.

13:34 preparation: **470 cached train/validation matches / 830,624 frames /
8,493 exact 1% checks / zero mismatches**, with 940 file checks. Labels audited on
472 matches with 1,077,524 contradictions; cleaner unchanged. Combined per-card
and body replay configuration is implemented; **147 synthetic checks PASS**.
No actual combined replay, new GPU rate, calibration, seal or formal gate measured.
T11 continues to own both 16/18 workload locks. Reservations remain 980 GB.

13:27 preparation: **457 cached train/validation matches / 810,563 frames /
8,286 exact random-1% checks / zero mismatches**, with 914 file SHA checks. New
home03 shard: 37 matches, 62,775 frames, 27.684 GB payload, exit 0 at 13:26:46.
Reservations total980 GB (300each01/16/18 +80on 03). Both leased-host workload
locks now belong to T11 training. No new augmented GPU throughput measurement,
formal fitting or gate measurement. Budget/disjoint-planning tests: **50 PASS**.

13:02 preparation: explicit body threshold now flows through replay, scoring and
event-selection evidence; mixed-setting grids/sweeps fail closed. **120 synthetic
checks PASS** on 01. No real body fitting, replay, calibration or formal gate
measurement. Phase A poll skipped, so counts above retain the 12:42:57 observation.
T11 copies still hold both lease locks; cache remains at 420 verified matches.

12:49 preparation: cache still 420 matches; T11 holds both lease locks, so no
new builder/GPU probe. Hub label audit passed on **433 train/validation matches**:
982,879 contradictions / 7,052,726 rows, unchanged cleaning rule. Later timing
snapshot **435 matches, all 21,273 accepted events mapped**, zero omissions;
empirical interval p95 256.981707 ms is uncertified, not prediction error.
Validation-selectable body confidence is now exposed at runtime; 15 synthetic
pixel-stream checks PASS. No threshold fitted or formal gate measured.

12:36 preparation: **420 cached matches / 747,788 frames / 7,645 exact checks**,
zero mismatches. The previous 404-match union's real probe passed all 1,840
raw/model comparisons; six-thread data-only rate **98.489652 windows/s** over
128 T16 windows (1.299629 s), excluding 423.130113 s SHA initialization and parity.
This is a short warm data benchmark; augmented/GPU rate is unmeasured. Engineering
trainer connection prepared; four formal-size/subset rejection tests PASS on 01.
GPU benchmark and next label audit wait for T11's locks on 16/18; failed pre-launch
EAGAIN receipts retained. Last completed label audit: 404 matches. No formal fit.

12:18 preparation: **404 matches / 716,916 frames / 7,330 exact checks**, zero
mismatches, 329,826,597,116 payload bytes across disjoint manifests. Cache union
routing passes 39 synthetic checks; real union probe preparing, no training
integration yet. Audit: 921,243 contradictions / 6,599,973 rows, cleaner unchanged.
Phase A poll skipped; previous observed counts unchanged. All formal gates BLOCKED.

12:07 label audit: **390 matches, 896,274 contradictions / 6,392,649 rows**;
unchanged cleaner, zero track-ID or same-tick association mismatches. New unique
cache extension runs on 16; latest verified union remains 390.

12:06 transport probe: **1,366/1,366 raw/model sample comparisons exact** across
16→18 on the 41-match extension. Six-thread, 128 T16-window transport loading:
**33.245273 windows/s**, 50% raw / 50% model inputs. Data-only engineering result;
no GPU fit, full-union training integration or gate claim. Both wrappers exited 0,
tunnel and server stopped. Original decoded-source equality remains 7,093 checks.

12:05 update: verified disjoint snapshots cover **390 matches / 693,947 frames /
7,093 exact checks, zero mismatches**, 318,798,526,069 payload bytes. Real
cross-host transport parity/throughput probe runs on 16→18; no result yet.
Full trainer integration, final-population preparation and formal fitting remain
BLOCKED. No heldout opening.

11:52 update: the unique builder's final verifier was missing on 16 (exit 2
retained); verification-only repair passed without decoding again. Disjoint
manifests now cover **374 matches / 665,624 frames / 6,805 exact checks, zero
mismatches**, 305,893,142,061 payload bytes. A complete replica exceeds the
300 GB host cap. Further unique extension runs on 16. Read-only block transport
passes 16 synthetic loopback checks; real cross-host parity/throughput and trainer
integration remain pending. Label audit: 851,722 contradictions / 6,122,045 rows,
same cleaner. No new Phase A poll (duplicate skipped), formal fit or heldout read.

11:32 update: **349-match cache independently verified on 01/18**, 698 hashes
and 6,410 exact checks each, zero mismatches. Full-copy growth pauses before the
300 GB/host caps. A receipt-pinned extension job on 16 now builds only matches
beyond that verified snapshot; 17 synthetic planner checks pass (child exit 0,
wrapper descendant-exit race recorded as stopped). No data deleted or new host
reserved. Full-population training needs verified access across shards; the
reader/throughput work is pending. No formal fitting or evaluation has run.

11:18 update: **349-match cache verified on 18**, 698 hashes / 6,410 exact checks,
zero mismatches; hub gather still active. Host 18 cache root 291,831,184,057 bytes:
further full-population cache access needs a layout within the existing per-host
and aggregate limits. New even-partition extension runs on 16. Guarded validation
selection orchestration passes 14 synthetic checks; no real model selection,
calibration, seal or formal gate measurement. Heldout remains unopened.

11:05 update: **325 cached matches independently verified on 01/18**, 650 hashes
and 5,962 exact random-1% checks each, zero mismatches. New 349-match / 627,343-frame
snapshot decoded and audited; gathers RUNNING. Label contradictions: 804,414 /
5,760,111 rows, unchanged cleaner. Timing audit maps all 17,480 events, empirical
interval p95 258.671 ms (uncertified). Per-card threshold preparation passes 17
synthetic checks; real selection/calibration and all formal endpoints remain unrun.
18 build allowance 295 GB is within the approved 300 GB host cap; next full copies
are nearing that cap. No new storage authorization is assumed.

10:47 preparation: complete 24x9 validation-grid provenance/ranking helper passes
28 synthetic checks on 16 (wrapper PASS). No real model selection or calibration;
325-match gathers remain active, verified snapshot remains 312. Phase A one-shot
skipped the duplicate; collection counts above retain their original timestamp.

10:40 update: **312-match cache verified independently on both 01 and 18**,
624 hashes and 5,720 exact random-1% checks each, zero mismatches. Next snapshot
**325 matches / 583,338 frames** decoded; gathers RUNNING. Label audit has
751,125 contradictions / 5,352,999 rows, same cleaner. Timing preparation maps
all 16,298 accepted events; interval p95 259.167 ms, maximum 843.163 ms,
uncertified. Duplicate Phase A poll skipped; no real model/heldout endpoint run.

10:32 update: **312-match / 559,559-frame cache verified on 18**, 624 payload
hashes, **5,720 exact checks, zero mismatches**, 257,035,901,870 payload bytes.
Hub r8 gather remains active; its verified snapshot is still 287 matches.
Fresh disjoint builders are running on 16/18. No new real model replay, selection,
calibration or formal endpoint measurement. Host 18's total cache root is
259,432,753,594 bytes; existing 280 GB build / 300 GB host guards remain binding.

10:19 update: 287-match snapshot verified on **both 01 and 18**, 5,297 exact
checks / 574 hashes each, zero mismatches. The **312-match / 559,559-frame**
extension is decoded and audited; gathers RUNNING. Label audit: 712,177
contradictions / 5,122,516 rows, unchanged cleaner. Timing audit maps all 15,593
accepted events; interval-width p95 259.256 ms, max 843.163 ms, uncertified.
Guarded file-backed validation scoring passes 12 synthetic checks with wrapper
PASS; no real formal model replay/scoring, selection or gate measurement yet.

09:49 update: **268 matches / 480,610 frames verified on 01/18**, 536 payload
hashes each, **4,915/4,915 exact checks**, zero mismatches; payload 221,330,665,879
bytes. Next 287-match / 518,276-frame snapshot decoded and label-audited, gathers
RUNNING. Audit: 655,450 contradictions / 4,729,632 rows; unchanged cleaner.
Timing preparation passed 32 synthetic tests. Empirical frame-bound audit maps
14,379/14,393 accepted train/validation events; **14 unenclosed** (12 train,
2 validation), retained as a scoring-preparation blocker. Interval-width p95
259.777 ms, maximum 843.163 ms; this is uncertainty width, not prediction error.
No timing or other formal gate measured.

10:03 update: 287-match cache verified on 18 (**5,297 exact checks, zero
mismatches**, 574 payload hashes); hub gather remains active. Phase A one-shot
skipped as a duplicate, so collection counts above are unchanged. Timing edge
handling now uses the valid observed lower bound in terminal-tail frames and
upper bound in leading frames, without treating either as a two-sided bracket.
Same 287-match timing audit now maps **14,393/14,393 events**, zero omissions;
interval-width p95 **259.783 ms**, max **843.163 ms**, still uncertified.
41 synthetic checks and final full audit pass. Earlier failed strict-clamp audit
retained. No prediction scoring, selection or formal gate measurement occurred.

09:26 update: **253 matches / 453,896 frames** are fully verified on 01 and 18:
209,258,933,040 payload bytes, 506 hashes each, **4,642/4,642 exact random-1%
checks**, zero mismatches. Next snapshot **268 matches / 480,610 frames** is
decoded and label-audited; its full-replica gathers remain RUNNING. Latest audit:
613,699 contradictions / 4,354,195 rows, same pre-training cleaner, no new fix.
Guarded validation pixel replay is implemented with 19 passing synthetic checks;
test child exit 0, wrapper stopped on descendant-exit race. No real replay or
selection measurement yet; all formal gates remain BLOCKED.

09:30 continuation: Phase A poll skipped as a duplicate; counts remain 09:17:53.
Completion-journal scoring adapter added, with 33 synthetic checks passing;
child exit 0 and wrapper descendant-exit race retained. Both 268-match gathers
remain active. No real validation/heldout endpoint was measured.

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

The same label audit extended to this snapshot: 2,918, 547 object rows and 411,626
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
audit of 48 decision files / 23, 546 intervals / 830.632 ms p95 was an incorrect
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
247,456 catalog-generation disagreements resolved, 30, 548 parent/child hints,
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

Validation checkpoint,
threshold and isotonic selection with a source/checkpoint seal; a full v4 heldout
scorer and T5/S3/T8 contract integration; authorized Mac CoreML conversion and
emulator-on replay. Every §5.1 gate remains UNMEASURED/BLOCKED. RUNBOOK.md prepares
fail-closed formal fitting commands, not an automatic heldout evaluation.

Post-shakedown changes only improve completed-checkpoint recovery and stamp runtime
availability after fusion/serialization and normalize native body aliases before
v3 spawner suppression. Exact measured model/trainer sources
are retained under receipts/, with hashes matching the shakedown manifest.
