# Unified practical Gym architecture (refreshed 2026-08-27)

## Decision

Keep `TensorResidentEngine` as the exact-debug mechanic verifier. Do not use
its retained-owner topology as the production RL executor.

The production backend is `SimpleGymRuntime`: a unified, fixed-shape tensor
Gym at 50 ms resolution. It is allowed to differ from the scalar Python
simulator in unobserved event ordering, scalar kinds, CPython RNG state,
diagnostic ledgers, and presentation-only motion. Policy-visible choices,
identity, privacy, action success, projected state, reward/history, and match
outcomes remain hard contracts.

This split is still justified by the bounded H200 resident profile in
`resident_h200_smoke_20260826.md`: one capacity-16 tick launched 275,608 CUDA
kernels and synchronized 19,231 times. That eager retained-object topology is
appropriate for exact debugging, not production collection.

## Production topology

The runtime uses one dense stable-ID entity table for towers, troops, and
buildings, plus bounded fixed-shape companion pools and retained state for
mechanics whose lifetimes differ from entities:

- ordinary, death, travel, and triggered effects;
- rolling spells, scheduled casts, payload containers, and periodic spawns;
- positive areas/buffs, statuses, shields, charge, and damage ramps;
- bridge-route, policy-visibility, Champion-ability, and special-travel state;
- triggered-event queues and atomic heterogeneous-spawn descriptors; and
- action/cycle state, projection inputs, reward history, and outcome state.

This is a unified execution owner, not a claim that every transient is forced
into one physical table. Setup may inspect Python game data and names. Runtime
dispatch is numeric: serialized card-aligned tables, stable IDs, fixed phase
order, and bounded capacity. Unknown or malformed declared profiles fail
closed during standard setup.

The entity table retains only policy/gameplay fields such as active/kind/owner,
typed card ID, integer logic-unit position, HP/shield, attack/target/timing,
deployment/lifetime, and stable identity. Internal stable IDs define ordering
and slot-reuse ownership; they never replace typed public vocabulary tokens.

All production time is integer 50 ms ticks. Serialized millisecond values are
compiled once, with explicit rounding rules, into immutable numeric catalogs.

## Tick ownership

One `SimpleGymRuntime.step_tick` owns the complete transition. Its broad phases
are:

1. evaluate simulator legality, ability requests, ordinary deployments,
   rolling/scheduled casts, and atomic heterogeneous spawns;
2. spend elixir, rotate accepted cards, and initialize every entity-bound
   mechanic plane for accepted slots;
3. advance ability, visibility, special-travel, deployment, status, positive
   area, and cooldown state;
4. select nearest legal targets with stable-ID tie breaking, route ordinary
   ground movers through the standard arena's two bridge openings, and advance
   direct/special movement;
5. resolve direct, projectile, line, fan, chain, rolling, area, travel, and
   triggered damage/status/impulse commands with explicit ownership so payloads
   are not double-applied;
6. resolve deaths, typed death children, delayed payloads, periodic/scheduled
   children, and capacity telemetry; and
7. regenerate elixir, advance regulation/overtime/tiebreak, compute reward and
   outcome, publish structured observations/masks/history, and clear or reset
   terminal rows when requested.

The hot path has no Python entity calls, per-card runtime objects, card-name
branches, whole-engine speculative clones, CPython RNG dependency, or detailed
diagnostic event ledger.

## Policy contract

The backend preserves:

- typed Hero/Evolution identity without base-family collapse;
- `canonical_lane_globals=true` for current-client causal models;
- actor-private own hand, Next, fractional elixir, and visible evolution state;
- label-independent public-action-mask contract v2 computed from actor tensors;
- optional privileged critic state which is never read by the actor mask;
- action success, public play-history pulses, previous action/reward/reset,
  rewards, done, and winner;
- recurrent hidden/cell ownership in the generic tensor collector; and
- deterministic repeated traces within one frozen semantics profile.

Simulator-exact legality and public-mask-v2 confidence legality remain distinct
domains. That distinction is active today: the simulator mask can expose Archer
Queen's implemented ability, while the current public-v2 provider deliberately
hard-masks the ability action. This is truthful domain separation, but it also
means a production policy cannot yet learn Cloak.

The supported-deck artifact pins the compiler label, canonical-lane setting,
public card support, and mask contract. Collector metadata pins backend/mask/
reward identifiers and digests. It does **not** yet fingerprint the complete
runtime/catalog semantics, and the isolated adapter rejects resume rather than
claiming compatible continuation. Full engine-profile checkpoint/resume
compatibility remains a promotion requirement.

## Current mechanic frontier

The original ten-card bootstrap suite remains useful historical coverage:
Knight, Archers, Giant, Cannon, Fireball, Arrows, Baby Dragon, Prince, Ice
Spirit, and Skeleton Army.

The production frontier is now broader. At clean commit
`1a641bb81ea4d866d8923bd1c841803b24280091`, the authoritative artifact check
admits **66/66** enabled public roots and **33/33** source decks. Generalized
numeric owners cover, among other families:

- typed homogeneous, death, delayed, periodic, scheduled, payload-container,
  and atomic heterogeneous spawns;
- direct/projectile/area, multi-target, chain, piercing line, fan, periodic,
  rolling, and damage-ramp attacks;
- shields, charge, slow/stun, Rage, death bursts, recoil, radial/forward push,
  and attraction;
- standard two-bridge routing, Royal Ghost/Tesla visibility, Archer Queen
  ability state, and Bandit/Mega Knight/Miner special travel; and
- deterministic regulation, overtime, tiebreak, reward, reset, and projection.

Admission is not exact mechanics or visitation proof. The current detailed
classification and remaining card/global approximations are recorded in
`simple_gym_enabled_card_coverage_audit_20260826.md`.

## Real-game evidence boundary

The refreshed read-only calibration gate covers 42 disjoint local matches,
111,404 neutral 10-Hz rows, 95,500 accepted clock rows, 1,525 valid visual play
events, 1,380 aligned actor targets, and 111,426 actor projection/mask rows.
Artifact integrity, sampling, clock rate, typed-key compatibility, action
encoding, canonical orientation, and coarse placement encoding pass their
bounded checks.

The overall gate is **fail**. All 37 observed regulation-to-overtime
transitions were correct, but the 95% Wilson lower bound is 0.905942 rather
than the configured 0.95. Exact tensor-provider mask equality is unavailable
because the corpus does not pin complete projection/tower state and semantics
authority. Independently labelled trajectories, hitboxes, HP/damage, statuses,
Hero/Evolution variant accuracy, and outcomes are also unavailable. See
`simple_gym_real_corpus_calibration_gate_20260826.md`.

## Promotion status at commit `1a641bb8`

| Gate | Status | Authoritative boundary |
|---|---|---|
| Current admission artifact | pass | 66/66 roots, 33/33 decks, byte-identical artifact, profile SHA `9e8dbfe1...` |
| Current focused CPU mechanics | pass | 99 passed, 50 CUDA skips across admission/navigation/visibility/ability/travel/triggered/heterogeneous seams |
| Crown Tower combat | fail | tower rows use card ID zero while ordinary attack-effect allocation rejects nonpositive card IDs; Princess/King attacks therefore acquire but do not damage, and King activation is not modeled |
| Seeded CPU terminal episodes | historical only | committed deterministic regulation/overtime/tiebreak and first-legal terminals predate current mechanics and exercised the now-known inert tower model |
| Seeded CUDA terminal episodes | historical only | the A6000 CUDA-Graph artifact proves 6,000-tick no-op and 909-tick first-legal terminals for source `5a8cc34e`, 22 commits before this head; it does not validate tower retaliation |
| CUDA launch and throughput | historical only | 10 launches, zero explicit sync, and 597.283 row-ticks/s at batch 128 were measured for source `5890e092`, before the current mechanics delta |
| Production-shaped recurrent CUDA collection | missing | no current-head frozen-policy/recurrent full-collection gate exists |
| Complete semantics fingerprint and compatible resume | missing | current metadata is partial; isolated route is fresh-only and rejects resume |
| Safe newer-main integration | stale candidate | the isolated integration used Simple source `37e4fff3`; the current mechanics tree has not been assembled and gated into stabilized main |
| Independent real-game calibration | fail/unavailable | the current corpus gate fails its overtime confidence bound and lacks combat/outcome/mask-equivalence authority |

## Promotion decision

**Not promoted.** Current admission and focused CPU mechanic seams are strong,
and the historical CUDA artifacts prove the architecture can satisfy the
launch and absolute-throughput shape. They do not certify this source head.

Promotion requires, at minimum:

1. restore and directly test Princess Tower retaliation plus King activation;
2. implement or explicitly calibrate first-hit/retarget and deployment-target
   timing;
3. current-head deterministic CPU and CUDA terminal replays with zero fallback;
4. current-head CUDA state/digest equality, launch count, zero-sync, and
   absolute-throughput evidence;
5. production-shaped recurrent-policy collection, including public-v2 and
   simulator-legality domain checks;
6. a complete engine semantics fingerprint with compatible resume rejection/
   acceptance tests;
7. safe assembly and verification on the stabilized newer training stack; and
8. resolution or explicit bounded acceptance of the public ability,
   navigation/body-physics, and real-data calibration blockers.
