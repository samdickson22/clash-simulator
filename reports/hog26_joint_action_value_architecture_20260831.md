# Fresh Hog 2.6 joint action-value architecture

Date: 2026-08-31

Status: structural prototype and real MPS training smoke passed; no skill or
promotion claim.

## Why this replaces the repair family

The untouched terminal gate showed that the frozen reranker learned a useful
slow-push wait but applied the same intervention to a split-lane parent win and
turned it into a loss.  The reranker had only 24 training roots and depended on
expensive 12-branch terminal simulation.  Threshold tuning after that failure is
forbidden.

The replacement learns actor-visible action values from every ordinary complete
trajectory while PPO is already collecting it.  It is jointly optimized with
the actor and state critic rather than attached to a frozen policy after the
fact.

## Head structure

`FactorizedActionValueHead` mirrors the public action contract:

1. play/wait/ability value;
2. shared card-pointer value over the four current hand cards;
3. card-conditioned value over the exact 18-by-32 deployment grid;
4. mandatory public legal mask.

The head consumes only actor-visible encoded state/card/tile tensors.  It never
receives the privileged critic, simulator objects, opponent private state, or
future labels.  At d_model 128 and state width 192 it has 67,140 parameters.
Slot permutation tests are bit-exact.

A scalar policy gate is initialized to exactly zero.  Consequently arbitrary
changes to the initially random action-value head leave policy logits bit-exact.
The action-value Huber loss trains selected actions toward GAE/return targets;
PPO may learn to open the gate only after those values become useful.

## Performance and device evidence

Fixed batch 128, state width 192, d_model 128, full 2,306-action output:

- CPU median-style loop: 2.584 ms/batch, 49,529 rows/s;
- Apple MPS: 1.345 ms/batch, 95,191 rows/s;
- CPU/MPS legal-value maximum absolute difference: 1.91e-6;
- illegal negative-infinity masks: exactly equal.

This standalone latency is small relative to the full policy/simulator path.
Production collector attribution remains required before a long run.

## End-to-end smoke

The actual training CLI ran one fresh Simple Gym update on MPS:

- two environments, two rollout decisions, four transitions;
- objective-v1-gamma-v1 Simple reward, leak disabled;
- actor and learner both MPS;
- selected action-value loss 0.089360;
- one finite PPO optimizer step;
- gate moved from exactly 0 to -0.000249944 through joint training;
- update-1 checkpoint SHA-256
  `e1e398bbbc15225c10024757e03fa5d0824f88b90349bee8794a3ff327b05871`;
- checkpoint persisted the enabled config, 14 action-value state entries, update
  counter 1, and four transitions.

The first smoke then exposed and fixed a matched-experiment confound: constructing
the optional head advanced the global initialization RNG.  The head is now built
inside a forked RNG context.  A same-seed control/candidate rerun proved all 126
shared initial state entries bit-identical; the candidate has only the 14 declared
action-value entries, and its policy gate is exactly zero.

The corrected MPS A/B used seed 1240002 and identical four-transition rollouts:

- reward/absolute reward: 0/0 in both;
- play/no-op: 0.75/0.25 in both;
- entropy/type/location/slot entropy: exactly equal in printed precision;
- value loss, auxiliary hand/elixir losses, KL, explained variance, and episode
  counts: exactly equal in printed precision;
- control action-value loss: 0; candidate: 0.9221;
- control learn wall 0.68 s; candidate 0.72 s (single smoke only, not a throughput
  claim).

Corrected initial checkpoint SHA-256 values:

- control: `6f76247fdd048fda0e1342cf754370bfebf16144907335262f4825b55622fab4`;
- candidate: `adc801880f1ff60c3cdc05f4619fb41392746c79e8664c9420e09e99291d7257`.

The production-target head structure was then exercised through
`--fresh-factorized-action-head`.  Both arms use an explicit three-way mode
gate, shared slot-equivariant semantic+mechanics card pointer, and the unchanged
card-conditioned heatmap.  At seed 1240003, all 133 shared initial state entries
were bit-identical and only `action_value_head_enabled` differed in their model
configs.  Their four-transition pre-update MPS rollout evidence again matched:
reward, policy/value loss, entropy components, auxiliary losses, KL, explained
variance, play/no-op rate, and episode counts were equal in printed precision.
The candidate alone recorded action-value loss 0.2289.

Factorized initial checkpoint SHA-256 values:

- control: `33ad2b2ecda499a3a8583c773066f7b123a29df8291844bb5c84efd171c17b08`;
- candidate: `ec79de0126d10aec0b8a06bfe7a69ae23cc7a936c65847e853556cbf104aca74`.

Focused validation: 58 CPU tests plus the real MPS collector/GAE/PPO test passed;
Ruff is clean.  Existing whole-file `train_recurrent.py` mypy still reports its
11 pre-existing ndarray annotation diagnostics; the new isolated module is
mypy-clean.

## Next experiment

Do not train this random 158k smoke model for skill.  Build a fresh matched
Hog-2.6 family from one causal imitation initializer:

- control: explicit play/wait/ability gate, shared slot-equivariant pointer,
  unchanged exact heatmap, no action-value head;
- candidate: identical model/data/seed plus this action-value head and return
  loss;
- three seeds;
- gamma-correct/no-leak Simple reward;
- short random/strategy/frozen-parent PFSP stages;
- collapse screen first, then the established 72-game breadth matrix.

Reject if any seed collapses to passivity/overplay, the candidate loses a held-
out strategy bucket, or collector throughput falls below 95% of control.  Only a
passing matched family may receive substantial CUDA training.
