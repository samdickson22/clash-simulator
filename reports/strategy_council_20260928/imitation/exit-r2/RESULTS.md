# ExIt r2 X screen — results pending

Exploration lane; no multiplicity adjustment. Preparation at2026-10-10 00:36Z.
All first fit attempts failed during input construction before any optimizer step.
The omitted r1 assets sidecar is restored; correction35cacd00 was pushed
before attempt2 launched00:52:49-51Z. All five fits passed input admission and have optimizer updates.
Scientific stage metrics remain pending.
No reporting game played. This is a status record, not a verdict.
The committed plan/seed audit must precede fitting; use final EMA only.

| Arm | Target / fraction | Fit | Stage1 | Stage2 | Stage3 | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| X1 | T=.003 /1.0 | running09 | pending | conditional | conditional | pending |
| X2 | T=.0001 /1.0 | running16 | pending | conditional | conditional | pending |
| X3 | z-score τ=.5 /1.0 | running08; resume13/14 if needed | pending | conditional | conditional | pending |
| X4 | T=.003 /.75 | running01, micro3584 | pending | conditional | conditional | pending |
| X5 | X1 double steps /1.0 | running04 | pending | conditional | conditional | pending |

Common width192, v1 main-2026100802 step22552 EMA, corpus1c8e1f49,
seed2026101001, batch8192, play weight1, final EMA. X1–4:4883steps;
X5:9766steps. Loader6/prefetch4, r1 parent and loader core layout.
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
Preparation audit CPU-hours:0.844768969, including retired scan attempts.
Preparation audit CPU costs and failed/retired scan attempts are retained under
the audit job and PROGRESS-X.md; final totals will include every fit and game
attempt, startup/loader CPU, and scientific postprocessing. Full per-arm metrics,
case counts, checkpoint pins and metered totals replace this pending record as
the staged decisions become available.
