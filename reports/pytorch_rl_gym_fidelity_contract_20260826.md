# PyTorch RL-gym fidelity contract — 2026-08-26

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

The 2026-08-25 persistent corpus contains 37 hash-verified native videos
(6.113 GB, 9,935.617 seconds, 99,356 contiguous 10-Hz frames). Twenty-nine have
reviewed deck closure. The new 29-game extraction contains 76,148 neutral rows,
65,285 clock-valid rows, 971,838 detections, 802,536 accepted typed identities,
and 471,866 accepted HP detections. The broader 33-replay audit contains 1,059
offline targets, of which 923 are clocked, 821 are public-mask legal, 711 are
legal-and-clocked action components, 220 have complete HUD, and 24 replays are
fully verified.

This evidence can currently validate accepted typed action-card identity,
label-independent public-mask-v2 legality, own HUD missingness, clock-conditioned
action components, and coarse deployment-tile distributions. It cannot yet
validate continuous trajectories, hitboxes/collision, exact HP values,
exhaustive entity counts, projectile targets, status durations, hidden RNG, full
action recall, or outcomes. Those channels remain simulator/balance driven and
must not be described as video-proven.

Primary external artifacts:

- `/Users/sam/Desktop/code/clasher/reports/persistent_batch_v1/local_closure_and_causal_gate_20260825.md`
- `/Users/sam/Desktop/code/clasher/reports/persistent_batch_v1/deck_closed_causal_corpus_audit_33games.json`
- `/Users/sam/Desktop/code/clasher/reports/persistent_batch_v1/reviewed_deck_decisions_v1.json`
- `/Users/sam/Desktop/code/clasher/datasets/derived/tv_royale_youtube_persistent_batch_causal_clocked_20260825`

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

## Simplification order

1. Replace the chain mechanic's dependency on diagnostic events with a direct
   projectile-impact handoff, then disable the detailed event ledger in Gym
   mode while preserving public card-play history.
2. Disable Python scalar-kind shadow planes in Gym mode; retain numeric HP and
   shield values.
3. Wire the existing native RNG profile for training, with exact Python RNG
   retained only for strict debug.
4. Use integer-millisecond deadlines in Gym mode; retain binary-float projection
   only in strict debug.
5. Consolidate duplicate owner target/shield snapshots and speculative copies
   only after the policy-transition gate is green.

Stable IDs/order, 50-ms phase ordering, integer geometry, actor-private
boundaries, typed Hero/Evolution identity, public action history, reward, and
win semantics are not simplification targets.
