# Hog 2.6 terminal outcome label authority

Decision: reject terminal labels ranked only by gamma-discounted dense reward.
Use learner-relative terminal win/draw/loss as the primary ordering and observed
discounted reward only as a tie-break within the same outcome class.

## Why the prior terminal contract was insufficient

The Simple Gym emits dense objective-potential deltas plus a one-shot terminal
win/loss reward. Counterfactual returns use decision gamma 0.995. At 600
decisions, a terminal reward is multiplied by approximately 0.049. A branch
with locally favorable tower shaping can therefore outrank a branch with a
better final match outcome even when both simulations reach terminal.

This reproduces the exact failure mode under repair: locally attractive moves
that lose the global game. Merely increasing the horizon does not correct the
label ordering.

## V4 contract

- `SimplePytorchTrainingCollector.collect()` exposes terminal winners only
  through the opt-in `include_terminal_winners=True` path. Ordinary PPO rollout
  dictionaries and `RolloutBatch` remain unchanged.
- The probe records the first terminal winner for each branch and maps it into
  learner-relative outcome `1`, `0`, or `-1`.
- Candidate order is lexicographic: terminal outcome, observed discounted
  reward, then total return. Terminal probes must have zero bootstrap, so the
  latter two are equal in accepted corpora.
- The compiler requires v4 outcome authority, validates every outcome, and
  stores `root_candidate_outcomes` separately from dense scores.
- Preference training compares outcome first. Any win/draw/loss difference
  dominates dense reward; dense reward ranks only equal-outcome candidates.

## Evidence

Focused collector, probe, compiler, and trainer gates passed 67 tests with 6
device skips before the final outcome helper test was added; the final focused
gate passed 59 tests with 5 skips plus 17 outcome-specific tests. Ruff, mypy,
and diff checks were clean.

A real MPS two-branch terminal smoke from warmup 13 reached terminal after 416
decisions. Parent action 1944 and no-op 2304 were both labeled learner loss
`-1`; their critic bootstrap was exactly zero. Their dense returns differed
(`-0.1394667999` versus `-0.1415800419`) and are therefore valid same-outcome
tie-break evidence, not substitutes for match result.

No v3 corpus or checkpoint is eligible for the outcome-first repair. Training
and held-out probes must be regenerated under v4.
