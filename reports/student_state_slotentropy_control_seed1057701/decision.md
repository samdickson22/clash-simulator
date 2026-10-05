# Conditional slot exploration pilot decision

## Hypothesis

The accepted policy's card-choice distribution is very peaked even when several
cards are legal. `conditional_slot_entropy_coef` was added as a card-name-free,
permutation-invariant PPO bonus over legal hand slots after conditioning on a
placement action. It cannot directly reward playing instead of waiting. The
default is zero, preserving previous training behavior.

Focused validation: 75 structured-policy/opponent-league tests passed; Ruff and
mypy were clean. Tests cover known entropy, one/no legal slots, finite zero edge
cases, CLI compatibility, and isolated PPO-loss contribution.

## Matched four-update pilot

All arms restarted from accepted iteration 2 with seed 1057701, the 478-deck
all-card balanced curriculum, the same 12-worker PFSP league, frozen placement
location behavior, and 16,384 transitions.

- Coefficient 0.01 was behaviorally ineffective. It changed slot-query weights
  only slightly and left rollout metrics effectively identical to control.
- Coefficient 0.10 retained 8/12 utilization gates but was worse than the
  zero-coefficient control's 9/12; it uniquely lost the Battle Ram gate and
  added no unique passing archetype.
- Therefore conditional slot entropy is rejected as the cause of improvement.

The zero-coefficient control initially looked promising: historical gameplay
improved from 61-11 and +86 crowns to 63-9 and +96 crowns, while the 12-archetype
matrix improved from 18-6 with 6/12 utilization gates to 20-4 with 9/12 gates.
Training stability, allowed-parameter, and 696-permutation equivariance audits
all passed.

## Expanded held-out gate

The small-screen result did not generalize.

| Pool | Parent | Challenger | Crown change | Paired outcomes |
|---|---:|---:|---:|---:|
| validation, 24 games | 16-8, +16 crowns | 16-8, +7 crowns | -9 | 2 improvements, 2 regressions |
| held-out, 24 games | 16-8, +13 crowns | 11-13, +2 crowns | -11 | 0 improvements, 5 regressions |

The challenger is rejected and iteration 2 remains the accepted policy. The
diagnostic matrix must not be used as promotion evidence by itself. Remaining
reliable failures are Graveyard, X-Bow, and Goblin Barrel; Battle Ram is
seed-sensitive. The next policy experiment must target held-out matchup
generalization rather than global card-choice diversity.

