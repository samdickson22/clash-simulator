# Frozen W search-opponent confirmation and latency experiment

Frozen before **any games**. Coordinator: 0523ae6f. Exploration lane, public repo.
Configuration SHA256:
`414ecf5235f899c41e874e9c03465c2a944de2f5372f25747b0159bfcaea42a8`.
The freeze commit identifies the harness. No tuning, arm selection, seed replacement,
or stopping based on outcomes on reporting seeds. Technical repairs require a dated
amendment and rerun of affected cases, preserving prior attempts outside git.

## Confirmation

Target: **600 paired fresh seeds per arm**, control 0-vs-0, W-vs-0,
H16-vs-0; supplementary W-vs-W on the first 100 of these same paired seeds.
Same five highest-frequency train-catalog archetype decks and 25 matchup cells as
tempo, selected without outcomes. Pair i has own deck i mod 5, enemy deck floor(i/5)
mod 5, focal seat i mod 2. Each cell has 24 main seeds and 12 per seat. Both players
use public search, not physical scripts. Both have d=27, cadence 10, one outstanding
command, abilities off, first decision tick 90. Fixed 16 random extras plus the
unchanged script proposals, three opponent styles, horizon 160 (H16: 320), no deadline.

W retains original WAIT and every immediate candidate, adds waits of 10/20/40 ticks,
suppresses own follow-ups and physical decisions for that duration, and adds the
original `0.01 * sqrt(wait_ticks/20) * (1-own_elixir/10)` prior below terminal score
magnitude 2. Duplicate original WAIT / 10-tick WAIT are **not** removed in confirmation.

Reuse `delay_fixes.CommandQueue` and `DelayFixPlanner.simulate_commands` / native
`rollout_commands`. Both hypothetical rollout channels also have d=27 and capacity 1;
no true pending enemy command crosses the player boundary. A private native extension
decodes timed WAIT actions and suppresses only own follow-ups until their wait ends.
All ordinary command paths are unchanged. Verify native timed-WAIT scores and traces
against a Python implementation of the same queue schedule before reporting runs.

Pin the checked-out build48 combat source plus GIL-release and x86-64-v3 in a **new**
binary/snapshot; qualify ordinary actions against the supplied quickwins build48 binary.
This is a new matched-engine comparison, not a claim of engine equivalence to tempo's
build46 historical result. Record source and binary hashes before running reports.
No live engine, running lane, gate artifact, or defaults are edited.

Fair boundary: public v5 observation, own HUD/hand/cycle, accepted enemy card events,
train-only deck prior and independent sampled hidden-state/RNG beliefs. Physical
BattleState and queues belong to the driver only. Root snapshots used for latency
replay are independently reconstructed hypothetical states, never hidden live states.
Full telemetry is reduced outside the player. No heldout/gate outcome payloads.

Seeds: `config.json` and `seed-audit.json` exclude prior tempo, search A/B, loss-review,
registered gate seed-only inventories and delay-fixes +50000..+51249 / +59000 smoke.
Check game/shuffle and both planners' helper offsets 0/100000/100001/100002/100003.
Reporting base 4503599630370496, i=0..599. Smoke and latency occupy disjoint ranges.

Primary outcome: terminal focal loss rate and W-minus-control loss change. Report
wins/losses/draws, H16 contrast and pointwise 95% paired bootstrap percentile CIs,
5,000 shared seed resamples. Supplementary WW is descriptive. Each run must reach
the existing 6,001-tick terminal bound; nonterminal games block complete reporting.
Loss-review metrics: pooled under-4 arrivals, no-affordable-defender in hand,
defender-not-in-hand, expensive-card hand affordability / accepted plays per deck-minute
(Xbow, Giant, Rocket, Fireball), time at cap and conservative leaked elixir/minute.
Report opportunity counts because WAIT changes the decision exposure. Include full
decision wall/CPU p50/p95/p99 and >200 ms fraction; loaded SCHED_IDLE game wall times
are not live latency qualification. Bootstrap all pooled ratios at the paired-seed level.

## Latency, separate from outcomes

Generate a fixed set of at most 125 public reconstructed decision states from 25
separate scripted driver seeds covering all matchups; ticks 90/300/600/1200/2400,
both seats alternate. Keep only nonterminal roots. Freeze state IDs, inputs, candidate
lists and hashes before comparing variants. No reporting states or outcomes tune a
variant. Run original full W and symmetric full W on the same states. Qualify the
original W scorer against the untouched tempo class before measuring reductions.

Profile full W. Compare exact WAIT/10-tick WAIT rollout reuse, one/two styles per
timed WAIT, timed-WAIT gating at elixir <4/<6/<8 and four Python threads with the
GIL-release binary. All non-WAIT candidates retain full scoring. Report exact action
agreement including wait duration, play-versus-WAIT agreement, and score regret
against full W. Three repeats/state, warmup excluded, paired execution order alternates.
One physical 3990X core with BLAS/Torch/Rayon=1 is the primary budget; separately
label four physical cores as exceeding that budget. Target empirical p95 ≤200 ms.
No win-rate claims for reduced variants; no inference of live deadline guarantees.

## Compute and storage

03 only. At most 56 own processes (50 game workers + parent/supervisor + bounded
profile/build work), nice 10 plus SCHED_IDLE at exec, detached with setsid. Combined
Clasher census ≤100, preserving delay-fixes allowance of 40. Admission and monitoring
record the existing cache service. Recheck reservations/processes before launch.
All caches/raw game reductions/native builds under `/mpac`, outside HOME and git.
Commit only lane docs, small JSON and code, explicit staged paths, secret-scan staged
diff before each commit, then push. Keep PROGRESS current and retain technical receipts.
