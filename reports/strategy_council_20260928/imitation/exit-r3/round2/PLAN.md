# R3 round 2 addendum

Coordinator decision323786ab (05:46Z, queued05:48Z), reiterated06:13Z,
authorizes R3c09, R3d16, R3e13 and a never-adoptable R3a descriptive study.
Original R3a/b decisions remain killed. This is an outcome-informed exploration
extension, with no multiplicity adjustment. Commit/push this plan, source pins
and fresh seed audit before any new fit; no intermediate checkpoint selection.

All three initialize the original releasedv1 step22552 EMA at width192;
all are ROOT-ONLY and HEAD-OFF. R3c:5000 steps/T=.003/trainseed2026101013.
R3d:2500/T=.003/new trainseed2026101014. R3e:5000/T=.01/trainseed2026101013.
Effective batch8192, finalEMA only. R3c/e each40,960,000 rows, R3d20,480,000.
Fresh full fits, not continuations of the2500-step cosine recipe. AdamW3e-4,
decay.05, warmup2000 and cosine to each arm's total steps, clip1/EMA.999,
BF16/teacher micro128/loader6-prefetch4/Torch1 remain unchanged. The new seed
changes deterministic root sampling and training RNG; C/E retain the same seed.

Reuse the verified R1 corpus1c8e1f49, all five G shards4e8faf7e, same root-only
filter,6,222,223 eligible roots, initialization/assets and immutable dependency
source. Scientific source changes only admit T=.01 in the round2 trainer copy;
the qualified loss already accepts temperature. Original fit/runtime copies
remain unchanged. Staging verifies every G file SHA and source/input pins.
Synthetic tests must retain exact head-off R2 equivalence at T=.003 and verify
T=.01 target normalization, masking and loss/gradient equivalence to R2.

Same heldout64/8088 roots, label-free34.6% threshold calibration and exploratory
calibration reuse. Same gates: play recall≥.6375, binary agreement≥allWAIT+.10,
mean positive frozen-W top8 regret≤.010. FinalEMA CUDAfloat32/TF32off only.
Intervals remain5000 whole-game resamples/80991013; gates use point estimates.
Any binary kill excludes adoption Stage2; frozen-W regret still reported.
Regret replays for C/D/E require a separately admitted HOME CPU slot; the current
04 grant ends07:30Z and is not extended to these later fits. No CPU sims on
leased hosts. Evaluation implementations will be pinned/pushed before new
offline/replay/games; no gate, scorer, seed or model change after seeing results.

Round2 paired reporting4503602407370496+[0,600); excluded smoke
4503602417370496+[0,8); regret RNG4503602427370496+[0,65536).
Expand helpers0/13/100000..100003/271828..271829 and audit every frozen
K/K-v2/K2/X/X-descriptive/G/originalR3 bank before this freeze. Surviving C/D/E
use the original frozen S-default adapter/runner,600 fresh paired rotated
complete same-seed blocks versus C-v1 and K0; kill upper paired95%CI≥0.
Incomplete blocks are archived and replayed in full, all attempts charged.

Separately, R3a descriptive reporting4503602507370496+[0,600), excluded
qualification4503602517370496+[0,32). Exactly[C-v1,R3a,K0], same-seed rotated
back-to-back S-default blocks on01 physical0–39/nice10/SCHED_OTHER, manager39,
after explicit X release/full independent drain, no G, MemAvailable≥24GiB.
Original R3a checkpoint/calibration are immutable; its stage1 kills are never
overwritten. Qualification uses excluded indices0/1. All contrasts/intervals
are descriptive, never adoption gates; every arm's adoption eligibility=false,
regardless of measured win/loss. Freeze and qualify the descriptive execution
addendum before any games; no controls pre-run or partial-block reuse.

New own job prefix /mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2 on09/16/13;
read-only R2 dependencies and original R3 verified inputs. Own setsid-f wrapper,
PIDs/PGIDs/log/exit/whole-tree meters and resumable progress. Every leased host
≤16 processes/nice≥10/PSSguard46GB-hard48GB/GPUfree≥8GiB. Guard current lease
and reclaim continuously; checkpoint stop Oct11 05:15Z, vacate by05:30Z.
No CPU-heavy sims, no roader paths, tailscale/crontab/pkill-f. Caches under/mpac.
05 remains metadata/SSH only. Only explicit owned git paths; scan every push.

Reports keep original and round2 metrics/costs separate, then provide a combined
cost ledger with global SHA dedup. Include all failed/replayed work, staging,
qualification, GPU wall and whole-tree CPU; nested diagnostics never add twice.
Continuation remains enabled while round2/descriptive work is pending.

Publication incident: initial06:28:10 startup wrappers were launched after an
unhandled publication-check failure. They are VOID, stopped by owned FIT.STOP
at06:28:35 and exited06:28:50 before any train log/checkpoint. The initially
claimed prelaunch commit was unrelated and invalid. Original meters/receipts
are retained, all CPU/GPU reservation wall charged. Restart from releasedv1
in fresh outputs under attempt2 ONLY after this corrected addendum is actually
committed/pushed and its exact git content is independently confirmed remotely.
No startup outputs, losses or checkpoint selection inform the recipe or gates.
