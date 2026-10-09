# ExIt round 1 B2/B3/B5

2026-10-09 10:52Z: **B2/B3/B5 accepted; generation running on03/04/08.** Own paths:
`imitation/exit_r1/` and this directory. Frozen T11 and model trainers untouched.

B2: eight-deck/four-opponent full-game matrix:6373gate-c byte-equal rows,
993scoredroots, exact submission-label -> d27queue -> physical game replays,
public events and final outcomes. Final full-v6 schema check on another terminal
game:826raw compact/public/D1/model-feature rows byte-equal, exact replay.
Teacher mmap/scalar equality32sampled real rows plus actual optimizer step PASS.
First measurement in<15min:4.59roots/core/s initialgame; mixed-deck matrix
**3.0699roots/CPU-s,19.7025emitted5tick rows/CPU-s** (323.46CPU-s). Expanded waits
are counted separately from roots. Acceptance receipts in `receipts/`.

B3: four tests PASS: ratio0bit-equal qualifiedT11 loss, all gradients, optimizer
result and updated parameters; soft gradients/WAIT probability aggregation;
mixed sampler/kill rules; optional value gradient/effective-batch normalization.
Explicit initial checkpoint parameter(v2selected or v1), teacher fraction,
soft-score temperature, rare-play weighting, optional value loss, atomic resume.
NumPy2teacher scalar rounding corrected in new adapter only. No GPU fitting.

B5: core63, one thread,1000proposer calls each at10/25/64entities including
feature building/top8. Worst p99 bywidth:192=14.916ms;288=17.979;384=27.552;
768=90.298. Only192meets<=15ms. Wider capacity arms are offline-only candidates.
Inputs synthetic;192uses released-v1 weights, others random architecture probes.
Capacity matched-row dev gain<.005 at25% kills the arm; no capacity training.

Generation: target **6Mroots combined**, ceilings03=4M,04=6M,08=4M. 04release
receipt T5PARKED_EXACT_CHECKPOINT_BACKED_UP_04_RELEASED SHA
f901710f... (full launch pins in receipts); explicit coordinator relay received.
All output data/source/native/manifest under each generating host:
`/mpac/sdicks02/jobs/clasher/exit-r1-20261009-r1/`. Completed games only are sealed,
with per-column SHA256 and root replay/input/source/native manifests.

- 03: supervisor2636618,46workers+spawntracker <=48,cores62–127,nice10/SCHED_IDLE.
- 04: supervisor2603056,94workers+spawntracker <=96,cores30–127,nice10/SCHED_IDLE.
- 08: supervisor3560459,94workers+spawntracker <=96,cores0–125,nice19/SCHED_IDLE.
  Cores126/127free; renewed cache2095380kept running. STOP drill fully cleared
  own supervisor/workers/tracker in1.409seconds; in-flight games expendable.

**Exact08stop path:**
`127x08:/mpac/sdicks02/jobs/clasher/exit-r1-20261009-r1/GENERATION.STOP`.
03/04use the same absolute stop path on their respective hosts. Touch only the
owned stop file; do not signal cache services or other workers. Exit evidence:
`generation/exit.json`. MemAvailable24GiB floor polled each second; any worker
failure stops its host. No leased CPU sims, no01jobs, no05heavy work, noMac.

Warm fleet at10:52:08Z: **375.13roots/s over127.01s**,148654completedroots,
960052pollrows, **historical10M ETA7.30h; superseded by6Mtarget**. This observed rate supersedes
the720roots/s extrapolation. All234workers live;24GiB memory floors hold.
Receipt `receipts/fleet-warm-rate.json` (later samples update the live controller).

Light05stdio/network controller3501473,nice19/SCHED_IDLE, polls every30seconds,
writes all three own STOPfiles at6M combined roots, verifies per-host exits.
Control output `/mpac/sdicks02/jobs/clasher/exit-r1-fleet-control-20261009-r1/control/`;
`progress.json`, `observations.jsonl`, eventual `exit.json`. It is stdlib-only;
no simulations, Torch, data copying or heavy work on05. First launch failed an
unneeded NumPy import immediately; corrected lightweight retry is the sole live
controller. No simulation run restarted. 03/04pinned supervisors predate the
08ops-only receipt/stop-reason refinements; launch manifests retain exact hashes.

Code commit/push and final source SHAs pending below. Data never committed.

Coordinator allocation: 03 <=48 processes while E1 runs, <=96 after E1;
04 <=96 only after the coordinator relays T5 parked/release evidence. 08 optional,
<=96 nice19, stop file and <=5 minute complete vacation. No 01 generation yet.
All execution nice>=10/SCHED_IDLE/setsid; MemAvailable floor 24 GiB.

Student screen: play recall below 50% of teacher kills the arm; fallback must
beat v2 fallback. Human anchor and teacher rare-play weighting are explicit.
Capacity scan: kill dev-NLL gain <0.005 at matched rows at 25% of schedule.

2026-10-09 10:59Z: live fleet controller target6,000,000 verified, PID3501473.
299845 roots /1932595 pollrows;120s warm371.04roots/s, ETA4.27h (~15:15Z).
Latest steering adds B3/B4 student screen infrastructure, ready before6M;
coordinator retains statistical-plan freeze. GPU destinations01(afterT11),09,
13/14/15. No GPU job launched. Source assembly/packing will avoid per-game mmap
FD exhaustion. Expansion after E1 is capped near64 physical-core workers/host.

2026-10-09 11:35Z: B3/B4 infrastructure ready:8 tests PASS (5.036s on03,
nice19/SCHED_IDLE), real v6 pack feature/target/ragged equality and SHA tamper
rejection, all-WAIT/WAIT-ratio/CI kills, paired identity/execution-freeze guards.
E1 native/student runtime initialization PASS. T11 EMA confirmed decay0.999;
2000warmup/8192batch/AdamW3e-4 defaults fixed, final-step EMA. Dataset packing
avoids thousands of per-game mmap descriptors. No GPU fitting or reporting games.
Approved STUDENT-SCREEN-PLAN.md SHA
`d98fdd74f2c59a23806aae1cfd85852016796d40f6d8d71e2ed6b3c9171b6138`
remains byte-unchanged, waiting for coordinator joint plan/seed-audit freeze.
Seed inventories zero overlaps on all reachable originals;03 archive supplement
still finishing. 02/07/18 unreachable; coordinator explicitly accepts committed
formula ranges plus03archive/04copies/01mirrors/gates-bc archival inventories.
Full inventories under /mpac/sdicks02/jobs/clasher/exit-r1-seed-audit-20261009-r1
on inventoried hosts; no raw inventories or data enter git.

2026-10-09 11:45Z: **Seed audit PASS and B4 joint-freeze inputs delivered.**
680352 files inventoried on ten reachable hosts plus archive/mirror supplements;
2872 reporting/smoke/helper integers, zero overlaps and unresolved errors.
02/07/18 not directly inventoried (No route to host); coordinator-approved
exploration coverage is committed formula ranges +03archive/04copies/01mirrors/
gates-bc inventories. Full raw inventories stay off git, with SHA pointers in
receipts/student-seed-audit.json. Audit SHA
`3e2764ad69a2a1c05ddc93dc27770261856517e231341eb1881e1b0a7e5c0986`.
Plan SHA remainsd98fdd74...; EMA decay0.999. Reviewed3045committed seed files,
248base/count declarations and407seed/base assignments. Conservative prior
upper4503600127370496 leaves880000000to first screen reporting seed.
No reporting games or GPU fitting. Own new smoke+0/+1 only: terminal H2H at
4365ticks,48.710CPU-s; E1deadline/proposer first-decision integration PASS.
Foundation code and acceptance receipts committed/pushed **39b6adf6**.
Before fitting, student adapter now writes input/recipe/source SHA evidence;
resume checks source/input pins. No scientific loss or frozen T11 change.

2026-10-09 19:49Z: Frozen student screen execution began under coordinator's
STUDENT-SCREEN-FREEZE-20261009.json (787e4c6a...). All generators exited cleanly.
The controller cutoff prefixes admit exactly49,577terminalgames,6,009,681roots
and38,738,534rows;40stop-drain games are excluded. Every source-game SHA was
verified by the frozen packer. Corpus manifest SHA
`1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b`.
Receipt `receipts/student-screen-pre-fit.json` was written19:48:54Z before any
fitting, pinning all1413runtime source files, E1native, explicitv1step22552,
width192, identical qualified human inputs and the unchanged recipe.
Frozen8tests PASS, including real packed-game equality and seal tamper rejection.
Data remains host-local under `/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1/`.
SHA-checked corpus copies are proceeding to01/04/09. Three GPU arms will overlap;
reporting uses03/04/01 only and leaves08entirely free for perception.
Task-localNumPy2.3.5 matches teacher serving; qualifiedcu118Torch2.7.1 is unchanged.
Operational scripts and setup retries are documented under
`operations/student-screen/` and `receipts/student-screen-ops.json`.
No reporting outcomes or fitting were observed before these pins.

### 2026-10-09 19:56Z — frozen student fits launched

Exact frozen-cutoff corpus SHA `1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b` verified across all 71 packed files on 01/04/09. Pre-fit pin published in `b6b39380`; operational compatibility/startup fixes in `f48d865d` change no frozen recipe or scientific source. S-mix on 01 and S-teacher on 04 launched at 19:54:01Z; S-human on 09 admitted at 19:54:37Z under existing versioned capture-extension supervisor (Oct11 04:30Z checkpoint deadline, declared four processes/46GB PSS). Old current supervisor refused before workload admission due to historical Oct9 deadline; coordinator authorized the extension wrapper. 08 remains unused. Home reporting controller on03 waits for all three step4883 final EMAs. Launch evidence: `receipts/student-fit-launch.json`.

### 2026-10-09 20:34Z — loader repair and owned GPU continuation

Five-minute baseline rows/s: S-mix859.6, S-teacher2148.5, S-human1272.2. Dated loader6 amendment `b839f178` preceded all reporting outcomes. Six ordered complete-step workers, prefetch4, no random mmap advice; all three passed two-step serial/parallel GPU replay with model/EMA/optimizer/scheduler/cursor/all RNG states bit exact. Parent affinity118/119/126 (loaders120–125, Torch scientific threads1) approved and recorded.

S-human09 attempted-step239 OOM:130 unsaved completed updates archived/accounted, exact recovery from108. Frozen ExIt sampler remains unsorted; qualified T11 main sorts each effective batch by entity count before micro slicing, explaining larger rare first7168 micros without a recipe change. Coordinator directed owned08 continuation; existing matching v2human store and copied corpus undergo fresh SHA checks before resuming. No expandable allocator change. S-mix01 completed239 then stopped because the wrapper incorrectly applied the leased8GiB reserve to an owned GPU; exact239 continuation launched with owned guard scope corrected. S-teacher04 exact510 continuation launched. Checkpoint cadence250 (S-human200) is operational; final EMA selection, recipe and all reporting seeds remain unchanged.08FIT.STOP bounds reclaim to≤5min. Reporting remains unstarted and waits for all final EMAs.

### 2026-10-09 20:41Z — S-human exact resume on owned08

Fresh08 checks passed all71 packed files and all63 human training columns, publicmask, init step22552/static buffers. S-human resumed exact checkpoint108 SHA `7a8d80ede64326d810b1e39ac33dc17d9df8f5b42446a941c569324d46ea1445` at20:38:45Z, trainerPID1602437, nice19, parent118/119/126, loaders120–125, checkpoints200. No allocator change. The watchedFIT.STOP preserves≤5-minute reclaim. Migration receipt: `receipts/student-owned-migration.json`. Reporting controller r5 on03 waits for final EMAs from01/04/08 and then uses home CPUs03/04/01. Discarded09 attempts retain GPU/CPU costs in final accounting. Five-minute post-affinity measurements are in progress.

### 2026-10-09 20:46Z — allocator qualification after owned08 OOM

Owned08 also OOMed attempted-step239:41.70GiB allocated plus4.38GiB reserved/unallocated. Checkpoint200 preserved92 useful updates;38 unsaved updates archived underowned08-oom-20261009, with full segment cost recorded. Dated `receipts/student-allocator-amendment.json` authorizes expandable_segments:True only after default/expandable two-step exact-state proof from200, both loader6. No sorting, micro or math change. Coordinator additionally pre-authorized S-human micro3584 with unchanged effective8192 and row order only if expandable still OOMs; that fallback has not been applied. Reporting outcomes remain unobserved. Controller r6 on03 will collect allocator proof and account for both failed segments.

### 2026-10-09 20:48Z — allocator replay bit-exact PASS

`receipts/student-allocator-qualification-S-human.json`: two exact-state GPU updates201/202 from checkpoint200 compare default versus expandable allocation, both loader6. Model/EMA/optimizer/scheduler/config/cursor/hashes/provenance and all RNG states bit equal. Exact checkpoint200 SHA `c395b0cb5f01375d62b7c7c0a0c2d19781d4835a5606988bebe88b006b5bb94f`. Production S-human08 resumed200 with expandable_segments:True; scientific micro7168 unchanged. Micro3584 fallback unused. Continuation timer every15min, next21:02:31Z, bound to this worker thread; disable after final reporting/commit. Timer ID `scheduled-task:command:mcp:28249cfe-4f07-46c4-a8cb-64c4b5ebf42c:schedule-task:exit-r1-student-monitor-20261009`.

### 2026-10-09 20:56Z — dense239 passes with authorized micro3584

Expandable allocator two-step proof passed but dense239 failed with CUDA driver invalid argument. Another38 updates archived/accounted. Coordinator-preauthorized S-human-only micro3584 runtime amendment resumed untouched200 with default allocator, same8192 rows/order/global denominators; floating-point summation order changes and is disclosed. An inherited self-imposed46GB PSS tree guard clean-saved232 with115.7GB MemAvailable. V3 operational amendment scopes treePSS cap to leased hosts; owned24GiB memory floor remains. Exact232 continuation PID1698898 passed239 and reached256 with≈15GiB GPU free. Loader/row arithmetic unchanged by PSS scope. V3 inherited fit_runtime_sha256 is historical; actual micro adapter is pinned in micro amendment/continuation receipts. Five-minute steady rate pending; reporting remains unstarted.

### 2026-10-09 21:01Z — five-minute steady rates

`receipts/student-loader-performance.json` pins≥300-second completed-update windows after20 warmup updates. S-mix01:859.6→3656.1rows/s,2.240658s/step,remaining2.434h; S-teacher04:2148.5→4234.4,1.934644s,remaining1.897h; S-human08:1272.2→4655.4,1.759688s,remaining2.168h. Optimizer fractions99.1%/99.8%/59.8%; teacher/mix now step-bound, human retains40% loader stalls despite loader6. Human exact232 continuation uses authorized micro3584/defaultallocator, passeddense239, saved400 and reached448. Micro amendment/continuation pushed6371fa06, allocator proofbdae8ab0. Every attempted/discarded GPU/CPU segment is retained; reporting remains unstarted until all final4883 EMAs. The15-minute continuation timer remains active, next21:02:31Z.

### 2026-10-09 22:34Z — staged reporting under frozen pairing

Coordinator authorized staged cases22:19Z. Frozen plan has no interleaving or simultaneous requirement; private per-seat policy RNG preserves the seed/deck/seat schedule across partial checkpoint sets. Immutable stage freezes and raw case receipts remain available; only a new validated provenance envelope enters the common final reducer. All metrics, agreement probabilities, CIs and kill decisions wait until all final4883 EMAs and all3232 tasks finish. Init600reference plus64heldoutteacher on03; human03, teacher04 and mix01 cases follow their sealed final EMA. Single pools use56/60/44 physical workers, nice/SCHED_IDLE,24GiB floor;08 no reporting CPU. Four provenance tests PASS.

First reporting startup failed before any game because generation native06d8... lacks E1 rollout_e1. All children vacated,0games;1289.014866CPU-s archived/accounted. Dated `receipts/student-reporting-native-amendment.json` precedes affected outcomes and restores qualified E1 native-v2 f387b2d288ed280de9eeae3164d38f465045685ee53819e279930c2ee10699a8 plus its missing byte-exact support files. Original corpus/fit pins and scientific39b6adf6/f98d8926 unchanged. The old waiting r6 controller was deliberately replaced by `staged_controller.py`; continuation timer updated to avoid duplicate pools. Five-minute throughput receipt95d7c353 remains pinned and is never repeated.

S-human final4883 EMA sealed at22:33:25Z, SHA bb257672d47465b20611c29f714cc4e077e5f1aeedc504fc6a8f7d1566fe4bf5. Trainer/loaders exited and08GPU has no compute applications.03 controller admitted its856cases. Corrected init stage SHA d3d9258a3b957285be68c0333fa6686f408a26d4608109cd666b5c8e58978c06; E1 startup/player PASS, activepool has no failures. Launch and startup costs: receipts/student-staged-reporting-launch.json.
