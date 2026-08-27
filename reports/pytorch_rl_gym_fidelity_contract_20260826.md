# PyTorch RL-gym fidelity contract — refreshed 2026-08-27

## Objective

The production objective is a fast, stable, high-fidelity reinforcement-learning
Gym—not a bit-for-bit reimplementation of the Python simulator. Python remains
an exact debug oracle, but incidental Python scalar types, binary-float residue,
CPython RNG state, and diagnostic event instrumentation are not native-game
requirements.

## Authority order

1. Independently reviewed real-game observations, when the measured channel is
   sufficiently calibrated.
2. Serialized balance/mechanic data and production-plausible fixed-step
   invariants.
3. Policy-visible transition consistency: actor/critic tensors, public-mask-v2,
   action success, reward, done/winner, reset/history, and recurrent inputs.
4. Python differential behavior as a regression and diagnosis aid.

No lower-ranked source may be presented as real-game proof when a higher-ranked
source is missing or contradictory.

## Production-plausibility gate

Production Gym logic should look like something a shipped mobile game could
reasonably contain:

- generalized components and serialized tables rather than card-name patches;
- integer/fixed-step clocks and bounded state rather than Python float residue;
- stable creation/update order, fixed phase order, and deterministic state
  transitions;
- no gameplay dependency on Python numeric types or verifier-only events;
- complexity must explain multiple mechanics or policy-visible behavior.

Rules which fail this check belong in `strict_oracle` debug compatibility, not
the production Gym path.

## Current real-game evidence boundary

The refreshed read-only calibration gate covers every manifest in two complete,
disjoint local clocked corpora: 42 matches, 111,404 neutral 10-Hz rows, 95,500
accepted clock rows, 1,525 valid visual play events, 1,380 aligned actor
targets, and 111,426 actor projection/mask rows.

Artifact integrity, 100-ms sampling, public-clock local rate, typed-key
compatibility, slot/action encoding, canonical orientation, and coarse placement
encoding pass their bounded checks. The overall gate is nevertheless **fail**:
37/37 observed regulation-to-overtime transitions are correct, but the 95%
Wilson lower bound is 0.905942 rather than the configured 0.95. Exact
tensor-provider public-mask equality is unavailable because the corpus does not
pin complete projected tower state and engine semantics authority.

This evidence does not validate continuous trajectories, hitboxes/collision,
exact HP or damage, exhaustive entity counts, projectile targets, statuses,
hidden RNG, Hero/Evolution variant accuracy, full action recall, or outcomes.
Those channels remain serialized-data/invariant driven and must not be
described as video-proven.

Primary repository artifact and read-only corpus roots:

- `reports/simple_gym_real_corpus_calibration_gate_20260826.md`;
- `/Users/sam/Desktop/code/clasher/datasets/derived/tv_royale_youtube_persistent_batch_causal_clocked_20260825`; and
- `/Users/sam/Desktop/code/clasher/datasets/derived/tv_royale_youtube_1000_causal_clocked_20260826`.

## Validation profiles

### `strict_oracle`

Retains exact Python snapshots, scalar kinds, CPython RNG, and call-site event
ledger. It is a debug/regression profile and may fail on harmless Python-only
differences.

### Approximate oracle-state diagnostic

Allows numeric scalar-kind equivalence, at most 0.25 tile position error, and at
most one 50-ms component tick for internal timers. Cards, identities, HP,
elixir, status/readiness flags, actions, and outcomes remain exact. RNG and the
diagnostic event ledger are excluded. This is useful for locating harmless
trajectory drift, but is not by itself Gym acceptance.

### Production Gym acceptance

The production gate must compare post-projection transitions for both seats:

- actor tensors and optional critic tensors;
- label-independent public-mask contract v2;
- applied-action success and public play-history pulses;
- reward, done, winner, reset, previous action/reward;
- frozen-policy actions and recurrent hidden/cell state;
- zero Python fallback and 100% requested native ticks.

Discrete fields and policy-visible HP/elixir/status/readiness remain exact.
Position differences may be accepted only after projection and only within
0.25 tile. Repeated runs under the same Gym semantics profile must have the same
digest. Checkpoint metadata must record the semantics profile and reject
incompatible resumes.

These are normative acceptance requirements. They have not yet been proven
collectively for the current production source head. In particular, historical
terminal validators do not include a full frozen-policy recurrent transition
comparison, and current checkpoint metadata does not fingerprint every runtime
catalog/mechanic semantic.

## Implemented simplification boundary

The earlier resident-to-Gym workplan is now embodied by a parallel
`SimpleGymRuntime`, rather than by weakening `TensorResidentEngine`:

1. card-name and Python-object setup compiles into fixed numeric catalogs;
2. production state uses dense entity planes plus bounded fixed-shape mechanic
   pools, without the resident diagnostic event ledger or scalar-kind shadows;
3. the production clock is integer 50-ms ticks with stable phase/order rules;
4. chain/line/fan/area/travel/triggered payloads hand off through direct numeric
   commands with one declared mutation owner; and
5. exact Python snapshots, CPython RNG behavior, and detailed diagnostic state
   stay in the resident verifier profile.

Stable IDs/order, 50-ms phase ordering, integer geometry, actor-private
boundaries, typed Hero/Evolution identity, public action history, reward, and
win semantics are not simplification targets.

## Current production frontier

At clean commit `1a641bb81ea4d866d8923bd1c841803b24280091`, the authoritative
Simple Gym artifact check admits all **66/66** enabled public roots and all
**33/33** source decks under canonical lane globals and public-mask contract
v2. The production executor is `SimpleGymRuntime`, not the Resident enabled-
action smoke. Its fixed-shape generalized catalogs/runtime now include typed
spawns and payloads, navigation, visibility, Champion ability state, special
travel, triggered impact/status/impulse, and atomic heterogeneous summons.

`TensorResidentEngine` remains the exact-debug verifier; its strict matrices
are diagnostic evidence rather than production acceptance. Simple admission is
also not live-game fidelity or mechanic-visitation proof. The detailed current
classification lives in `simple_gym_enabled_card_coverage_audit_20260826.md`.

Historical seeded CPU/CUDA terminal and accelerator artifacts show that the
architecture can run deterministic zero-fallback matches and can reach 10 CUDA
launches, zero explicit sync, and 597.283 row-ticks/s at batch 128. Those
artifacts predate the current navigation/visibility/ability/travel/triggered/
heterogeneous mechanics delta and do not certify this head. They also exercised
the now-known inert Crown Tower combat path, so terminal completion is not
high-fidelity tower-retaliation evidence.

Still required before a training promotion:

- working Princess Tower retaliation, correct King activation, and direct
  runtime regressions for both;
- current-head seeded CPU and CUDA terminal/digest gates with zero fallback;
- current-head accelerator launch, synchronization, absolute-throughput, and
  production-shaped recurrent-policy collection evidence;
- complete engine-semantics checkpoint metadata and compatible resume tests;
- refreshed safe assembly into the stabilized newer main training stack;
- a production policy path for Archer Queen's currently public-v2-masked
  ability, or an explicit bounded exclusion; and
- resolution or explicit bounded acceptance of omitted first-hit/ordinary
  retarget clocks, deployment targetability, navigation/body physics, and the
  failing/unavailable real-game calibration channels.
