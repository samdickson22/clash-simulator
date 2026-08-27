# Unified practical Gym architecture — final refresh 2026-08-27

## Decision

Keep `TensorResidentEngine` as the exact-debug verifier. Use
`SimpleGymRuntime` as the production RL executor.

The accepted production source is
`504444ea400ff8bf595c0386ff000afe2c1f3490`. It is a unified,
fixed-shape tensor Gym at 50 ms resolution. Policy-visible identity, privacy,
legality, action success, history, reward, reset, and outcomes are contracts;
Python-only scalar/event/RNG details are verifier concerns.

## Production topology

The runtime owns one dense stable-ID entity table for towers, troops, and
buildings plus bounded aligned state/pools for mechanics with different
lifetimes:

- attack locks, cooldown fractions, shields, charge, ramps, statuses, and
  delayed kamikaze contact;
- visibility, Champion ability, special travel, river jump, collision, mass,
  and hover state;
- direct, projectile, line, fan, chain, area, rolling, travel, and triggered
  effects;
- death, delayed, periodic, scheduled, payload-container, and heterogeneous
  spawns;
- action/cycle state, actor/critic projection, reward history, and outcomes.

Setup may inspect Python game data and typed names once. Runtime dispatch is
numeric: stable IDs, card-aligned tensors, fixed phase order, and bounded
capacity. Unknown, malformed, duplicate, or partially represented declared
profiles fail closed.

## Tick ownership

One `SimpleGymRuntime.step_tick` owns the complete transition:

1. validate simultaneous actions, abilities, spells, and atomic deployments;
2. spend elixir, rotate committed cards, allocate typed bodies, and initialize
   every aligned state plane;
3. advance deployment, ability, visibility, travel, status, buff, and retained
   clocks;
4. acquire/retain stable-ID targets, route ground/hover/air bodies, start or
   advance river/special travel, and resolve owner-mirrored dense contact;
5. allocate and advance unified effects, including status and impulse;
6. resolve deaths, payloads, children, scheduled/periodic work, and capacity;
7. regenerate elixir, advance match phases, publish reward/outcome,
   observations/masks/history, and selectively reset terminal rows.

Pending bodies participate in targeting/effects/contact while their action and
movement sources remain deployment-gated. Delayed kamikaze contact is a
serialized numeric lifecycle, not a card-name branch.

## Policy boundary

The backend preserves:

- `canonical_lane_globals=true`;
- public-action-mask contract v2 from actor projection only;
- actor-private own hand, Next, elixir, entities, and ability state;
- an optional separate privileged critic never consumed by the actor mask;
- typed lookup with unknown and Hero/Evolution variants fail-closed rather than
  base-collapsed;
- simulator legality and public confidence legality as separate domains;
- action success, play history, previous action/reward, reset, reward, done,
  and winner; and
- recurrent hidden/cell state in the collector and newer-main wrapper.

Archer Queen's ability is available when exactly one supported own visible
live Queen is deployment-ready with sufficient elixir and ready public state.
Ambiguous multiple owners fail closed.

The 494-token vocabulary includes distinct Hero/Evolution identities. The
admitted 66-card pool has no variant root, so this is an identity/fail-closed
guarantee rather than a variant-gameplay claim.

## Mechanic frontier

The accepted generalized owners cover all 66 admitted base roots and include:

- homogeneous, heterogeneous, death, delayed, periodic, scheduled, rolling,
  and payload-container materialization;
- direct/projectile/area, multi-target, chain, line, fan, rolling, periodic,
  tower, charge, and damage-ramp attacks;
- shields, slow/stun, Rage, death bursts, recoil, push, attraction, mass, body
  separation, and building avoidance;
- Crown Tower retaliation and King activation;
- stable first-hit/retarget locks and capacity-atomic attack commit;
- visibility, Champion ability, special travel, hover, and river jump; and
- deterministic match phases, reward, projection, reset, and collection.

## Validation matrix

| Gate | Result | Authoritative evidence |
|---|---:|---|
| Admission | pass | 66/66 roots, 33/33 decks, profile `9e8dbfe1...` |
| Isolated-main CPU | pass | 406 passed, 248 CUDA skips |
| Strategy/action geometry | pass | 85 passed |
| Exact-source CUDA mechanics | pass | 222/222 at `504444ea` |
| CUDA terminal replay | pass | two replays each; tick 6000 tiebreak and tick 3600 crown; deterministic/native/committed/zero-fallback |
| CUDA throughput | pass | 410.053 row-ticks/s median; 820.106 actor transitions/s; 10 launches; zero sync |
| Newer-main CUDA route | pass | 191/191 at `b1ff9f1e` |
| Real recurrent policy | pass | 494-token policy; legal actions; `[1,2,32]` hidden/cell; native/committed/admitted; zero fallback |
| Live-main preservation | pass | isolated branch; live dirty checkout/process/model/data/checkpoints untouched |
| Real-corpus calibration | bounded | structural channels pass; combat labels unavailable; 37/37 OT sample misses Wilson confidence floor |

The exact accelerator evidence is aggregated in
`reports/simple_gym_cuda_a6000_contact_final_20260827.json`.

## Newer-main integration

Integration commit `b1ff9f1e2e1380071cca62afab68afdbb5dfdef9`
contains the exact `504444ea` Simple tree with zero mismatches across 196
selected paths. It adds `--simulation-backend simple-pytorch`, uses the
committed actor-v2 provider, converts collector output to PPO rollout shape,
persists mask/reward/artifact metadata, and passes a CPU PPO update plus CUDA
policy smoke.

The route is intentionally fresh-only and rejects resume. This is the safe
release posture: no old checkpoint silently crosses simulator/reward/
observation domains. The live dirty main checkout was not altered. See
`reports/simple_pytorch_main_final_integration_20260827.md`.

## Accepted boundaries

This architecture does not claim the client's full navigation graph,
presentation trajectories, hidden RNG, Evo/Hero gameplay, exact video combat,
or exhaustive free-running visitation. Arrows wave collapse, deterministic
Graveyard geometry, spirit homing in place of hop arcs, and dense contact
steering are explicit practical approximations.

## Final status

**Production accepted for fresh practical RL training.** All source, terminal,
accelerator, recurrent-policy, and isolated-integration gates are exact-current;
the verifier split and evidence boundaries remain explicit.
