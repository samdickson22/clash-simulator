# PyTorch simulator audit and vertical-slice design

Date: 2026-08-14

Branch: `codex/pytorch-simulator-f872`

Base: `27877055` (`codex/simulator-throughput-f872`)

## Scope and completion rule

The Python simulator remains the behavioral oracle. The PyTorch backend is not
complete until enabled-card battles and complete episodes run tensor-resident,
all exact differential gates pass, and the production 12-worker rollout plus
oracle workload is at least twice as fast. Unsupported state currently falls
back to Python and is counted; fallback is a milestone safety mechanism, not
acceptance evidence.

## Repository and baseline findings

- The generated worktree initially pointed at divergent `origin/main`
  (`99f936f8`), which has no RL stack. The delegated source thread and its
  verified simulator performance work live on `codex/simulator-throughput-f872`.
  This worktree was moved to a new branch rooted at that tip without changing
  either existing branch or worktree.
- The committed throughput tip depends on intentionally uncommitted training
  work in `/Users/sam/.codex/worktrees/f872/clasher`. A clean checkout therefore
  has seven collection failures: missing `strategy_bots.py` and missing newer
  reward-model names. The source worktree was inspected read-only and remains
  untouched. Core simulator and focused RL tests are runnable here.
- The first environment sync attempted Python 3.14 and reproduced pygame's
  missing `SDL.h` failure. This worktree now uses CPython 3.12.13 from `uv`,
  with torch 2.10.0 and available Apple MPS.
- Sustained current throughput measurement is deferred: the resident-Rust test
  process was using one CPU at 99%, and a separate training tmux workload was
  present during the audit. Existing matched reports remain historical evidence
  only and are not claimed as current PyTorch performance.

## Authoritative tick order

`BattleState._step_logic_tick` advances one 50 ms native frame in this order:

1. Increment time/tick and publish double/triple-elixir and overtime flags.
2. Regenerate elixir and advance delayed hand refill for both players.
3. Snapshot start-of-frame entities and resolve due server-delayed commands.
4. Snapshot lethal projectile reservations.
5. Run combat components in entity-ID order against start positions; direct
   mutations are visible to later components.
6. Run movement components in entity-ID order, including collision pressure,
   forced movement, pathing/river logic, and native position publication.
7. Run building lifetime/hitpoint components.
8. Run buff/status clocks after their final effective combat/movement frame.
9. Run the dynamically growing object phase. Newly appended projectiles,
   areas, explosives, and child objects may tick in the same frame; command-
   created objects do not.
10. Clean up dead entities, publish death spawns and tower/champion ownership.
11. Refresh derived fast caches and conditionally resolve win state.

This ordering, including object birth visibility and entity-ID ordering, is a
hard tensor-kernel constraint.

## Mutable state model

### Battle/player state

- Float-visible clocks: `time`, `dt`, step remainder, elixir, tower HP views.
- Integer/order state: tick, next entity ID, command sequence, refill cooldown,
  four hand slots, deck and cycle queue order.
- Match flags: double/triple elixir, overtime, sudden death, game over, winner,
  and sudden-death crown snapshot.
- Per-battle `random.Random` state; simulator randomness occurs in serialized
  spell spread, spawn placement, knockback/status chances, and death effects.

### Entity state

- Stable ID and creation order, class/kind, owner, serialized card definition,
  alive/targetability/air/building/crown traits.
- Native 1/1000-tile integer coordinates, facing, lane, collision radius/mass,
  target-distance discount, movement accumulators, route/river/forced-movement
  state.
- HP/damage/range/sight and combat clocks, windup/preload state, target ID,
  projectile pending-damage reservations.
- Deployment, activation, lifetime, status/debuff/buff clocks, periodic damage,
  stealth/shield/ramp/spawner/champion mechanic state.
- Object-specific projectile, area, rolling, timed-explosive, Graveyard, spawn,
  chain, and death payload state.

### Derived state

Python target arrays, entity buckets, placement masks, alive-building lists,
and Crown caches are accelerators, not behavioral authority. Tensor execution
should derive equivalent masks/index planes from authoritative dense tensors.

## Enabled mechanic inventory

The current `decks.json` manifest contains 33 decks and 66 unique resolvable
cards: 47 troops/champions, 5 buildings, and 14 spells. The manifest spells
exercise direct damage, point/group projectiles, rolling projectiles, delayed
spawn projectiles, persistent areas, Tornado pull, Graveyard, and Royal
Delivery. The global registry contains 31 spell aliases/variants.

Shared serialized mechanic classes currently include shield, damage ramp,
knockback, freeze/stun/status, Crown scaling, periodic spawner, death damage,
death area, death spawn, multiple-target attack, on-hit buff, spawn area,
spawn pushback, and champion active ability/Skeleton King soul state. Runtime
object classes include troop, building, projectile, chain lightning, area and
buff/death-area containers, spawn/rolling projectiles, timed explosive, and
Graveyard.

The implementation plan is organized by these serialized opcodes and runtime
object kinds, never by card names.

## Training and oracle ingress

- `SelfPlayBattleEnv` owns action ordering, applies both actions, advances a
  decision window (normally eight ticks), then builds rewards/observations.
- `DiscreteTileActionSpace` owns exact legality/masks, deployment geometry,
  no-op, and champion ability actions.
- `StructuredObservationBuilder` and `CvObservationBuilder` consume the public
  Python battle view; they must be differentially gated before direct tensor
  projections replace that view.
- Recurrent training constructs environments locally or through persistent
  `ActorWorkerConfig` processes. `--simulation-backend` now reaches both paths.
- Oracle planners clone `BattleState` and call tick windows directly. They are
  not yet routed through the PyTorch executor; resident fork/clone semantics
  and RNG preservation are required before oracle acceptance.

## Performance bottlenecks

The current engine spends time in repeated per-entity Python dispatch and
allocation across targeting, collision, movement/path queries, object growth,
state cloning for oracle leaves, action-mask geometry, structured observation
packing, and multi-process handoff. Existing matched reports show that even
narrow exact reductions in Crown fallback scans and river walkability queries
produce measurable rollout/oracle gains, confirming that target/movement
inner loops are hot. The tensor design therefore prioritizes:

1. batch-wide structure-of-arrays state and masks;
2. data-driven mechanic opcode tables;
3. stable slot allocation plus ID/order tensors;
4. vectorized target/collision geometry with explicit stable tie ordering;
5. tensor-resident forks for oracle search;
6. direct observation/action-mask projections; and
7. batching across environments within each worker before considering MPS.

CPU float64/int kernels are the parity baseline. MPS is appropriate only for
large supported batches and float32-safe projections; native integer/fixed-
point semantics and unsupported float64 operations rule out blanket MPS use.

## Implemented vertical slice

`src/clasher/torch_sim` now provides:

- a batched dense `TensorBattleState` with global/player/card-cycle/entity/tower
  tensors and native integer coordinates;
- exact snapshots and deterministic first-divergence paths that reject scalar-
  kind changes as well as value changes;
- `python`, `pytorch-shadow`, and `pytorch` execution modes;
- a complete tensorized inert-Crown-tower tick: match clocks, elixir phases,
  hand refill, active tower clocks, overtime/sudden death/tiebreak, and outcome;
- persistent tensor state across supported tick windows; and
- explicit counted Python fallback for unsupported battle states.

Current direct evidence:

- 13 new vertical-slice tests pass.
- Exact matches cover 1/100 ticks, refill mutation, and boundaries around
  120/180/240/300 seconds, including exact scalar kinds.
- 83 pre-existing focused tests passed before type cleanup; the final owned
  gate is 47 tests plus mypy success for six touched modules.
- With the seven uncollectable inherited modules explicitly ignored, the broad
  clean-tip run produced 1,255 passes and 135 failures. Those failures are
  dominated by parity tests passing the uncommitted `reward_profile` argument
  to the committed determinism helper; three imitation-objective failures are
  also part of the inherited source/test split. They are recorded as baseline
  failures, not PyTorch acceptance evidence.

## Next parity ladder

1. Tensorize command queues, card allocation/cycling, entity spawn slots, and
   deployment legality so action ingress remains tensor-resident.
2. Port status/lifetime and stationary direct combat as shared mechanic opcodes.
3. Port targeting/projectiles/areas/death cleanup and same-frame object growth.
4. Port ground/air movement, collision, native pathing, bridge/river jumps, and
   forced movement.
5. Add exact tensor forks and direct projections for oracle/action masks/
   observations/rewards.
6. Expand differential gates from phase fixtures to exhaustive manifest pairs,
   randomized crowded states, long seeds, and complete episodes.
7. Remove fallback only after every reachable enabled state is covered, then
   run guarded 12-worker plus oracle matched benchmarks and require at least 2x.
