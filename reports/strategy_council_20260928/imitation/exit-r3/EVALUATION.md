# R3 evaluation implementation freeze

Scientific plan remains [PLAN.md](PLAN.md), frozen/pushed bc542da8 before both
fits. This supplement pins operational evaluation entrypoints before any
calibration, W-regret root scoring, smoke, or reporting games. Training code,
roots, hyperparameters, seeds, thresholds, and final-EMA selection are unchanged.

Fit-host offline runs only after final step2500 and clean trainer/supervisor
exit. It uses float32 CUDA/TF32off on09/16, one encoder pass per minibatch, and
the 8088 eligible roots from the frozen 64-game R1 heldout slice. The threshold
nearest34.6% deterministic root plays is selected without action labels; ties
choose the smaller threshold and equal probabilities stay together. R3a ranks
legal conditional play probabilities; R3b ranks legal predicted advantages.
Top8 are offered even on gate-WAIT roots. The gate selects WAIT or the highest
ranked legal play as the S-default action.

The home CPU regret phase replays all64 original command streams to terminal.
For each heldout root, it reconstructs a fresh frozen R1 W belief/scoring root
with regret RNG4503601927370496+global corpus row index. Both students' legal
top8, the recorded W candidate set, WAIT, and WAIT10 are fully scored on that
common root. Groups contain at most8 plays so screening does not leave any
proposal unscored; repeated WAIT scores must match exactly between groups.
The comparator is W's best completed score among its recorded candidates;
the proposal best includes the always-available WAIT/WAIT10 fallbacks. The
mean positive regret gate is .010, as declared before fitting. Signed regret,
teacher-play-only regret, and percentiles remain descriptive. Every root and
all command replay hashes are sealed. Heldout-game bootstrap5000/80991013.

Survivors qualify on excluded smoke indices0/1 from the reserved191 bank.
Then600 fresh reporting seeds from190 run rotating complete same-seed blocks
[C-v1, survivingR3a/R3b in arm order, K0]. Each block runs back-to-back on one
physical core and one host at nice10/SCHED_OTHER, Torch/BLAS1. No controls are
pre-run. An incomplete block is archived and replayed in full; all attempts
remain charged. Smoke outcomes cannot select arms or thresholds.

The byte-frozen X S-default adapter, clock tests, K source and native pins are
retained. Own changes only load the calibrated R3 policy and supply its
default/proposal ranking, plus provenance and coordinator's actual scheduler
class. Both actors poll releasedv1. Student inference remains inside the
frozen200ms full-decision timer with8ms return reserve; complete refined play
uses X's unchanged best-complete-score rule. There is no eligibility filter.

03 admission requires K2's explicit notification/PROGRESS RELEASE, the atomic
`/mpac/sdicks02/jobs/clasher/k2-20261010-r1/K2-CPU-RELEASE.json`, terminal
reporting_complete/released flags and host03, and independent absence of every
recorded PGID plus no K-v2/K2/G timing processes. Own admitted receipt embeds
the exact release evidence SHA. Merely reaching07Z or seeing an idle core does
not admit work. Fallback01 similarly requires explicit X descriptive release
and full X/G drain. Own continuous guards require≥24GiB MemAvailable, allowed
physical cores0–59 on03/0–39 on01, no conflicting owner, own stop flags, and
Oct11 05:15Z deadline. Pools use8 regret workers,2 smoke workers, and at most46
reporting workers to stay below96 processes including per-block child games.

Final reduction checks every raw/case/block SHA, source/native/adapter/student
pins, paired decks/seat/seed, timer configuration, host/core/class and rotated
case order. It uses shared paired5000 bootstrap resamples80991013. The Stage2
kill rule remains upper95%CI(lossR3-lossC-v1)≥0; K0 is descriptive.

Metering charges each complete fit supervisor tree, each offline process, and
each home pool tree once. Nested game/block/replay diagnostics are never added
again. Every failed or replayed attempt stays retained. Qualification receipt
records five own unit tests and seven unchanged injected-clock tests. Earlier
dry runs and missing-dependency qualification attempts consumed no games and
have unmetered small test/copy overhead, disclosed separately.

Coordinator04:33Z granted a separate regret-only offline CPU slot on04,
physical12–19/nice19/at most8 processes. This supersedes the earlier need to
wait for03/01 only for Stage1 W-regret, and does not admit paired timing games.
Own guard_regret04.py and pool_regret04.py use manager19 and three scoring
workers12–14, keeping the manager, workers and simultaneous timestamp/SSH
helpers within8. No CPU52/116, X5 CPUs118–126, A19 cores0–11/47, GPU, or writes
outside the owned job prefix. Each scoring game still scores both arms on the
same frozen common roots and retains the scientific seed/gate definitions.

The04 manager continuously checks memory PSI fullavg10 and immediately stops
its own process groups if it exceeds10, checks recognized A19 launches, and
fails closed on any change to RUNBOOK.md/PROGRESS-T6T7.md SHA from the clear
admission snapshot or unavailable checks. Worker heartbeat expires after6s.
Vacate before any A19 launch; coordinator notification is requested before
launch. Absolute cutoff is Oct10 08:00Z. Any authority change requires explicit
review/re-admission; no automatic replay or stale authority reuse. Owned
REGRET04.STOP, recorded PID/PGIDs, reaped children and REGRET04-VACATED.json
are durable. Three workers leave spare room for short-lived helper processes.
After04 reduction, transfer the Stage1 results/offline merged metrics and
64-game proofs to the finally admitted03/01 job; do not repeat the regret
phase there or overwrite merged Stage1 metrics with raw GPU diagnostics.

Coordinator clarification headed05:16Z supersedes the earlier08:00Z deadline
and progress-SHA revocation rule. Hard vacancy is now Oct10 07:30Z. A19 cannot
launch before the existing A1 seal exits and its launch approval has not been
issued; the coordinator will notify R3 before issuing that approval. Admit
regret replay as soon as both final proposals exist, after fresh grant/PSI/no
A19-process checks. Review and approval bookkeeping may change progress SHAs
without revoking this grant. Continue recording observed hashes and fail closed
on unavailable progress checks. Actual A19 process detection, owned STOP,
PSI fullavg10>10, nice19/cores12–19 and at most8 processes remain enforced.
Manager19 and scoring workers12–14 are unchanged. No scientific gate, seed,
scorer, training recipe, or Stage2 CPU contract changes.
The guard begins vacancy at07:29:50Z, leaving ten seconds for bounded SSH
polling and three-second owned child reaping before the07:30Z hard deadline.
