# ExIt r2 X screen — results pending

Exploration lane; no multiplicity adjustment. Preparation at2026-10-10 00:36Z.
Original X1–X5 first fit attempts failed during input construction before any optimizer step.
The omitted r1 assets sidecar is restored; correction35cacd00 was pushed
before attempt2 launched00:52:49-51Z. All six fits now passed input admission
and have optimizer updates; X6 attempt1 began01:22:43Z after its own freeze.
Scientific stage metrics remain pending.
No reporting game played. This is a status record, not a verdict.
The committed plan/seed audit must precede fitting; use final EMA only.

| Arm | Target / fraction | Fit | Stage1 | Stage2 | Stage3 | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| X1 | T=.003 /1.0 | running09, step1202/4883 | pending | conditional | conditional | pending |
| X2 | T=.0001 /1.0 | running16, step1167/4883 | pending | conditional | conditional | pending |
| X3 | z-score τ=.5 /1.0 | running08, step1126/4883 | pending | conditional | conditional | pending |
| X4 | T=.003 /.75 | running01, step819/4883, micro3584 | pending | conditional | conditional | pending |
| X5 | X1 double steps /1.0 | running04, step1132/9766 | pending | conditional | conditional | pending |
| X6 | T=.0001 /.75 | running13, step180/4883, micro3584 | pending | conditional | conditional | pending |

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
CI≥0. Arm and empty-hook K1 control both face v1 on identical seeds/decks/seat.
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
9.379653CPU seconds (parent+children once); new controller/gate meter pending.
Current-attempt snapshots at2026-10-10 01:30:15–27Z:3.252965018 allocated
GPU-wall hours and10.164486111 provisional whole-tree CPU-hours across six fits.
Original five are attempt2; X6 is attempt1. These running totals replace earlier
snapshots and will be replaced by final supervisor exit meters; they exclude
failed attempts and preparation costs above.

| Arm | Live fit GPU-wall h | Provisional live fit CPU h |
| --- | --- | --- |
| X1 | 0.623852 | 1.616317 |
| X2 | 0.624974 | 1.671664 |
| X3 | 0.626522 | 1.838417 |
| X4 | 0.626221 | 2.915386 |
| X5 | 0.626107 | 1.708925 |
| X6 | 0.125289 | 0.413778 |

Own supervisor/trainer/loaders are counted once; segment diagnostics are not
added again. Receipt: `receipts/monitor-20261010T0130Z.json`. All six have eight
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
