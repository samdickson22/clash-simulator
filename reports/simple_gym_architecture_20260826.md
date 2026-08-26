# Unified approximate Gym architecture — 2026-08-26

## Decision

Keep `TensorResidentEngine` as the exact-debug mechanic verifier. Do not use its
retained-owner topology as the production RL executor.

Build a parallel, unified Gym backend that mirrors the policy-relevant game at
50 ms resolution. It may differ from the Python simulator in unobserved event
ordering, scalar types, CPython RNG state, and sub-tick float-clock artifacts.

The decision follows the bounded H200 profile in
`resident_h200_smoke_20260826.md`: one capacity-16 tick launched 275,608 CUDA
kernels and synchronized 19,231 times. This is an architectural eager-op
problem, not a remaining card-specific optimization.

## Production state

Use one dense entity table for towers, troops, buildings, projectiles, and area
effects. Retain only policy-relevant fields:

- active, stable internal ID, kind, owner, serialized card ID;
- integer logic-unit position and velocity;
- HP/max HP, shield/max shield;
- status bits and integer tick deadlines;
- target stable ID, deployment, cooldown, and lifetime ticks;
- battle tick, elixir, hand, Next/cycle, tower slots, winner, and done.

Internal stable IDs exist for deterministic ordering and must not replace the
typed public vocabulary tokens in observations.

All time is integer 50 ms ticks. Compile serialized millisecond parameters to
ticks once at the catalog boundary.

## Tick

The production tick is a small number of broad vector passes:

1. validate actions, spend elixir, rotate cards, allocate summons;
2. advance deployment and status timers;
3. select targets with one stable-ID reduction;
4. advance movement;
5. resolve attacks, projectiles, and area damage with grouped scatter;
6. resolve deaths and data-driven death spawns;
7. regenerate elixir and advance regulation/overtime/tiebreak outcome state.

There are no Python entity calls, per-card owner objects, whole-engine
speculative clones, exact diagnostic event ledger, Python scalar-kind shadows,
or CPython RNG parity in the production tick. Unknown mechanics fail closed at
catalog compilation, not halfway through a tick.

## Policy contract

The backend preserves:

- typed Hero/Evolution identity without root collapsing;
- `canonical_lane_globals=true` for current-client causal models;
- actor-private own hand, Next, fractional elixir, and visible evolution state;
- label-independent public-mask contract v2 for causal training;
- optional privileged critic state without leaking it into actor input;
- action success, previous action/reward/reset, rewards, done, and winner;
- deterministic within-profile repeated traces and checkpointed profile ID.

Simulator-exact legal masks and public-mask-v2 confidence masks remain distinct
domains and must never be relabeled as each other.

## Initial mechanic suite

The first acceptance deck covers ten representative cards:

- Knight: melee acquisition, retarget, direct damage, death;
- Archers: multi-summon and ranged projectile;
- Giant: buildings-only targeting;
- Cannon: building footprint, lifetime, ground targeting;
- Fireball: travelling area damage and tower scaling;
- Arrows: rapid area damage;
- Baby Dragon: airborne movement and air/ground splash;
- Prince: serialized charge modifier;
- Ice Spirit: jump, freeze timer, and self-consumption;
- Skeleton Army: high-count stable allocation and capacity behavior.

Python differential traces remain useful diagnostics. Acceptance focuses on
gameplay semantics: serialized hit values, deterministic outcomes, milestone
timing within one tick, projected positions within 0.25 tile for simulator
comparisons, stable/no-reused IDs, and privacy-safe finite policy tensors.

## Real-game gates

Current video data can independently gate clock/phase behavior, typed actions,
contract-v2 masks, orientation, and coarse placement. It cannot yet gate
sub-100-ms combat timing, HP/damage, projectile trajectories, statuses, or
outcomes. Those fields use serialized game data and bounded simulator
differentials until better labels exist; Python is diagnostic rather than
gospel.

## Promotion gates

1. CPU schema and ten-card lifecycle tests.
2. CPU deterministic seeded terminal episodes with zero fallback.
3. CUDA state/digest equivalence for the same profile.
4. Fewer than 1,000 CUDA kernel launches per tick initially; target fewer than
   200, with zero host synchronizations inside the tick.
5. Absolute throughput evidence, then production-shaped recurrent collection.
6. Integration into a clean branch based on the stabilized newer training
   stack; do not overwrite its model/data/training contracts.
