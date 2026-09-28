# Hog 2.6 epsilon-mixture behavior decision

Decision: reject epsilon-mixture PPO behavior before training. No production
trainer code or checkpoint was retained.

## Hypothesis

The retained Hog policy is competent only under deterministic decoding. Unit
temperature stochastic play had previously fallen from 9-3 to 0-12. The
bounded alternative assigned `1-epsilon` probability to the policy's exact
deterministic action and `epsilon` to its full legal stochastic distribution.
Collector and PPO log-probability recomputation were implemented and tested on
CPU and MPS before gameplay screening.

## Development screen

Twelve paired games per arm used identical seeds, seats, Hog deck, and held-out
opponent decks.

| Arm | W-L | Crowns/game | Placement rate |
|---|---:|---:|---:|
| deterministic | 7-5 | +0.500 | 7.066% |
| epsilon 0.01 | 9-3 | +0.667 | 7.527% |
| epsilon 0.02 | 9-3 | +1.000 | 7.803% |
| epsilon 0.05 | 5-7 | -0.250 | 8.675% |
| epsilon 0.10 | 5-7 | -0.167 | 9.400% |

Raw report: `reports/hog26_epsilon_behavior_seed1200801.json`.

## Disjoint confirmation

The two initially positive arms were checked on a different 24-game-per-arm
quarantine pool and seed set.

| Arm | W-L | Crowns/game | Placement rate |
|---|---:|---:|---:|
| deterministic control | 14-10 | +0.750 | 7.056% |
| epsilon 0.01 | 10-14 | +0.125 | 7.507% |
| epsilon 0.02 | 10-14 | +0.042 | 7.814% |

Raw reports:

- `reports/hog26_epsilon_behavior_confirmation_eps1_seed1200901.json`
- `reports/hog26_epsilon_behavior_confirmation_seed1200901.json`

Both exploratory arms reversed four wins and materially reduced crown edge.
The development gains were noise. Because the behavior distribution itself
failed admission, PPO training would not be attributable and was not run.

## Interpretation

Even one percent unstructured full-action exploration is too destructive for
this brittle policy. The problem is not solved by reducing generic stochastic
noise. Future work must obtain structured, state-conditional alternatives from
a competent teacher/search procedure or replace the policy architecture/data;
it must not resume temperature, scalar hazard, factorized gate, or epsilon
sweeps.
