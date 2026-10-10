# ExIt r2 X screen — interim results

Updated 2026-10-10T05:42:38Z. Exploration; no multiplicity adjustment. X1, X2, X3, X4, X6 and X7 are killed at the frozen offline64 gate. X5 continues fitting. Original h2h256 and d0264ec9 stage3 banks remain unconsumed; R2 is ineligible. The separate never-adoptable descriptive study is reporting on01; results remain pending until all600paired blocks close. The experiment is active.

Coordinator 03:58 judged the frozen stage1 gate design **infeasible**: fresh-W self-agreement top8 is0.314 [0.283,0.348] against0.50, while root agreement0.706 [0.686,0.725] barely reaches0.704. Frozen kills are retained for the record and **do not establish student quality**. [Committed noise-ceiling analysis](ANALYSIS-NOISE-CEILING-20261010.md),136a1285. Remaining fits and offline scoring finish unchanged. Original stage2 and d0264ec9 stage3 banks remain unconsumed; R2 cannot trigger.

A separate fresh-seed S-default study is frozen and pushed at e8c82b10: **exploration; never adoptable**, X1/X2/X4 under coordinator04:35 selection amendment693bc3b1, shared C-v1/K0 anchors,600 paired seeds on01/nice10/SCHED_OTHER after X4 exit. Reporting4503602007370496+,qualification4503602017370496+, fully interleaved same-seed cases. X4 is highest play recall among the completed X3/X4/X6 recipes; X5/X7 are excluded as X1-family variants but finish fitting/scoring for the record. Optional h2h omitted. Provisional180 bank was withdrawn unused after K-v2 collision. The passed fresh audit and prelaunch receipt precede all study games.

| Arm | Target / teacher fraction / seed | Fit | Stage1 | Stage2 / Stage3 |
| --- | --- | --- | --- | --- |
| X1 | T=.003 /1 /2026101001 | sealed final EMA 4883 | KILL: recall, top8, hard agreement | SKIP: stage1 killed |
| X2 | T=.0001 /1 /2026101001 | sealed final EMA 4883 | KILL: recall, top8, hard agreement | SKIP: stage1 killed |
| X3 | root z-score τ=.5 /1 /2026101001 | sealed final EMA 4883 | KILL: recall, top8, hard agreement | SKIP: stage1 killed |
| X4 | T=.003 /.75 /2026101001 | sealed final EMA 4883 | KILL: recall, top8, hard agreement | SKIP: coordinator infeasible-gate ruling |
| X5 | X1 double steps /1 /2026101001 | running 127x04, step8859/9766 at2026-10-10T05:42:05Z | pending | SKIP: coordinator infeasible-gate ruling |
| X6 | T=.0001 /.75 /2026101001 | sealed final EMA 4883 | KILL: recall, top8, hard agreement | SKIP: stage1 killed |
| X7 | X1 replicate /1 /2026101007 | sealed final EMA 4883 | KILL: recall, top8, hard agreement | SKIP: coordinator infeasible-gate ruling |

Stage1 on the unchanged sealed r1 heldout64:8088 eligible root rows,2798 teacher plays and5290 teacher WAITs. The all-poll supplement has37950 eligible rows. Below are point estimates and paired whole-game percentile95% bootstrap CIs (5000 resamples,PCG64 seed80991010). Display rounded; linked receipts retain full precision, denominators, all-poll metrics and pinned final EMA.

| Arm | Play recall [95% CI] | Top8 recall [95% CI] | Root hard agreement [95% CI] | Student WAIT [95% CI] | WAIT / teacher |
| --- | --- | --- | --- | --- | --- |
| [X1](receipts/stage1-X1.json) | 0.259019 [0.247870,0.269634] | 0.305933 [0.288135,0.324391] | 0.612760 [0.594250,0.632325] | 0.829245 [0.816916,0.842311] | 1.267852 |
| [X2](receipts/stage1-X2.json) | 0.235215 [0.223984,0.245770] | 0.303431 [0.285266,0.322416] | 0.629822 [0.612412,0.648093] | 0.849532 [0.838083,0.861410] | 1.298868 |
| [X3](receipts/stage1-X3.json) | 0.252151 [0.241149,0.262688] | 0.310222 [0.292146,0.329165] | 0.624505 [0.606383,0.643139] | 0.835594 [0.823661,0.848178] | 1.277558 |
| [X4](receipts/stage1-X4.json) | 0.255751 [0.242770,0.267749] | 0.291637 [0.274494,0.309906] | 0.600890 [0.580724,0.622214] | 0.828369 [0.814955,0.842488] | 1.266511 |
| [X6](receipts/stage1-X6.json) | 0.226257 [0.214442,0.237495] | 0.287706 [0.269442,0.306828] | 0.625247 [0.607801,0.643641] | 0.853604 [0.841990,0.865746] | 1.305094 |
| [X7](receipts/stage1-X7.json) | 0.258470 [0.247024,0.269396] | 0.308077 [0.290518,0.326272] | 0.613625 [0.594565,0.633512] | 0.829674 [0.817245,0.842832] | 1.268508 |

All six kill on play recall<.60,top8 recall<.50 and root hard agreement<.704. Teacher WAIT is.654055391 [95% CI .641069402,.668218454]; all six student WAIT rates pass the fourth rule (kill only if>1.5×teacher). No stage2/3 CI or loss is estimated for a killed arm. Final EMA/source/corpus/seed recipe remains unchanged.

X7 minus X1, descriptive seed-replicate gap on frozen teacher roots: play recall−0.000548497, top8 recall+0.002144389, hard agreement+0.000865480 and WAIT+0.000428758. These are point differences; no paired gap CI is estimated. [Gap receipt](receipts/X7-minus-X1-offline-gap.json). Original stage2/stage3 gaps are not estimable because their banks are unconsumed. The separate X1/X2/X4 study excludes X7 under pre-report693bc3b1, so its descriptive-game gap is not estimable.

The operational GPU scoring/routing amendmenta7b5acd1 was secret-scanned/committed/pushed before all six offline attempts. Float32 CUDA/TF32 disabled/no autocast preserves the original batch64, metric formulas,CPU reductions,bootstrap and point gates. Synthetic128-row qualification matched hard actions/top8 exactly, score max difference7.629e-6, metric/CI differences<1e-6;12 metadata admission tests passed. These are qualification data, not heldout outcomes.

Proposed X8 (X2 replicate, trainseed2026101008,host15) was cancelled by coordinator before freeze, staging, audit, host access or fit. Zero fit/game compute; seed unused. This is a cancelled proposal, not a scientific kill. Seven arms remain. [Cancellation receipt](receipts/x8-cancellation.json).

Stage1 continues on each arm’s own fit host after sealed finalEMA/clean fit exit/ownedgroups absent/GPUidle/currentlease and floor checks. The original stage2 and d0264ec9 stage3 route is now disabled and its seeds unconsumed. The separate descriptive S-default study uses only01 physical0–39, nice10/SCHED_OTHER/Torch1 after X4 clean exit and G full drain/home24GiB/load≤100, with every same-seed case interleaved and no control pre-run.

X3 finished fit03:30:36Z and offline03:30:50Z. All own08 fit/scoring PGIDs are absent; GPU has no compute process and48578MiB free at03:32:05Z.08 vacated well before05:30Z; no migration or X6/X7 priority yield required.

X6 finished fit cleanly03:49:20Z; one heldout GPU attempt launched03:49:29Z and closed03:49:44Z. Supervisor2869254=PGID2869254/worker2869263=PGID2869263; logstage1-X6-attempt1.log. FinalEMA SHA6f8cd058db209ca4e53df42740434f9242b489c064dbae1be10970558c42cbe8. Controller collected the kill without failures. All own13 fit/scoring groups absent, GPU compute empty/free48666MiB at03:50:38Z. [Completion receipt](receipts/X6-completion.json). Fit max processes10 remains below leased16; original input/optimizer/RNG/recipe/source unchanged. No extra X2/X6 h2h games are run after their stage1 kills.

| Closed arm | Fit GPU-wall h | Fit whole CPU h | Offline GPU-wall h | Offline whole CPU h |
| --- | --- | --- | --- | --- |
| X1 | 2.504213012 | 6.513343099 | 0.003094961 | 0.002847458 |
| X2 | 2.520438362 | 6.790320697 | 0.003094121 | 0.002869096 |
| X3 | 2.629250317 | 7.795465627 | 0.003155318 | 0.002952663 |
| X4 | 3.632502419 | 19.850079163 | 0.003676310 | 0.003114785 |
| X6 | 2.443525074 | 9.508914612 | 0.004235091 | 0.003630126 |
| X7 | 2.567170730 | 7.187754370 | 0.003956509 | 0.003652209 |

Current seven-fit total at2026-10-10T05:42:38Z: 21.117274177 allocatedGPU-wall h /70.803372012 wholeCPU h ([snapshot](receipts/monitor-20261010T0542Z.json)). ClosedX1/X2/X3/X4/X6/X7 final exit meters replace their live snapshots; X5 is provisional. This replaces all prior live totals, never sums snapshots. Offline total is separately0.021212310GPU-wall h/0.019066336CPU h. Child scoring result CPU is nested inside the whole supervisor meter and is not added again. GPU guard resource peaks are sampled, not continuous maxima.

Post-kill study frozen/pushed e8c82b10 before any game: [plan](POSTKILL-SDEFAULT-PLAN.md), [addendum](receipts/postkill-sdefault-addendum.json), [fresh audit](receipts/postkill-seed-audit.json). Fresh239590-file scan zero collisions/errors,217.087355CPU s;2560 expanded interval comparisons .554847CPU s. Three post-kill code qualification attempts total8.728720CPU s; offline-only six-test qualification1.335640CPU s. Metadata staging verification on01 passed source/native/policy pins and correctly kept games closed while X4 fit remains active. Sender/bootstrap/copy/direct metadata-shell CPU unmetered and disclosed; no new game attempt yet.

New preparation: GPU synthetic qualification10.238241CPU s/10.278003GPU-wall s;12 metadata tests.344673CPU s; all7 heldout staging6.196271CPU s. Source sender/bootstrap/native-copy CPU is unmetered and disclosed. Prior failed fits/audits/staging/controllers/smokes remain separately retained in receipts and history. Retired seven-armcontroller1870636 cleanexit11.910174CPU s charged once; retiredcontroller1940296 exited cleanly (19.744972CPU s once); currentcontroller2071651 remote jobs are separately metered, controller’s SSH/local children only counted in its own final meter.

X4 clean fit exit04:30:48 and single GPU score exit04:31:03; all original fit/scoring groups absent. FinalEMA a1b4aaae2173b17a68256796585ab18fb737204307a3dbde3b8d1ad48223c5b9. [Completion](receipts/X4-completion.json). The disclosed608.730407s slowdown remains inside the whole fit meter.

Descriptive selection amended/frozen/pushed693bc3b1 before any reporting game: [selection addendum](POSTKILL-SELECTION-ADDENDUM.md), [sealed X1/X2/X4 selection](receipts/postkill-selection.json). Original e8c82b10 bytes and search/default/timer semantics preserved. Six metadata-only routing/selection tests pass,2.869253CPU s. Selected final checkpoints transferred directly09/16→01 and SHA verified. Reporting still uses600 fresh200-bank seed blocks and five fully interleaved cases per seed; X5/X7 fit/offline continue independently.

Fresh201 smoke indices4/5: six terminal mechanics games, both complete same-core interleaved blocks; [wrapper qualification PASS](receipts/postkill-wrapper-qualification.json), inference inside Kwall0/both v1 polling actors/legal defaults/proposals/raw metadata. Smoke losses excluded and never read as reporting outcomes. Whole smoke pool524.551305CPU s/267.878277wall s; nested case/block CPU not added. Frozen-output reduction separately1.111888CPU s; transfer/bootstrap/direct metadata-shell overhead unmetered and disclosed. Original global G STOP remains; authorized host STOP-01 written04:28:15 and G fully drained before admission.

Reporting started04:42:48Z on01, poolPID=PGID2035131/logpostkill-reporting-attempt1.log, managercore63 and40physical cores0–39/nice10/SCHED_OTHER/Torch1. Preflight and startup passed all source/native/policy/checkpoint pins, clean old-group exit, no existing pool/bank, G drain and memory/load floors. First completed case metadata from each of the five arms passes amendment/nonadoption/thread/horizon/scheduler checks; no reporting loss or CI inspected. At04:44:56,40active blocks/560pending/0complete/no failures, available109575536640bytes/load40.29. Whole live poolCPU2193.46s at04:43:46 is provisional and replaced by final whole-pool meter; never add nested block/caseCPU. [Startup](receipts/postkill-reporting-startup-qualified.json). Current health05:42:05:307/600 complete paired blocks,253pending/40active, no failures, available110226137088bytes/load47.52. New provisional wholepooltreeCPU46461.92s replaces the startup live CPU sample, final exit meter supersedes both; never add nested case/block CPU. No reporting outcomes inspected. Reporting and remaining X5 record are still pending; schedule stays enabled.

X7 final4883/EMA fit exited cleanly05:41:45Z; one frozen GPU score closed05:42:06Z. Fit2423139/2423269 and score3048428/3048438 groups absent,14GPUempty48666MiB. EMA SHAafb6775fe49a8fd5dee7dfcbfc0b7130e48909fa8bd204217007b6250ad98bbd; all original source/input/final checkpoint SHA checks pass. [Completion](receipts/X7-completion.json), [pin verification](receipts/X7-final-pins-verification.json). Separate read-only final-check preparation0.833881CPU s. Whole scoreCPU13.147951s includes nested resultCPU12.238340s, which is not added again.

Earlier operational records below are historical; current state, protocol and costs above supersede stale “pending/current controller” snapshots.
Common width192, v1 main-2026100802 step22552 EMA, corpus1c8e1f49,
seed2026101001, batch8192, play weight1, final EMA. X1–4:4883steps;
X5:9766steps; X6:4883steps. Loader6/prefetch4, r1 parent and loader core layout.
Coordinator added X6 at01:05Z to complete the temperature×anchor2×2.
It yields13 to X3 exact resume; all six arms share the same staged rules and
at most three stage3 survivors total. X6 has no gate outcome yet.
X3's flag-off targets/loss/gradients/AdamW update match r1; all seven student and
target tests passed on01/16/03. No evaluation outcomes used for choices.

Stage1 uses the sealed r1 held-out64 whole games, root probability play recall,
top8 recall on teacher plays, hard agreement and expected WAIT. Kill boundaries:
recall<.60, top8<.50, hard agreement<.704, or WAIT>1.5×teacher.
Stage2 survivor h2h256 seeds4503601507370496+, kill upper loss CI≥.50.
Stage3 up to3 survivors,600 paired seeds4503601517370496+, kill upper loss-change
CI≥0 for S-n−C-v1; K0 is descriptive. All arms face v1 on identical
seeds/decks/seat, interleaved back-to-back on the same host/core/class.
K1 qualified before06Z; its primary harness is pinned, fallback unused.
The initial own wrapper used a K1 opponent in two mechanics-only smokes.
That design was corrected before any reporting game; v2 qualification gates
reporting. Corrected qualification passed01:06:17Z: four terminal games,
two exact seed/deck/seat pairs, v1 opponent/fallback, one ownK1 core,
empty reference hooks and inference afterwall0. Those two original smokes cost0.047438426CPUh and are ineligible controls. Corrected smokeCPUh:0.069102254;
sealCPUseconds:0.039148. No reporting outcomes consumed.
Intervals:5000 whole-game percentile95% bootstraps, seed80991010.

R2 DAgger is conditional on a stage2 survivor. No R2 generation is admitted yet.
All games are home01/03 only;04 CPU seal/core52 protected;08 GPU temporarily authorized until Oct10 05:30Z.13 has not
been preempted. Leased GPU jobs require current leases and strict process,
PSS/headroom/nice guards and return before2026-10-11 05:30Z.

Metered failed-attempt fit GPU-wall hours:0.036806672;
fit CPU-hours:0.029492098; heldout/reporting CPU-hours:0; mechanics costs reported above.
Preparation audit CPU-hours:0.861178583, including retired scan attempts and
X6's fresh13 audit59.074613CPU seconds. X6 corpus staging/SHA preparation meter
is493.808473 local CPU seconds (0.137169020h), excluding remote senderCPU.
All71 corpus-file SHAs passed01:22:16Z; fit attempt1 launched01:22:43Z after
addendum c99491bc push. Startup qualified01:25:33Z at step18, eight own
nice10 processes,21.36GB PSS,31.79GB GPU free, no stop reason. No scientific
X6 outcome claimed. Original controller replacement meter is
9.379653CPU seconds (parent+children once); superseded six-arm controller
1502885 adds11.933346CPU seconds (parent1.784861+metadata children10.148485),
with no evaluation active on exit. Superseded G-admission controller1596239 adds18.384221CPU seconds once;
superseded K-admission controller1746462 adds8.388678CPU seconds once;
current readiness/K-admission controller1808181/gate meter pending.
Current-attempt snapshot at2026-10-10 02:52:22Z: 11.443398520
allocated GPU-wall hours and38.210255556 provisional
whole-tree CPU-hours across six fits. Original five are attempt2; X6 is
attempt1. These replace prior live totals; final exit meters supersede them.
Closed failed/preparation/controller/qualification work stays separate.

| Arm | Live fit GPU-wall h | Provisional live fit CPU h |
| --- | --- | --- |
| X1 | 1.989035 | 5.195000 |
| X2 | 1.991803 | 5.382794 |
| X3 | 1.991342 | 5.914853 |
| X4 | 1.989411 | 10.344944 |
| X5 | 1.989443 | 5.608156 |
| X6 | 1.492363 | 5.764508 |

Own supervisor/trainer/loaders are counted once; segment diagnostics are not
added again. Full identity receipt: `receipts/monitor-20261010T0238Z.json`;
latest snapshot: `receipts/continuation-check-20261010T0252Z.json`. All six have eight
owned processes, nice10, no stop reason. Leased09/16/13 remain below46GB PSS
and above8GiB GPU free. 08 quiet entries are empty after stripping comments.
Capacity released13 at01:03Z; independent GPU-idle check01:12:24Z confirms
release provenance. X6 now occupies13 and will checkpoint/yield for X3;
fresh lease/GPU-idle admission checks remain mandatory before any X3 resume.
Preparation audit CPU costs and failed/retired scan attempts are retained under
the audit job and PROGRESS-X.md; final totals will include every fit and game
attempt, startup/loader CPU, and scientific postprocessing. Full per-arm metrics,
case counts, checkpoint pins and metered totals replace this pending record as
the staged decisions become available.

2026-10-10 01:38Z resource observation: X4 optimizer latency rose from2–3s
to27–73s after step835, around G's01 generation launch01:30:38Z. Own CPU
affinity stays118/119/126 plus loader120–125; G uses physical0–39. Only X4
uses the GPU; free memory29.88GB and hostMemAvailable~89GB pass guards,
but host memory PSI full~80% and GPU utilization~1% suggest shared-memory
pressure. Cgroup limit unlimited/no failures. Coordinator notified for a
reversible load check; causal attribution remains unproven. No job stopped,
recipe/source changed or scientific kill assigned. Observation receipt records
raw timing and the verified X6 step250 checkpointSHA dbd95e8419a95483facdc5d3bb54ba41864f0185f9e5c924f3e38c616c1b8de1.

2026-10-10 01:41:32Z follow-up: X4 steps855–861 recovered to1.71–2.78s
optimizer latency as G honored STOP01:38Z and drained games. Host available
memory106.04GB, memory PSI full avg10=11.76% (falling). G supervisor remained
present; full vacate was not claimed. X trainerPID1217609, source, recipe and
checkpoint lineage unchanged; slow interval remains charged within attempt2.
Recovery supports shared-load interference but does not establish its precise
cause. Coordinator informed; receipt x4-throughput-recovery-20261010T0141Z.json.

2026-10-10 01:42Z comparator hold: no stage3 reporting processes or case files
on01/03, verified with remote process/case audit. Prior disjoint qualification
smokes stay excluded from reporting. RuntimeSTAGE3.HOLD and the updated
continuation prompt suspend all stage3 arm/control games pending explicit
coordinator comparator revision; independent review ETA02:30Z is not a
release. Fits and stages1/2 continue unchanged, conditional R2 still requires
a stage2 survivor. No comparator substitution or scientific kill assigned.

2026-10-10 01:47Z evaluation handoff: operational amendment989b7429 was
secret-scanned/pushed before controller replacement. Old1502885 clean exit
retains its11.933346CPU seconds once. New03controller_g_yield.py
PID=PGID1596239 started01:46:38Z,nice19/SCHED_IDLE/core63, no active gate or
failures. Before stage1/2, helper writes authorized G STOP-03 then waits for
all G ops processes to exit, two empty scans and24GiB available memory.
Manual01 evaluations must use STOP-01 and the same drain check. No real G
stop requested by X admission yet because all fits still pending; qualification
used fake files/metadata with no games. Science/frozen source bytes unchanged;
stage3 remainsHOLD and conditional R2 depends on a stage2 survivor.

2026-10-10 01:48Z continuation: current controller1596239 healthy, no scientific
stage outcomes or G admission request. All six fit groups unchanged and
resource checks pass;08 quiet entries empty. X6 checkpoint750 verifiedSHA
b3e907d7045fc0fe5368696c45223efd5b885516cc9eb26c8a571642860dccaa; only final
EMA remains eligible for reporting. X4 steps954–958 optimizer1.92–2.35s and G01
supervisor1356583 is now absent. Stage3 remains held; no reporting seeds.

X4 operational disclosure, coordinator clarification received01:50Z: affected
steps836–851 spanned608.730s (~01:31:01–01:41:10Z, UTC derived approximately
from monotonic elapsed and runtime.start). Instrumented synchronized-step
latency18.60–73.25s, versus2.18–3.11s at831–835 and1.71–2.06s at852–855.
The timing field includes resource reads and is not isolated GPU compute.
Coordinator wrote G01 STOP at exactly01:37:55Z, consistent with PSI~80%,
systemCPU~30%,~560k interrupts/s and active kcompactd/kswapd observed on01.
04PSI0 while X5+G coexist, per coordinator; no04 action. G01 stays off for
the rest of X4 fitting and cannot return without explicit release. X4
continued the same process/attempt2, no recipe/source/optimizer/RNG lineage
change or intermediate selection. Five source/freeze SHAs reverified01:50Z.
The entire slow interval remains included in attempt2 metering, never added
again as a separate cost. Full timing rows/authority/restriction retained in
receipts/x4-operational-disclosure.json; no scientific kill or outcome claim.

S-default replacement qualification: C-v1 versus empty-hook K1 and S-v1-standin
versus same-hooks/same-candidates K1 each reproduce125/125 actions and scores.
Seven injected-clock tests pass; seven block admission/ranking/legal argmax/stop-reap tests
pass. Empty-hook action differences11/125=8.8% are descriptive hook effects;
partial44/50 retained. Fixture-only short HUD fill is approved and disclosed.
The reporting contrast compares the full student package and does not separate
hook/default effects. No control pre-run; same-seed complete interleaved blocks
are required and K-v2 timing games must exit first. No replacement game has run.
All six synthetic qualification attempts are retained, including fixture failures
and the pre-Python launcher error. Metered synthetic CPU=200.940313s
(0.055816754h), plus all five block qualification attempts CPU=13.729057s.
These costs are separate preparation, never scientific reporting outcomes.
Small unmetered shell/direct-test preparation overhead is explicitly disclosed
in sdefault-qualification-attempts.json. Disjoint replacement wrapper smokes
remain pending K-v2 release; 600-seed reporting remains conditional.

S-default scientific freeze d0264ec9 pushed before any new game. Operational
phase-release check widened before games because K-v2 advanced to smoke-r3;
a successful REPORTING*-DONE marker still requires zero active timing processes.
Original stage3 freeze archived, default/hook/contrast/seed design unchanged.
All seven block tests re-pass. K timing release remains false02:16:55Z, so no
wrapper-smoke or replacement reporting process launched.

03 timing constraint received02:24Z: no stage1/2 evaluation overlaps K-v2
latency-sensitive work on03. Real observedK PGID1718091/releasefalse; current
controller has no active gate or outcome. A qualified versioned controller
queues final EMAs until successful K reporting release and no live timing
PGID, then waits G drain. Home01 requires completed X4/no fit PIDs first.
Eight metadata admission checks pass; all three qualification attempts CPU
8.473321s (0.002353700h), separate preparation with no scientific games.
Training/science/S-default hashes and staged thresholds are unchanged.

02:32Z controller replacement complete: prelaunch amendment e782cc77 pushed
before controller_k_yield.py launched02:30:20Z PID=PGID1746462, nice19/
SCHED_IDLE/core63. Source/qualification/startup checks pass. Superseded G-only
controller1596239 cleanly exited, no evaluation active; its parent2.142988+
children16.241233=18.384221CPU seconds retained once in controller-g-yield-meter.
Current controller has no active task, offline/stage2 outcomes or failures.
K timing PGID1718091 remains active; no stage1/2 starts on03 before release.
All six original GPU groups remain healthy,08 quiet empty/resource floors pass.
No reporting/S-default smoke/R2 generation admitted.

Final-fit handoff operational fix qualified02:46:37Z:10 metadata-only tests
PASS,CPU1.331412s; real unfinished-X1 readiness refusal CPU1.085578s on03,
remote tiny metadata probe CPU unmetered/disclosed. Complete.json is written
before loader cleanup/segment file, so collection now additionally waits final
artifacts, coherent metadata and clean owned fit exit. No training changes,
game outcomes or source/recipe/seed/gate changes. Costs are separate preparation.
Replacement controller must be frozen/committed/pushed before launch.

02:49:28Z collection startup PASS:77cbea40 amendment secret-scanned/pushed
before02:48:55Z launch, controller_ready_yield.py PID=PGID1808181 nice19/
SCHED_IDLE/core63. Old1746462 absent/clean, no active gates; its parent1.525436+
children6.863242=8.388678CPU seconds retained once. New source pins and
originalfreeze/S-default SHAs match. K1718091 active/noDONE, no evaluation
or replacement smoke/reporting admitted. Original six fits remain healthy;
operational handoff does not change training, scientific metrics or decisions.

X7 seed replicate approved; training/gates pending. Different trainseed2026101007, otherwise exact X1. X1/X7 share one stage3 recipe-family slot; only better-ranked survivor eligible, competing normally for3total slots. X7-X1 offline/h2h gaps pending; stage3 within-family gap will not be estimable. Preparation audit CPU41.298611s and metadata/stub-shell qualification CPU2.933585s are separately charged, no scientific outcome. Staging not yet complete; remote transfer sender/bootstrap CPU unmetered and disclosed.

2026-10-10T03:04:27Z X7 staging completed:71/71 corpus SHAs and input/human/sidecar pins pass; staging2379849 exited,427.168715s wall,420.142932s local whole CPU. Readonly sender CPU unmetered/disclosed. Staging receipt retained; still no X7 fit before prelaunch commit/push.

2026-10-10T03:07:15Z. X7 launcher2417277=PGID2417277 exited before supervisor/trainer because own venv symlink target absent. No optimizer/fit GPU cost; setup shell CPU unmetered disclosed. Existing lease-local clasher-gpu environment verified and own symlink corrected; original scientific hashes unchanged. Attempt1 log/identity retained; retry attempt2 only after correction commit/push. Old03 controller1808181 exited clean with no active task, wholeCPU8.155191s retained once.

X7 attempt2/new seven-arm controller active03:07:42Z after prelaunch freezes; no scientific outcome at launch. Old ready controller closedCPU8.155191s charged once. New controller startupPASS03:08:41Z, no active gates. X7 initial loading pending; original six resource guards remain passing.

X7 startup qualified03:10:10Z,step30/245760rows: exact replicate recipe exceptseed2026101007,loader6/prefetch4/affinities/nice10/floorsPASS. All7 scientific outcomes pending. Latestlive snapshot13.034709717GPU-wallh/43.602094444provisionalCPUh replaces prior snapshots; final exits supersede. No stage3 reporting seed or R2 root consumed.

Fit-hostGPU stage1 operationalamendment qualifies originalCPU metric/reducer parity:128syntheticrows,hard/top8exact,scoremax7.629e-6,metrics/CI<1e-6; no heldoutinference/game consumed. GPUqualCPU10.238241s/GPUwall10.278003s,metaguardqualCPU.344673s,prep separatelycharged. Qualificationbriefly shares01GPU withunchangedX4fit. Stage1gates/recipes/seeds unchanged;stage2 earliest01cleanX4exit or03Krelease. Staging73MiB heldoutall7metered,senders/bootstrap unmetered disclosed.
