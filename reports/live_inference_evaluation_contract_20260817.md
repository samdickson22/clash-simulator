# Live inference evaluation contract

## Decision

The deployment/evaluation boundary is now defined as **current public vision
only in, model-owned recurrent state hidden inside the adapter, predictions
out**.  Held-out truth is loaded only after inference and cannot be passed to
the model adapter.

This is a contract and focused-test milestone, not evidence that the current
vision system or policy passes the quality gates.

## Files

- `src/clasher/rl/live_inference_contract.py`: strict schemas, leakage guard,
  adapter boundary, held-out scoring, and fail-closed gates.
- `scripts/evaluate_live_inference_contract.py`: JSONL scorer with source
  hashes and nonzero exit on gate failure.
- `tests/test_rl_live_inference_contract.py`: synthetic contract and scoring
  evidence.

## Input schema

Each current frame contains only:

- episode/frame identity and monotonically increasing capture timestamp;
- visible public clock measurement and confidence;
- the player's visible elixir, four-card hand, visible next card, and
  confidences;
- current visible entities: public identity, owner, position, optional measured
  HP, visible statuses, and confidence;
- card-play events detected in the current frame, with optional placement.

It contains no prior-frame history.  The adapter owns reset and recurrent
updates internally.  A SHA-256 state digest and monotonic state step make that
state trajectory auditable without exporting its values as future inputs.

## Leakage gate

The parser recursively rejects simulator objects and privileged names,
including `BattleState`, `public_card_play_history`, exact opponent elixir,
opponent hand/next card/deck/cycle, critic state, engine/object/target IDs,
pending damage, exact legal-action masks, exact timer/cooldown fields, and RNG
state.  Unknown schema keys also fail closed.

This catches accidental wiring and serialized-state leakage.  It cannot prove
that arbitrary hostile Python code does not use a hidden global.  Production
integration must therefore run the adapter in a vision-only process which does
not import or construct the simulator.

## Held-out metrics and provisional gates

Labels must identify a `validation`, `heldout`, `archetype_test`, or
`chronology_test` split.  Training labels are rejected.  The scorer measures:

| Trajectory | Metric | Provisional gate |
|---|---:|---:|
| public clock | MAE | <= 1.0 second |
| opponent elixir | MAE | <= 0.5 elixir |
| revealed-card cycle | exact counter accuracy | >= 95% |
| deployment position | within 1 tile | >= 90% |
| visible HP | fraction MAE | <= 0.10 |
| visible statuses | set F1 | >= 90% |

Every metric needs the configured minimum sample count.  Missing predictions,
missing labelled values, fabricated placement/status outputs, or extra frames
fail the overall gate.

## Integration prerequisites

1. The vision lane must emit this current-frame schema, including deduplicated
   play-event IDs and stable public entity track IDs.
2. The structured-state lane must provide an adapter that consumes only
   `PublicVisionFrame`; clock, opponent elixir, and cycle state remain private
   inside the model artifact.
3. The held-out TV Royale lane must export labels into a separate file.  Exact
   simulator truth may be used there for scoring, never as inference input.
4. Before promotion, run the adapter in a process whose import graph excludes
   `clasher.battle`, hash all inputs/outputs, and use materially sized held-out
   arena, chronology, and archetype sets.  Synthetic tests are insufficient.

## Dual-HUD spectator perspective gate

`src/clasher/rl/perspective_sanitizer.py` adds the pixel-level privacy boundary
for permissioned dual-HUD spectator footage.  The production artifact is not a
masked full frame.  It contains only detached, read-only copies of:

- the public arena;
- an isolated public clock crop;
- the bottom player's own hand/Next/elixir HUD.

The opponent's top HUD never appears on the returned object.  Raw ndarrays are
rejected by both the policy-input builder and the type-gated cache.  A SHA-256
over named surface shapes and exact pixels makes the boundary auditable.

Sanitization must precede temporal caching and actor accept/reject heuristics as
well as tensor construction.  A production adapter may compute hard cuts from
the sanitized arena but must not retain a previous raw dual-HUD frame or let
top-HUD pixels influence whether an actor frame is emitted.

The current audited portrait geometry uses arena `(0.024, 0.196, 0.954,
0.659)`, public clock `(0.790, 0.105, 0.200, 0.065)`, bottom own HUD `(0,
0.855, 1, 0.140)`, and top private band `(0, 0, 1, 0.160)`.  Geometry remains
the visual adapter's responsibility; the generic sanitizer validates its
privacy relationships and performs only allowlisted copies.
