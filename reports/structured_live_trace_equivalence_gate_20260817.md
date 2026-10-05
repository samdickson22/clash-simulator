# Structured live trace equivalence gate

Date: 2026-08-17

## Decision

The bounded A22 live-adapter contract gate passes after one material adapter
fix.  One hundred independently reset, simulator-projected traces completed;
the live adapter and the independent direct causal arm were exact on every
accepted input tensor, public mask, deterministic action, recurrent hidden
state, and recurrent cell state.

This is an execution-contract result, not evidence that the accepted policy is
deployable or skilled.  The 100 episodes are deliberately short phase scenarios
(32 native ticks, or earlier natural tiebreak termination), not 100 full
five-minute battles.  They test reset-to-done trace behavior without turning a
contract check into sustained gameplay training.

## Bug found and fixed

The first asymmetric actor-1 smoke trace failed before the gate was accepted.
The compatibility checkpoint has `canonical_lane_globals=false`; the direct
causal path therefore retained physical actor-1 tower lanes, while
`StructuredLiveInferenceAdapter._globals()` unconditionally used canonicalized
x.  The first mismatch was actor global 8: direct `0.74`, live `1.0`.

The adapter now reads the checkpoint's explicit `canonical_lane_globals`
contract. Entity positions remain half-turn canonical for actor 1. Tower slot
assignment alone uses physical x for actor 1 when the checkpoint says false,
and canonical x when it says true. A focused asymmetric six-tower test covers
both contracts. Fresh causal training still requires `true`; the false branch
exists only to reproduce a legacy checkpoint faithfully.

## Reproducible command

```bash
uv run python scripts/verify_structured_live_trace_equivalence.py \
  --traces 100 \
  --seed 1064901 \
  --output reports/structured_live_trace_equivalence_seed1064901.json
```

Checkpoint:

- path: `checkpoints/fresh_structured_causal_v1_seed1062701/resource_belief_gated_seed1063602/resource_u10_gate0.pt`
- SHA-256: `3353615954fdcfdb24f2ba570f1888cd6130242238391a9bcf98dcedbcfc5b88`

The command was run twice. Both JSON outputs were byte-identical.

## Exact result

- requested/completed traces: `100/100`
- failures: `0`
- seats: `50` actor 0, `50` actor 1
- asymmetric traces: `100`
- phase scenarios: `25` regulation, `25` overtime transition, `25` triple
  elixir, `25` tiebreak
- accepted recurrent steps: `350`
- exact input tensor comparisons: `8,050` (`23` fields per accepted step)
- exact public-mask comparisons: `350`
- exact deterministic-action comparisons: `350`
- exact hidden-state comparisons: `350`
- exact cell-state comparisons: `350`
- reset checks: `100`
- duplicate-frame checks: `100`
- duplicate-timestamp checks: `100`
- before-cadence jitter checks: `100`
- allowed one-interval-drop checks: `75`
- non-grid cadence-jitter checks: `125`
- repeated current-cue steps: `175`
- unknown-hand steps: `10`
- unknown-entity steps: `5`
- typed confidence failures: `75`; recurrent state preserved: `75/75`
- label-independent mask checks: `350`
- privileged counterfactual-label rejections: `700`

Hashes:

- trace-set SHA-256: `ed4d206df8f506811c3acd2f82dfe0887f8096a0d61f13f92d58b931cea7292e`
- canonical in-document result SHA-256: `0e84c920d245806b89140832d3209e07808d16f7dc320c552f06ddbf08633a4c`
- JSON file SHA-256: `b7608973dbb3422fbe383832ece30bd9a5b6914d5443d3378ad5d6511401f21d`

## What the two arms share and do not share

Both arms share the frozen checkpoint, token catalog, and public card catalog.
They do not share recurrent state or model invocation. The direct arm constructs
current public tensors from the simulator's exact structured state using an
independent projection, builds its own contract-v2 public mask, and advances its
own recurrent tuple and previous action. The live arm consumes only a
`PublicVisionFrame`, rebuilds tensors and the mask internally, and advances its
own serialized adapter state.

For each accepted step the gate compares all `LivePolicyInputs` tensor fields
exactly before invoking either arm. It then invokes the model separately and
compares action and recurrent tensors byte-for-byte. Ignored cadence frames and
invalid-confidence frames must leave recurrent tensors, previous action, and
state step unchanged.

## Coverage details

Each scenario starts from a real `SelfPlayBattleEnv` reset, applies deterministic
asymmetric public tower HP and elixir, advances with independently chosen exact
simulator-legal actions, and reaches `done`. Public frames contain only current
visible state. The gate exercises:

- both canonical actor perspectives;
- asymmetric lane-sensitive tower HP;
- explicit episode reset;
- regulation, overtime, triple-elixir, and tiebreak state;
- duplicate frame IDs, duplicate timestamps, early frames, one missing cadence
  interval, and non-grid cadence jitter;
- the same public play cue visible in consecutive accepted frames;
- accepted unknown hand/entity identities, which fail closed to missing tokens;
- invalid clock, Next, and HP confidence/value pairs, which fail before state
  mutation; and
- two counterfactual expert labels per accepted frame, neither of which can
  enter the public frame or change its mask.

## Validation

```text
uv run ruff check \
  src/clasher/rl/structured_live_adapter.py \
  scripts/verify_structured_live_trace_equivalence.py \
  tests/test_verify_structured_live_trace_equivalence.py

uv run mypy \
  src/clasher/rl/structured_live_adapter.py \
  scripts/verify_structured_live_trace_equivalence.py

uv run pytest -q \
  tests/test_verify_structured_live_trace_equivalence.py \
  tests/test_rl_structured_live_adapter.py \
  tests/test_canonical_projection_parity.py
```

Focused result: `61 passed`.

## Remaining limits

- The simulator projection is exact and synthetic; it does not measure camera
  detector accuracy, association errors, or live HUD latency.
- Short traces prove state-machine equivalence across the named boundaries, not
  long-horizon gameplay quality or stability across a natural five-minute game.
- Visible statuses remain typed but ignored by this compatibility checkpoint,
  as already declared by the adapter.
- The accepted checkpoint still ignores the new deterministic public clock and
  play-event features. Passing this gate makes that limitation reproducible; it
  does not remove it.
- A future fresh-lineage gate should repeat the same harness with
  `canonical_lane_globals=true`, the current-client card/variant closure, and
  the production detector's measured confidence/missingness distribution.
