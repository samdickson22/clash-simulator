# Hog 2.6 scalar hazard repair decision

Decision: reject further global scalar play-hazard tuning for the retained Hog
2.6 lineage. Keep the parent checkpoint unchanged.

## Retained parent

- checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt`
- SHA-256: `28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`

## New evidence

The stored-gate PPO implementation is numerically stable and preserves the
behavior policy support, but neither controlled run passed the full paired
promotion matrix:

- competence seed 1193001: retrospective update 6 tied the parent on the
  expanded 56-game-per-arm matrix (candidate 29-27, parent 30-26, exact crown
  tie); no promotion.
- hardening seed 1193201: the small screen was positive, but the expanded
  matrix regressed (candidate 30-26, parent 31-25, crown -0.018/game); no
  promotion.

The first exact-fanout counterfactual corpus retained 14 training roots and 6
validation roots. A four-epoch scalar-hazard fit reached all 6 validation
corrections but changed no deterministic gameplay: candidate and parent were
bit-for-bit identical across the 56-game-per-arm screen (36-20 each). A
20-epoch fit moved far enough to cross the play threshold, then regressed the
development screen from parent 6-6 with +0.333 crown/game to candidate 3-9 with
-0.583 crown/game.

Older localized hazard-adapter lineages show the same failure mode. One gated
adapter scored 0-4 against both bridge-pressure and slow-push at update 52 and
fell from mean strategy score 0.250 at update 52 to 0.083 at update 54. A later
gain-0.2 gate lost all 12 strategy games while no-oping on roughly 94.6% of
playable decisions.

## Interpretation

A single scalar can only shift placement versus waiting globally. It cannot
express that one card/tile is better while another placement at the same state
is worse. Small changes are inert under the hard threshold; large changes
alter many unrelated states at once. This is an architectural mismatch, not a
learning-rate problem.

## Next gate

Use state-specific counterfactual supervision over the complete action:
play/wait/ability, hand slot, and placement tile. Candidate generation must be
stratified across playable hand slots and arena regions, and roots must span
multiple game phases and opponent styles. Truncated rollouts must stop at the
first terminal and use a disclosed bootstrapped value only for nonterminal
branches. Any trained candidate still has to beat this retained parent on the
full paired matchup matrix; offline preference accuracy alone is not
promotion evidence.
