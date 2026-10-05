# Hog 2.6 paired asymmetric evaluation audit

## Decision

The retained champion is still the best deployable policy, but its previous
asymmetric evaluation evidence was not seat-paired. The evaluator is corrected,
and the first trustworthy paired matrix shows that the champion is a narrow Hog
reactive baseline rather than a generally competent policy.

Do not promote a new policy from the old asymmetric reports. Future promotion
gates must declare `paired_asymmetric_matchups=true` and prove that the logical
candidate and opponent decks are byte-for-byte identical across both physical
seats in every matchup pair.

## Evaluation defect

`eval.py` intended games `2k` and `2k+1` to be the same matchup with the
candidate swapping seats. It constructed separate player-0 and player-1
environments, however, and each environment sampled its physical player pools
sequentially through one RNG. Swapping the pools therefore changed which
opponent deck was sampled. Nominally paired games had the same seed but different
candidate/opponent deck identities, so matchup difficulty and seat were
confounded.

This was directly observed in the pre-fix seed-1163101 matrix: every adjacent
seat pair changed the opponent deck.

## Correction

For asymmetric evaluation only:

1. sample the logical candidate and opponent deck once from their weighted pools;
2. shuffle both once using a deterministic matchup-local deck RNG;
3. install those already-ordered decks without consuming battle RNG;
4. swap only their physical player assignment for the second game.

Ordinary environment sampling and training behavior are unchanged. Evaluation
JSON now records `paired_asymmetric_matchups=true` when the contract is active.

Source changes are limited to:

- `src/clasher/rl/deck_pool.py`
- `src/clasher/rl/selfplay_env.py`
- `src/clasher/rl/eval.py`
- focused tests in `tests/test_rl_eval.py` and
  `tests/test_rl_sampling_deck_pool.py`

## Verification

- Ruff: clean
- Mypy on all three changed source modules: clean
- Focused evaluation/deck/strategy tests: 33 passed
- Real two-seat proof, seed 1163201: candidate deck identical, opponent deck
  identical, seats `[0, 1]`
- Exact repeated two-game record SHA-256:
  `7a69feff6ab8c754e158a115d18a06e380b2aa8300746c2ca5f76f2ccfae84ca`
- Corrected 72-game matrix: all 36 adjacent matchup pairs passed exact deck
  identity and `[0, 1]` seat-order checks

## Corrected champion profile

Champion:
`checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt`
(`28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`)

Fixed Hog 2.6 candidate deck, six exact opponent decks, both seats, and all six
strategy bots produced:

| Strategy | Record | Crown differential/game | Defense event success |
| --- | ---: | ---: | ---: |
| bridge-pressure | 0-12 | -2.333 | 0.292 |
| slow-push | 1-11 | -2.000 | 0.205 |
| balanced | 1-11 | -1.167 | 0.400 |
| reactive-defense | 2-10 | -1.167 | 0.284 |
| spell-control | 3-9 | -0.750 | 0.407 |
| split-lane | 3-9 | -0.833 | 0.413 |
| **total** | **10-62** | — | — |

Controls clarify the result:

- balanced StrategyBot on a paired Hog 2.6 mirror: 13-11;
- random bot on paired diverse decks: 7-17.

The model can execute a recognizable Hog mirror plan, but it does not generalize
its defense to diverse archetypes. Across the paired strategy matrix it went:

- 1-11 against bait/Bomb Tower;
- 1-11 against Giant/Mini P.E.K.K.A;
- 4-8 against Golem/Night Witch;
- 0-12 against P.E.K.K.A/Battle Ram;
- 2-10 against a second bait/Wall Breakers deck;
- 2-10 against Giant/Prince.

The apparent aggregate seat imbalance was not stable under controls: Hog mirror
was 6-6 as player 0 and 7-5 as player 1, while diverse random was 5-7 and 2-10.
This does not support a remaining universal canonical-seat defect; it supports
matchup-specific weakness and small-sample variance.

## Training consequence

The next league must not be mirror self-play. It must use learner-only updates
against resident frozen/checkpoint/strategy opponents, with opponent actions
excluded from PPO loss. Initial opponent weighting should emphasize:

1. bridge-pressure;
2. slow-push;
3. balanced/reactive-defense;
4. spell-control and split-lane as retention opponents.

Deck sampling must deliberately cover bait, Giant beatdown, Golem beatdown, and
P.E.K.K.A bridge-spam rather than drawing a generic pool and hoping those
matchups appear. Hog mirror remains a retention gate, not the main curriculum.

The compact 64-wide fresh lineage is separately rejected in
`reports/hog26_capacity48_compact_f3_seed1162001/decision_20260828.md`; it played
no cards in 12 stop-gate games and must not initialize this league.
