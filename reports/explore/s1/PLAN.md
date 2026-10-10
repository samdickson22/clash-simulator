# S1 frozen exploration plan

Question: how strong is one-core coarse-first W with the R3a student proposer
and cutoff fallback on the same honest-lateness/plain-v1 opponent scale as
K2/K4, and how does it degrade with a 160ms rather than200ms deadline?
Exploration lane, frozen plan and seed audit before reporting; no PREREG.

Five arms use600 fresh paired seeds, symmetric d27/capacity1, five decks,
25matchups, alternating seats,12seeds per matchup/seat. Opponent is K2's exact
sealed stochastic T1 v1 policy with no search. One-core arms K0c-200/S-200 and
K0c-160/S-160 use coarse-first W-screen8. Candidate generation receives top8
legal v1/student proposals; balanced scan must finish before any play receives
its complete three-style score. The same-packet fallback is returned if no
candidate completes. All scores use horizon160 and original-order epsilon1e-9
ties. K0c caches one v1 forward for both stochastic fallback and exact top8
proposals; S uses one R3a EMA forward for its frozen calibrated deterministic
fallback and top8. No cross-poll cache. K2-200 is the frozen two-worker
WAIT-first anytime W anchor with no proposal hooks and unmodified v1 fallback.
K0c is not K-anytime/K2's policy-only K0 and is not the earlier r1(b) mirror.

R3a final2500 EMA SHA37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85;
calibration SHAe300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414,
threshold0.5005528330802917. Its original Stage1 kill/NEVER-ADOPTABLE status
remains immutable. S1 assesses a compute tier; it does not admit R3a into live
play or override R3's gates. No heldout fitting or calibration changes.

K2/K-v2 full timer begins before public observation, includes inference,
belief preparation, candidates, fair root, scoring, reduction and submission.
Scoring cutoffs are192ms/152ms with the same8ms reserve. Every positive wall
overrun delays command due time, own availability and timed waits by
ceil(overrun*20)ticks. Exact belief preparation is resumable/cancellable; GC
is deferred only during decisions, with maintenance pauses retained. This is
budget-equivalent speed emulation, not a measured hardware underclock.
The152/192 ratio is79.17%; nominal deadlines have ratio80%.

Only127x01 physical0–39, nice10/SCHED_OTHER, ownsetsid-f wrappers. R3 has priority
until c/e finalStage1 and any survivor reporting; explicit finalrelease,
independent PGID/lock vacancy and no other CPU job required before admission.
Never timing-share01. Main/supervisor39;13 disjoint three-core slots0–38,
10slots0–29 if who nonempty; K2 uses all3cores, others slotfirstcore only.
Each seed's five arms run consecutively on its same slot in cyclic rotated
order. Complete blocks only; preserve interrupted work, require explicit
investigation before any scientific retry. STOP and24GiB memory floor polled.
Caches below/mpac. Never03/04/08/05/leasedhosts for scientific computation;
05 serves only repository/metadata authoring. No Mac access.

Qualification completed before finalfreeze:125-state frozen no-deadline action,
candidate, score and root equality for coarse-first and K2; proposal-augmented
coarse-first vs frozen W equality; single-cached vs double-inference v1 actions,
proposals and RNG equality; student cached vs original TimedPolicy equality;
injected-clock coarse cutoff/partial/late/WAIT alias tests, inherited two-worker
non-drain/reuse tests, honest-lateness, belief cancellation and GC tests.
Runtime asserts every real student forward occurs inside this game's full
wall timer/GC window. Excluded8paired seeds (40games) require metadata,
paired schedule, honestlateness, scheduler/cores, no GC inside decisions,
forward==fallback counts and checkpoint/native/source pin checks.
Timing tails are disclosed without outcome-driven changes.

Reporting base4503602607370496+[0,600); excluded smoke4503602617370496+[0,8).
Audit all frozen ranges and helperoffsets0/13/100000..100003/271828..271829.
Freeze source, plan, seed audit, qualification, immutable base snapshot/native,
policy/checkpoint/calibration before any reporting game. Commit only owned
explicit paths, run clasher-secret-scan, push, verify committed bytes remotely.
No outcomes before all600 terminal paired blocks across allfive arms.

Use5000 shared paired-seed bootstrap resamples, RNG2026101026, unadjusted95%
percentile CIs. Loss means opponentwins; draws separate. Primary contrasts
S-200−K0c-200, S-160−K0c-160, S-200−K2-200. Also report paired degradation
S-160−S-200 and K0c-160−K0c-200, arm W/L/D and lossCI, cutoff/fallback rates
with seed-resampled CIs, all latency and positiveoverrun p50/p95/p99/max,
overrun ticks and cutoffreturns>deadline+reserve, GC counts/generations,
pause distributions and simulatedgame-minute rates. Retain source/raw/command
hashes, scheduler/core receipts, failures, whole-tree CPUcosts and finalvacancy.

Decision: **1-core student tier viable** iff upper95CI(S-200−K0c-200)≤−10pp
AND upper95CI(S-200−K2-200)≤+5pp. Otherwise report descriptively. No tuning,
optionalstopping, early outcomereduction or multiplicity adjustment.
Update S1-owned Mac-tier note with the result and limits. Fleet one-root
strength does not establish loadedMac fullpipeline/four-belief-root timing;
GC maintenance lacks timestamp/opportunity tracing inherited from K2.
