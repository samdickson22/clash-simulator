# ExIt r2 X screen — results pending

Exploration lane; no multiplicity adjustment. Preparation at2026-10-10 00:36Z.
Original X1–X5 first fit attempts failed during input construction before any optimizer step.
The omitted r1 assets sidecar is restored; correction35cacd00 was pushed
before attempt2 launched00:52:49-51Z. All six fits now passed input admission
and have optimizer updates; X6 attempt1 began01:22:43Z after its own freeze.
Scientific stage metrics remain pending. Coordinator replaced stage3 with
S-default K1; replacement reporting waits gates, freeze/push, K-v2 release and
wrapper smokes. The old comparator remains suspended; no stage3 seeds consumed.
No reporting game played. This is a status record, not a verdict.
The committed plan/seed audit must precede fitting; use final EMA only.

| Arm | Target / fraction | Fit | Stage1 | Stage2 | Stage3 | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| X1 | T=.003 /1.0 | running09, step3590/4883 | pending | conditional | conditional S-default | pending |
| X2 | T=.0001 /1.0 | running16, step3543/4883 | pending | conditional | conditional S-default | pending |
| X3 | z-score τ=.5 /1.0 | running08, step3323/4883 | pending | conditional | conditional S-default | pending |
| X4 | T=.003 /.75 | running01, step2396/4883, micro3584 | pending | conditional | conditional S-default | pending |
| X5 | X1 double steps /1.0 | running04, step3214/9766 | pending | conditional | conditional S-default | pending |
| X6 | T=.0001 /.75 | running13, step2637/4883, micro3584 | pending | conditional | conditional S-default | pending |

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
current K-admission controller/gate meter pending.
Current-attempt snapshot at2026-10-10 02:42:33Z: 10.464743377
allocated GPU-wall hours and34.907205556 provisional
whole-tree CPU-hours across six fits. Original five are attempt2; X6 is
attempt1. These replace prior live totals; final exit meters supersede them.
Closed failed/preparation/controller/qualification work stays separate.

| Arm | Live fit GPU-wall h | Provisional live fit CPU h |
| --- | --- | --- |
| X1 | 1.826612 | 4.767153 |
| X2 | 1.828054 | 4.938075 |
| X3 | 1.828058 | 5.409483 |
| X4 | 1.827176 | 9.486225 |
| X5 | 1.825426 | 5.177653 |
| X6 | 1.329419 | 5.128617 |

Own supervisor/trainer/loaders are counted once; segment diagnostics are not
added again. Full identity receipt: `receipts/monitor-20261010T0238Z.json`;
latest snapshot: `receipts/continuation-check-20261010T0242Z.json`. All six have eight
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
