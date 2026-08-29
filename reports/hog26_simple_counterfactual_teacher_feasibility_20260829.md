# Simple Gym counterfactual teacher feasibility

## Decision

Proceed to a small CPU-parallel label corpus and a held-out spatial-only A/B.
Do not resume static PPO or StrategyBot tile distillation.

## Exact branching contract

`SimpleGymRuntime.fanout_row_()` uses the same explicit mutable tensor inventory
as selective reset.  It copies one live row across state, action, effects,
travel, death/triggered payloads, buffs, lifecycle, modifiers, navigation,
policy mechanics, abilities, outcomes, attack/river/spawn sidecars, projection
caches, and runtime status fields.  Immutable catalogs remain shared.

The focused gate copies a deliberately nonuniform row, verifies every captured
batch-leading mutable tensor equals the source, then advances eight no-op ticks
and proves row-exact observations and rewards throughout.

## Probe

Checkpoint:
`checkpoints/hog26_simple_hazard_competence_seed1193001/policy_v2_update_000000.pt`
(the exact retained parent rebound to the Simple Gym capacity/vocabulary).

One balanced-opponent state was warmed for 20 decisions.  Eight common-public-
legal root actions were fanned out and continued deterministically for 24
decisions (9.6 seconds of battle time) with gamma-correct reward ranking.

CPU results:

- candidate phase: 15.248 seconds, 0.525 candidates/s
- best action 1414: discounted return -0.097240
- second action 1203: -0.126064
- no-op 2304 and four other actions: -0.259814
- all branch roots passed exact actor-field and public-mask row equality
- ranking exactly reproduced the earlier scalar row-0 probe

MPS results:

- candidate phase: 33.467 seconds, 0.239 candidates/s
- 2.20x slower than CPU
- complete action ordering matched CPU
- return magnitudes differed slightly, so cross-device numeric identity is not
  claimed and labels must pin one backend

CPU is the local label authority.  The scalar implementation took 47.812
seconds for the same eight candidates, so exact fanout provides a 3.14x local
speedup.  At 15.25 seconds/state, 1,000 labels are roughly 4.2 serial hours;
states are independent and can be process-parallelized.

## Next gate

Generate a small replay-disjoint corpus across balanced, bridge-pressure,
spell-control, reactive-defense, slow-push, split-lane, and random states.
Accept labels only when the best candidate beats both no-op and the parent's
chosen action by a predeclared return margin.  Fine-tune spatial heads only with
the retained parent anchored, then require multi-bucket free-running gains.

Evidence:

- `reports/hog26_simple_counterfactual_probe_seed1193401.json`
- `reports/hog26_simple_counterfactual_vectorized_probe_seed1193401.json`
- `reports/hog26_simple_counterfactual_fanout_probe_seed1193401.json`
- `reports/hog26_simple_counterfactual_fanout_mps_probe_seed1193401.json`
