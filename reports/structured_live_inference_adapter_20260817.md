# Structured live inference adapter

Date: 2026-08-17

## Outcome

`src/clasher/rl/structured_live_adapter.py` is the first concrete
current-frame-only execution boundary for the existing structured policy.  It
accepts only validated `PublicVisionFrame` instances and owns:

- canonical actor perspective;
- confidence-aware actor tensor construction;
- mandatory `PublicActionMaskBuilder` mask construction;
- previous selected action;
- zero previous reward;
- episode reset and decision cadence;
- recurrent hidden/cell tensors;
- exact serialization, digest, and restoration of adapter state; and
- deterministic model invocation and legality verification.

It has no argument for an exact mask, expert action, critic tensor, opponent
hand/elixir, simulator history, or reward.  Those names are rejected by the
upstream public-frame parser.  Directly constructed `PublicVisionFrame`
dataclasses are reserialized and revalidated at the adapter boundary, so a
caller cannot bypass confidence/value or player-ID invariants by skipping the
JSON parser.

## Import isolation

`clasher.rl.__init__` now resolves its historical package exports lazily, and
the type-only simulator observation imports in `public_action_mask.py` are
guarded by `TYPE_CHECKING`.  A fresh-process test proves importing
`clasher.rl.structured_live_adapter` loads neither `clasher.battle` nor
`clasher.rl.structured_obs`.  Accessing an explicitly simulator-facing lazy
package export still loads its normal implementation.

The adapter receives an already constructed model and public mask builder.  A
future fully standalone deployment loader should likewise load the checkpoint
and frozen public card catalog without importing simulator builders.  The
existing evaluation loader is not claimed to meet that packaging gate.

## Current-frame mapping

Supported now:

- public entity identity, typed kind, owner, position, identity confidence;
- optional visible HP with a separate HP-bar confidence;
- public arena positions canonicalized by actor (`x -> 18-x`, `y -> 32-y` for
  actor 1);
- four own hand cards, visible Next, and per-slot confidence;
- own visible elixir and confidence;
- elapsed public clock measurement and confidence;
- visible Crown Tower HP measurements;
- static range, sight, radius, and damage values copied from immutable tensors
  already packaged in the model; and
- one current opponent play event for future deterministic-state checkpoints.

The accepted checkpoint does not consume current play events, so this is
reported as `ignored_by_checkpoint` rather than silently presented as working
cycle/elixir inference.

Explicitly zero or ignored:

- motion/facing: current-frame input cannot provide it and the accepted train
  semantics do not match video displacement;
- entity speed: packaged card speed uses a different normalization from the
  legacy entity channel;
- visible statuses: counted in diagnostics, but no accepted live status
  channels exist;
- exact phase flags, crowns, Champion cooldown/duration, next-refill clock, and
  enemy-King-alive flag;
- exact remaining status/attack/deployment timers; and
- all opponent-history/seen-card arrays, which are fixed width zero.

The public clock is carried in the tensor schema, but the accepted structured
checkpoint uses its own decision clock and ignores this measurement.  A future
deterministic public-state checkpoint can consume it without changing the
adapter boundary.

Unknown entities are omitted with track IDs reported.  Unknown or missing hand
slots remain zero-confidence, causing the public mask to disable those slots.
The adapter never invents a card, kind, HP, timer, status, or legal action.

## Cadence and state

Default decision cadence is 400 ms, matching the accepted policy's training
interval.  Duplicate frame IDs/timestamps and early frames do not advance the
model.  A gap above two intervals raises `LiveCadenceError`, marks the adapter
as reset-required, and does not synthesize missing recurrent steps.

Serialized state is canonical JSON containing exact tensor dtype/shape/bytes,
episode, perspective, prior action, cadence metadata, and seen frame IDs.  Its
SHA-256 is verified before restoration.  Perspective, schema, tensor shape, and
digest changes fail closed.

## Public mask boundary

Every accepted step constructs its own mask from current public actor tensors.
The mask builder always preserves no-op and disables the unsupported Champion
ability.  The adapter checks the model-selected action against that mask before
publishing it.

The existing mask builder still consumes a frozen public card catalog for
cost/type/radius/spell legality.  That catalog must be packaged with the
deployment artifact; it is not inferred from hidden battle state.  The new
adapter never accepts a precomputed mask, and its label counterfactual test
proves changing an external expert label cannot change the mask.

## Evidence

Focused tests cover:

- fresh-process import isolation and lazy package-export compatibility;
- both actor perspectives and exact canonical positions/team flags;
- nonzero public Next propagation;
- mandatory label-independent public mask;
- rejection of opponent-private and simulator-only fields;
- rejection of malformed directly constructed public-frame objects;
- reset, duplicate, early, out-of-order/gap behavior;
- state serialization/restoration across the next decision;
- explicit unsupported-cue zeros and diagnostics;
- separate HP confidence propagation; and
- bit-exact action and recurrent-state parity with direct `PolicyInputs` on a
  frozen synthetic step using the accepted checkpoint.

No training or sustained gameplay was run.
