# Admission-scope decision v1 (council pilot)

Decided 2026-09-30. The user approved this narrowing; the coordinator relayed it. Machine-readable form: `admission-scope-decision.json`, which a test checks against the lists enforced in code.

**Decision.** The Tier A admission `m0-tier-a-fresh-v7` (receipt `aeb4a2ff…`, runtime `native-final-v7`) binds only the admitted-simulator scope. The pilot's own source freeze pins training-only code instead.

## Scope

- **ADMISSION_BOUND** covers every `src/clasher/**/*.py` module the v7 admission pins, except the training-only list below. That is 342 of 351 modules. Each one must exist in the pilot runtime, be pinned by the pilot freeze, and hash exactly as in `admission.source_pins`. This includes `rl/model.py`, `structured_obs`, `public_observation`, `public_action_mask`, `public_policy_contract`, `selfplay_env`, `council_recurrence`, `council_opponents`, the scripted opponents (`public_scripted_opponent`, `strategy_bots`, `scripted_demonstrations`), `reward_model`, `eval.py`, and all simulator and card code (`battle.py`, `entities.py`, `cards/*`, `torch_sim/*`, …).
- **TRAINING_ONLY** covers 9 modules. They are pinned by the pilot freeze, and their digests may differ from the admission.

| Module | Why it cannot change observation, legality, dynamics, reward or opponents |
| --- | --- |
| `rl/train_recurrent.py` | CLI, orchestration and checkpoints. Observation stacking and storage, both admitted collectors, truncation bootstrap, GAE, `ppo_update`, `_sequence_inputs`, the milestone planner, `save_checkpoint` and `RolloutBatch` are bound at the AST level. The new learner-side loop calls those helpers in the admitted order. |
| `rl/parallel_rollout.py` | Actor-process transport. The admitted worker collector, the worker-path environment construction, opponent specs and the builder factory are bound. The new code steps the same admitted environments and opponents. |
| `rl/shared_rollout_ipc.py` | Shared-memory buffers for the asynchronous trainer. Not on the council path. |
| `rl/council_pilot.py` | Config schema, argument validation, commands and this verifier. The actor contract, opponent-pool publication, initializer checks, critic warm-up rule and evaluation commands are bound roots. |
| `rl/council_budget.py` | Compute-ledger accounting only. |
| `rl/council_monitor.py` | Monitoring-only alarms. |
| `rl/council_warmstart.py` | Runs admitted script games and the imitation fit. It chooses training data only. |
| `rl/council_evaluation.py` | Protocol and scoring. Games are played by the bound `eval.py`, and the protocol file is compared with `build_protocol` before execution. |
| `rl/imitation.py` | Supervised fit and corpus I/O. Names imported by bound modules are auto-bound. |

**Bound symbols inside changed training-only modules.** Three sets of definitions must be AST-identical to the admitted source:

- the declared roots;
- every name an admission-bound module imports from that module, found by parsing all bound modules (for example `_stack_step_inputs`, which the bound opponent adapter and evaluator use);
- the runtime closure of same-module definitions that those names reference.

Imports are compared per alias. Shadowing a bound name is refused. If a bound module imports a whole training-only module, that module must stay byte-identical.

## Verification (fails closed)

`council_pilot.require_pilot_admission` first runs `verify_pilot_source_scope` against the admission's own pins and admitted sources. It then calls the unchanged ledger check `require_admission` with exactly the admission-bound subset, mapped from the pilot root to the admitted root. The admitted `require_admission` checks the fresh declaration against the source tree it is imported from, so it can only pass inside the admitted runtime. When the pilot runtime root differs, the ledger check therefore runs in a subprocess from `native-final-v7` (admitted code, numba cache in a temp dir). The receipt it returns must equal the claimed receipt. It refuses in each of these cases:

- a bound module is missing, unpinned, pinned with a different digest, or changed on disk;
- the runtime contains a `src/clasher` file the admission never pinned;
- a training-only module is unadmitted, unpinned, or differs from the freeze;
- a pin is stale or lies outside the pilot root;
- a bound definition changed;
- any ledger, seal, artifact, calibration or game-data check fails.

Tests: `tests/test_pilot_admission_scope.py`. They include drift in a bound file (refused), drift in a training-only file (refused against a stale freeze, allowed once re-frozen), bound-symbol drift (refused), extra modules, and real-v7 checks that `battle.py` or `ppo_update` drift is refused.

## Recorded deviation

In learner-side inference mode, each environment owns one council opponent adapter. It is seeded from its global index, and its logs are `worker-envNNN-*.jsonl`. The worker path uses one adapter per actor process instead. The mixture, the frozen weights and opponent behavior are unchanged, because they are decided by the bound `council_opponents.py`. Only the random stream that draws per-match assignments differs. This makes transitions independent of the actor partition.

## Unchanged recipe

The recipe is unchanged:

- 128-step chunks, 2 epochs, lr 1e-4, clip 0.2, γ 1, λ 0.95;
- target KL 0.02, critic warm-up of 20 updates, sequence minibatch 2;
- exact full-prefix recurrent reconstruction through the bound `council_recurrence`;
- the bound actor contract.
