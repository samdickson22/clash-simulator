# DAgger stationary-behavior input reuse

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Scope: source work and bounded single-process parity tests only; no throughput
benchmark, corpus collection, or training was run.

## Finding

The authoritative corpus collector currently does redundant work on every
checkpoint-behavior decision:

1. `_policy_action` builds a full actor/critic observation and a legal mask for
   each seat.
2. Corpus serialization rebuilds the full observation and mask for each seat.
3. `SelfPlayBattleEnv.step` recomputes each seat's spendability because the
   already-built masks are not passed as `pre_action_masks`.

The corpus stores only actor-public tensors, and deterministic behavior action
selection does not use the critic value. The candidate therefore adds:

- `StructuredObservationBuilder.build_actor`, whose public arrays are exact
  matches for the corresponding arrays from `build`;
- `prepare_behavior_decision`, which builds both masks once and only the public
  observations requested by the collector;
- `actor_policy_action`, which consumes the prepared public observation and
  mask without running the critic encoder;
- mask-reusing random and data-driven strategy selection; and
- a deterministic `(shard_index + episode_id) % 2` behavior-seat schedule.

There are no card-name branches. Strategy resolution is limited to the shared
`STRATEGY_NAMES` registry.

## Static work removed per decision

| Workload | Current full observation builds | Candidate actor-only builds | Current legal-mask evaluations | Candidate legal-mask evaluations |
| --- | ---: | ---: | ---: | ---: |
| Checkpoint self-play, store both seats | 4 | 2 | 6 | 2 |
| Oracle self-play, store both seats | 2 | 2 | 4 | 2 |
| Checkpoint/oracle learner vs stationary, store behavior seat | unsupported | 1 | unsupported | 2 |

The current checkpoint rows also run two critic encoders; the candidate runs
zero. The mask counts include the two spendability evaluations performed by
`env.step` when `pre_action_masks` is omitted.

These are source-attributed call counts, not a wall-clock speedup claim. A
matched corpus preflight must be timed after the shared compute window is
released.

## Exactness evidence

Command:

```bash
PYTHONPATH=src:. uv run pytest -q tests/test_rl_dagger_behavior.py
```

Result: `8 passed`.

The fixed-seed probe uses seed 2301, four decisions, a deterministic recurrent
policy, and a separately seeded stationary-random stream. Baseline full-input
inference plus step-time mask recomputation and candidate actor-only inference
plus `pre_action_masks` produced the same digest in every engine mode:

```text
off     2e1648dc381b93013919677a770f2ab8361a4fbbc3fb1fcdc27c79ca7ce462bf
shadow  2e1648dc381b93013919677a770f2ab8361a4fbbc3fb1fcdc27c79ca7ce462bf
on      2e1648dc381b93013919677a770f2ab8361a4fbbc3fb1fcdc27c79ca7ce462bf
```

Shadow mask mismatches were zero for baseline and candidate. The digest covers
both masks, both actions, tick, entity count, rewards, termination, and both
recurrent-state tensors. A separate test asserts exact equality of the public
arrays returned by full and actor-only builders, and exact deterministic action
and recurrent-state equality against the legacy full `_policy_action` call.

Additional focused gates:

```text
7 passed, 8 deselected in 0.76s
Ruff: clean for dagger_behavior.py and test_rl_dagger_behavior.py
mypy: clean for dagger_behavior.py and structured_obs.py
```

## Training-branch integration

Do not port this worktree's stale/untracked `imitation.py`. Port the isolated
candidate commit, then wire the authoritative collector as follows.

1. Add `behavior_opponent: str | None` to corpus metadata, shard config,
   fingerprint, manifest-facing metadata, and CLI. Accept `random` and
   `strategy:<shared-name>`. Keep `None` as legacy self-play behavior.
2. For stationary mode, choose the learner seat with
   `behavior_player_for_episode(shard_index, episode_id)`. Save only that seat's
   expert-labeled sample; the stationary seat is an environment actor, not a
   DAgger training example. This makes `samples == decisions` for stationary
   mode and preserves `samples == 2 * decisions` for legacy self-play.
3. On each decision, call `prepare_behavior_decision` after oracle labeling.
   Pass `(0, 1)` for legacy self-play or `(behavior_player,)` for stationary
   mode. Use the returned observation and mask for both behavior inference and
   `_append_observation`.
4. In stationary mode, execute the learner's oracle action when no behavior
   checkpoint is supplied or the DAgger expert coin wins. Otherwise use
   `actor_policy_action`. Always choose the other seat with `stationary_action`.
   Give stationary random its own deterministic RNG stream so shadow-mask
   sampling cannot perturb its action trace.
5. Pass `prepared.action_masks` to
   `env.step(executed_actions, pre_action_masks=prepared.action_masks)` in every
   mode. Strategy bots must receive their prepared mask through `action_mask=`.
6. Include opponent spec, stationary-label scope, behavior-seat schedule, and
   stationary RNG seed derivation in the corpus fingerprint. Old shards must
   not be reusable under a different behavior distribution.
7. Reset recurrent behavior state at every episode boundary. When the behavior
   seat alternates, initialize the newly selected seat from the model's initial
   state and reset its previous action/reward/start fields.

Before a production corpus, run a small matched legacy collector A/B and pin
the corpus array hash, expert-action distribution, executed-action trace, and
zero shadow mismatches. Then run a separate stationary preflight that verifies
sample count, seat balance, random/strategy action legality, shard resume, and
metadata fingerprint rejection across opponent-mode changes.
