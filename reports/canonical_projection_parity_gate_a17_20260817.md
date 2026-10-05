# Canonical projection parity gate A17

Date: 2026-08-17

## Decision

Gate A17 passes for fresh policies using both `canonical_perspective=true` and
`canonical_lane_globals=true`, after fixing one production wiring defect in the
fresh recurrent trainer. No checkpoint, corpus, sidecar, or historical manifest
was rewritten.

The neutral extraction contract remains deliberately absolute-world. Actor
canonicalization happens once, at the structured observation/live adapter and
action boundaries. Actor 1 uses a 180-degree half-turn; actor 0 is unchanged.

## Production defect found and fixed

`train_recurrent.main()` previously made two conflicting choices for a fresh
causal run:

- `PolicyConfig.canonical_lane_globals` was set to `true` for
  `causal-frame-v1` and `causal-vision-v1`.
- The shared `StructuredObservationBuilder` was created with
  `canonical_lane_globals=false` whenever no resume checkpoint existed.

The trainer then injected that shared builder into each single-worker
`SelfPlayBattleEnv`. Consequently, a new causal checkpoint could claim the
corrected actor-1 lane contract while training on legacy unswapped tower
globals. Local evaluation and rehearsal paths also reused the mismatched
builder.

The fix adds `_canonical_lane_globals_for_run()` and computes the lane-frame
choice once. Both the builder and fresh `PolicyConfig` consume that value.
Resumed checkpoints continue to preserve their recorded boolean, including
legacy `false` checkpoints; this change does not retrofit them.

## Deterministic parity matrix

The new `tests/test_canonical_projection_parity.py` covers:

- Both actor IDs through neutral absolute-world projection and the current
  `StructuredLiveInferenceAdapter`.
- All 576 world tiles, all four hand slots, and both actors: 4,608 exact
  encode/decode round trips through `DiscreteTileActionSpace`.
- Every arena tile center through both
  `StructuredObservationBuilder._canonical_position` and
  `StructuredLiveInferenceAdapter._canonical_position`: 1,152 comparisons.
- Troop, building, projectile, and area-effect rows for both teams at all four
  corner tile centers and both actor views: 64 structured/live comparisons.
- Five asymmetric native facing vectors in both actor views: 10 vector
  half-turn comparisons.
- Six distinct tower-health fractions, compared for both actors between
  simulator structured globals and live vision globals: 12 lane-sensitive
  values. Actor 1 proves the expected left/right swap for both own and enemy
  towers.
- Fresh causal, fresh exact-simulator, and resumed `true`/`false` trainer
  configuration paths.

Motion/facing availability is not overstated: the simulator structured schema
rotates native facing channels 27-28, while the current-frame live contract
intentionally supplies those channels as zero and reports
`motion_channels=zero_current_frame_only`. The gate proves the coordinate and
vector convention; it does not claim the vision adapter observes motion that
its current schema omits.

## Evidence

Commands:

```text
uv run pytest -q tests/test_canonical_projection_parity.py
uv run pytest -q tests/test_canonical_projection_parity.py tests/test_rl_structured_live_adapter.py tests/test_rl_structured_policy.py -k 'canonical or lane or adapter'
uv run ruff check src/clasher/rl/train_recurrent.py tests/test_canonical_projection_parity.py
uv run mypy src/clasher/rl/train_recurrent.py
git diff --check -- src/clasher/rl/train_recurrent.py tests/test_canonical_projection_parity.py reports/canonical_projection_parity_gate_a17_20260817.md
```

Expected focused results at handoff: 45 tests in the exhaustive file and 71
selected canonical/lane/adapter tests, with Ruff, mypy, and diff-check clean.

## Scope limits

- This is representation and wiring parity, not game-engine parity.
- It does not validate detector accuracy, hidden-state estimation, reward
  quality, or gameplay skill.
- It does not make old `canonical_lane_globals=false` policies compatible with
  the new lane convention.
- A new lineage must record `canonical_lane_globals=true`; mixing samples or
  checkpoints across the two lane conventions remains invalid unless an
  explicit migration is designed and separately proven.
