# Frozen-actor value-guided search decision

## Status

The accepted actor remains `checkpoints/student_state_symmetry_dagger_seed1056901/iteration2.pt` (`dac7f2327efcfaa6ebd66ebebc6551447ee6e2ede5a5af360b5b816a9fc506f2`). No actor checkpoint from the experiments below is promoted.

The value-guided search configuration passed the initial validation and held-out screens, but failed expanded held-out and fresh-quarantine safety gates. It is rejected as a controller. The outcome head remains a useful diagnostic artifact.

## Actor experiments rejected

- Four PPO updates with conditional legal-slot entropy coefficients `0.01` and `0.10` did not improve card utilization; `0.10` regressed Battle Ram.
- The coefficient-zero matched PPO control improved a small screen but regressed on expanded validation and held-out decks.
- Averaging the two independent PPO policy deltas reduced validation variance but the selected `alpha=0.50` blend regressed on held-out decks.
- Replacing the narrow rehearsal corpus with a 32,768-state, 102-episode exact behavior anchor covering all 66 enabled cards reduced KL drift but still lost crown margin on validation.

These results close the current actor-fine-tuning branch. More rehearsal weight is not justified by the evidence.

## Public outcome head

The actor was frozen and used to collect exact simulator features from 384 battles:

- train: 256 battles, 20,648 sampled states
- validation: 64 battles, 5,586 sampled states
- held-out: 64 battles, 4,768 sampled states
- opponents: balanced, bridge pressure, slow push, spell control, reactive defense, split lane, random, and self-play
- perspectives: both players, producing balanced win/loss labels
- deck splits: 478 train, 105 validation, and 105 held-out decks

The selected 75,137-parameter MLP head is:

`checkpoints/student_state_public_outcome_seed1058201/public_outcome_value.pt`

SHA-256: `e70e957761df1a787afe45bfefb2636200b7989e0fed71d169d0aa4418e43d8e`

Raw mean AUC across early/middle/late game:

| Split | AUC | Mean Brier |
| --- | ---: | ---: |
| Train | 0.814 | 0.194 |
| Validation | 0.723 | 0.215 |
| Held-out | 0.746 | 0.210 |

The exact zero-sum paired evaluation used by search improves mean AUC to 0.780 on validation and 0.806 on held-out games.

## Validation-selected search configuration

- rollout horizon: 4 policy decisions
- candidate cap: 6
- query stride: every 32 decisions, only when the actor chose no-op while a play was legal
- minimum predicted win-probability gain: 0.02
- opponent continuation: the actual deterministic strategy bot

Across 20 matched validation games using identical decks, seeds, seats, and opponent actions:

| Policy | W-L | Total crown differential |
| --- | ---: | ---: |
| Frozen actor | 15-5 | +27 |
| Actor plus search | 17-3 | +31 |

There were 23 overrides and no win-to-loss outcome regressions. Reactive-defense outcomes stayed 3-1 with equal crown margin. Bridge-pressure outcomes stayed 4-0 and crown differential improved from +6 to +7.

## First held-out gameplay screen

Eight matched games against the balanced strategy bot used the untouched held-out deck split:

| Policy | W-L | Total crown differential |
| --- | ---: | ---: |
| Frozen actor | 5-3 | +3 |
| Actor plus search | 7-1 | +12 |

The search made 16 overrides. Two baseline losses flipped to wins (`0-3` to `3-1`, and `1-3` to `3-0`), with no outcome regressions.

## Expanded held-out failure

Across balanced, reactive-defense, bridge-pressure, slow-push, spell-control, and split-lane opponents, the original four-step search eventually produced a hard split-lane regression: one Minions override changed a `3-1` win into a `1-2` loss. The leaf value assigned the override `0.761` win probability versus `0.707` for the actor's no-op.

An eight-step diagnostic correctly rejected that specific override, but the deeper configuration independently failed on a new split-lane validation seed, changing a `3-0` win into a `1-2` loss. Deeper rollout alone is therefore rejected.

## Risk-gated search and untouched quarantine

A general emergency-only gate was added: search could override only when the base action's predicted win probability was at most `0.65`. On 24 validation games across balanced, reactive-defense, bridge-pressure, and split-lane opponents, this candidate improved `18-6, +30` crowns to `20-4, +34` with no outcome regression.

To avoid retuning on exposed held-out games, a new procedural pool was generated with seed `1059401`. Every exact signature from the previous 688-deck universe was removed. The resulting quarantine contains 395 decks across all 12 archetypes with zero signature overlap.

Across 24 one-shot quarantine games spanning six strategy opponents:

| Policy | W-L | Total crown differential |
| --- | ---: | ---: |
| Frozen actor | 21-3 | +38 |
| Risk-gated search | 20-4 | +33 |

The search changed a `1-0` win into a `1-2` loss with a Tombstone override despite a predicted gain from `0.542` to `0.593`. This is a hard no-regression failure.

## Decision

Reject online state-value-guided action reranking. The head generalizes as an observational outcome predictor, but it is not a reliable causal estimator for counterfactual actions: candidate branches are out of the behavior-policy distribution used to train it.

Keep the accepted actor unchanged. The next justified direction is an exact counterfactual action-value/repair dataset: sample actor states, branch diverse legal root actions under matched continuation randomness, label their realized relative outcomes, and train a small action-conditioned ranking head. This tests action effects directly and avoids using a generic state-value model as a Q-function.
