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

- 24 owned PyTorch tests pass.
- Exact matches cover 1/100 ticks, refill mutation, and boundaries around
  120/180/240/300 seconds, including exact scalar kinds.
- A retained 12-battle tensor batch advances independently through timer and
  terminal boundaries. Mixed batches fail closed per member rather than
  forcing supported members through Python.
- Mechanic-free deployment advances entirely in tensors until the zero-crossing
  frame, then continues through Python at the first frame where combat can act;
  both the pure and split windows match exact snapshots in shadow and on modes.
- `TensorCardCatalog` compiles all 66 enabled definitions and the complete
  current factory mechanic/effect inventory into dense opcodes and scalar
  parameter planes without card-name dispatch.
- Ruff's F/I gate and mypy pass on all PyTorch modules plus both training
  integration modules.
- The initial milestone also passed 47 focused integration/regression tests;
  the current evidence above is additive to that gate.
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

## Parallel subsystem milestone

The next standalone tensor layers are implemented behind explicit support
boundaries and are awaiting integration into the retained battle state and
complete tick executor:

- stable monotonic entity identity, reusable physical slots, deterministic
  ID-order selection, cleanup, death-spawn allocation, and compaction plans;
- all-enabled-card action decoding, exact hand/cycle/elixir transitions,
  deployment legality, placement occupancy, and stable command emission;
- fixed-point stationary targeting, stable tie/Crown fallback selection,
  attack clocks, direct/area damage, projectile launch events, and lethal
  projectile reservations;
- fixed-point projectile travel, area clocks, timed payloads, same-frame
  dynamically growing object worklists, and ordered object event streams;
- exact integer natural movement, collision pressure, standard-arena
  walkability, route-head movement, and river-jump transition kernels;
- source-slot stun/slow/haste/freeze/periodic status work and native integer
  building lifetime decay; and
- a sharded differential harness comparing exact battle state, scalar kinds,
  Python/NumPy RNG, action masks, both observations, rewards, step metadata,
  and outcomes while rejecting fallback-only coverage claims.

Current combined owned gate: 104 tests pass; Ruff F/I, mypy across all 14
PyTorch/training source modules, and `git diff --check` pass. The manifest
generator losslessly represents 4,356 ordered one-card matchups and 4,888,521
ordered two-card-per-owner compositions. These numbers are enumeration evidence,
not executed full parity evidence. The standalone kernels likewise do not yet
make ordinary combat tensor-native: `TensorBattleState`/executor wiring,
mechanic callback opcodes, direct observation/reward projections, full episode
coverage, and the production throughput requirement remain incomplete.

## Serialized mechanics and manifest evidence

This lane adds reviewed standalone kernels and truthful capability audits on
top of parent tip `642e48ee`:

The current combined PyTorch gate is 131 passed and one explicitly skipped
probabilistic-status inventory test; focused mypy, Ruff F/I, and diff checks
pass.

- nested serialized status payload compilation/dispatch for
  `SerializedOnHitBuff`, plus global `Stun` and `FreezeDebuff` payload forms;
- serialized `Shield` damage/break events and `ArcherQueenCloak` ownership,
  activation, death/cancel, and lifecycle deadlines;
- recursive enabled-root spawn inventory, exact `PeriodicSpawner` clock/event
  scheduling, and context-carrying `DeathSpawn` child plans; and
- an exhaustive one-tick post-deployment census of all 4,356 ordered enabled
  1v1 pairs: 484 executed entirely in tensor kernels, 3,872 used counted Python
  fallback, and zero oracle mismatches or execution-accounting errors.

The enabled manifest SHA-256 is
`39fd5d5fe36cc7cfa69cf049de3ea2e7e00bc143ec71b14f33ead300fb4b2944`;
the one-tick result matrix SHA-256 is
`004f2b1b48c41b8d72cda2737ec8ac25cccab3db2248af80629f6da1d9051ad7`.
These are deployment-window results, not complete interaction or episode
parity. Fallback rows are never counted as tensor evidence.

The repository has only owners `(0, 1)`, no controller-to-team identity, and a
two-wide tensor player axis. True four-controller team 2v2 is therefore
structurally unsupported by both the Python oracle and tensor backend: zero of
66 enabled-card rows qualify. Two cards deployed by each of the existing two
owners are now labeled `cards_per_owner`, not 2v2.

All 23 enabled serialized mechanic opcodes remain unintegrated in the retained
`TensorBattleState`/executor. Five now have standalone partial or complete
kernel slices—`ArcherQueenCloak`, `DeathSpawn`, `PeriodicSpawner`,
`SerializedOnHitBuff`, and `Shield`—but ordinary battles containing them still
fall back. The 18 enabled mechanic opcodes without a dedicated serialized
kernel are `AttackRecoil`, `BanditDash`, `BattleRamCharge`,
`CrownTowerScaling`, `DamageRamp`, `DeathAreaEffect`, `DeathDamage`,
`ElectroDragonChainLightning`, `ElectroSpiritChain`, `HideWhenIdle`,
`IceSpiritFreeze`, `InvisibilityWhenNotAttacking`, `MegaKnightSlam`,
`MultipleTargetAttack`, `SpawnAreaEffect`, `SpawnPushback`,
`UndergroundDeployment`, and `WallBreakersDemolition`. Enabled effect opcodes
`PeriodicArea` and `ProjectileLaunch` likewise have standalone object kernels
but no retained executor dispatch. Global Skeleton King `SpawnUnits` ability
effects, death-child geometry/materialization, spawn travel/pushback, first-tick
immunity/freeze inheritance, and ordered executor wiring are still explicit
gaps.
