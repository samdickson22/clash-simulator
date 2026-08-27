# PyTorch RL Gym fidelity contract — final refresh 2026-08-27

## Decision

The production backend is accepted for **fresh practical RL training** at
Simple source `504444ea400ff8bf595c0386ff000afe2c1f3490`.
`TensorResidentEngine` remains the exact-debug verifier; it was not weakened or
redefined as the production executor.

Acceptance means a deterministic, serialized, policy-faithful 50 ms Gym for the
current 66-card/33-deck training pool. It does not mean bit-for-bit Python
parity, complete live-client reconstruction, or independently video-calibrated
combat.

## Authority order

1. Independently reviewed real-game observations for channels the corpus can
   actually measure.
2. Serialized balance/mechanic data and production-plausible fixed-step rules.
3. Policy-visible transition consistency: actor tensors, public-mask v2,
   action success, reward/outcome, reset/history, and recurrent inputs.
4. Python/Resident differential behavior as a debug and regression aid.

No lower-ranked source is presented as proof for a missing higher-ranked
channel.

## Production-plausibility boundary

The accepted runtime follows rules which a shipped game could reasonably own:

- generalized numeric components and serialized tables, not card-name runtime
  patches;
- dense bounded state, stable IDs, integer 50 ms clocks, and fixed phase order;
- one mutation owner for each effect, spawn, travel, contact, and outcome;
- deterministic owner-mirrored tie breaking and fail-closed malformed profiles;
- no Python entity calls, CPython RNG dependency, host compaction, or diagnostic
  event ledger in the hot path.

Exact Python scalar kinds, binary residue, call-site event tuples, and CPython
RNG snapshots remain verifier concerns rather than production Gym semantics.

## Accepted production contract

At source `504444ea` the standard compiler admits all **66/66** public roots and
all **33/33** source decks. The committed artifact is byte-exact, requires
`canonical_lane_globals=true`, and pins public-action-mask contract v2.

The production path preserves:

- actor-private own hand, Next, fractional elixir, and public entity state;
- a separate optional privileged critic which the actor and mask never read;
- typed card/body lookup with no Hero/Evolution base-family collapse;
- public-mask semantics
  `public-action-mask-v2/tensor-actor-projection-v2`;
- Archer Queen ability legality derived only from actor-visible typed state;
- action success, public play history, previous action/reward, reset, reward,
  done, winner, and recurrent hidden/cell ownership;
- objective reward contract `objective-v1-gamma-v1`; and
- zero Python fallback with explicit native/committed row evidence.

Typed Hero/Evolution preservation is an identity contract. The 494-token
vocabulary keeps variants distinct and fails closed on ambiguous or unknown
keys. The admitted 66-card runtime pool contains no `_hero` or `_EV1` root, so
variant gameplay is not claimed or silently approximated.

## Mechanic fidelity frontier

Generalized production owners cover ordinary and Crown Tower combat, serialized
first-hit/retarget locks, shields, charge, damage ramps, direct/projectile/area/
line/fan/chain attacks, periodic and rolling effects, statuses, positive buffs,
death/delayed/periodic/scheduled/heterogeneous spawns, visibility, Champion
ability state, special travel, river jumps, displacement, body collision,
building avoidance, mass, hover, and match outcomes.

The final contact repair also proves two policy-visible invariants that were
previously missing:

- pending deployed bodies are targetable, effectable, and collidable while
  remaining unable to act; and
- Skeleton Barrel uses a generalized serialized first-hit windup plus
  stun-paused 500 ms contact countdown before self-pop and payload resolution.

The predecessor `f67ed3a8` is explicitly rejected: its exact-overlap fallback
was not owner-mirror equivariant and its per-tick direction-table allocation
invalidated CUDA Graph capture. Both faults are fixed and directly tested at
`504444ea`.

## Final evidence

### CPU and artifact gates

- supported-deck check: 66/66 roots, 33/33 decks, zero rejected;
- support-profile SHA-256:
  `9e8dbfe1edf10835bd2138f237dcc917b65dc1f44f39bc26ff221da4d6aaefab`;
- exact isolated-main suite: **406 passed, 248 CUDA skips**;
- newer-main strategy/action-geometry checks: **85 passed**; and
- actual one-update CPU PPO smoke: 494 tokens, 119,095 parameters, two
  transitions, checkpoint reload and metadata assertions passed.

### Exact-source CUDA gates

The authoritative aggregator is
`reports/simple_gym_cuda_a6000_contact_final_20260827.json`, SHA-256
`0dc2f070feadf11a15eb55ae43deb410be89759afdf2db7ad0261be820f42b0b`.

- expanded source suite: **222/222 passed** on an RTX A6000;
- no-op: tick 6000, overtime/tiebreak, digest
  `d14d2c7b5d41fed9784b521c9ee31c27b7d9a10903954dbf792abf73cd0c4226`;
- first-legal: tick 3600 regulation crown, digest
  `0430c8f45ab028d590bbdb293ff25dd3f936ec172aa6f9bbd7af786e83981fc1`;
- two exact CUDA-Graph replays per policy, all native and committed, zero
  fallback;
- batch-128 trials: 410.708, 410.053, and 409.637 row-ticks/s;
- median: **410.053 row-ticks/s** and **820.106 actor transitions/s**;
- **10 CUDA launches**, **zero explicit host synchronizations**, identical
  trial digest, and the declared 400 row-ticks/s floor passed.

### Newer-main CUDA gates

The isolated newer-main integration commit
`b1ff9f1e2e1380071cca62afab68afdbb5dfdef9` contains the exact
`504444ea` Simple tree with zero blob mismatches. It passed **191/191** CUDA
route/mechanic tests. A real 494-token recurrent `ClasherPolicy` produced
public-mask-legal actions, hidden/cell outputs of shape `[1,2,32]`, exact
metadata, two native committed/admitted ticks, and zero fallback.

The live dirty main checkout, its running training process, model/data tree,
and checkpoints were not modified. The A6000 pod was terminated and the
provider reported zero active paid pods.

## Real-game calibration boundary

The read-only corpus gate covers 42 disjoint matches, 111,404 neutral 10 Hz
rows, 95,500 accepted clock rows, 1,525 visual play events, 1,380 aligned actor
targets, and 111,426 actor projection/mask rows. Artifact integrity, sampling,
clock rate, typed-key compatibility, slot/action encoding, canonical
orientation, and coarse placement encoding pass.

This remains bounded evidence. All 37 observed regulation-to-overtime
transitions were correct, but the predeclared 95% Wilson lower bound is
0.905942 rather than 0.95. Combat trajectories, exact HP/damage/status,
outcomes, hidden RNG, and tensor-provider mask equality are unavailable. Those
channels use serialized data, invariants, direct tests, and deterministic Gym
evidence; they are not described as video-proven.

## Deliberate acceptance limits

The following are accepted practical-Gym approximations rather than hidden
passes:

- Arrows waves are collapsed into one bounded total-damage event;
- Graveyard uses deterministic bounded spatial scheduling rather than live RNG;
- Ice/Electro Spirit hops use homing-effect travel rather than presentation
  arcs;
- body contact and obstacle steering are deterministic dense approximations,
  not the client's entire path graph/avoidance implementation; and
- full free-running visitation of every mechanic in all 66 roots is not
  claimed; direct generalized seam tests plus admitted-deck episodes are the
  authority.

The training route is deliberately **fresh-only**. Resume is rejected before
model mutation, so an incompatible old simulator/reward/domain checkpoint
cannot be silently continued. Compatible-resume support and a complete runtime
catalog fingerprint are future capabilities, not requirements of this fresh
training acceptance.

## Final status

**Accepted for fresh practical RL training.** The exact verifier remains
available, the dense production engine meets its fidelity and accelerator
contracts, and the validated backend is safely assembled on the newer training
stack. Broader live-game parity claims remain out of scope.
