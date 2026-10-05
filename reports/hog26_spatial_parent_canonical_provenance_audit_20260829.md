# Hog 2.6 spatial parent canonical-projection provenance audit

Date: 2026-08-29

## Decision

The retained Hog 2.6 spatial-imitation candidate is **not rejected** for the
suspected `canonical_lane_globals` mismatch.  The `false` value in the old
`fit.json` report is inconsistent with the serialized checkpoints and with the
actual causal sidecar tensors.  It must be treated as stale/reporting metadata,
not as the effective model or observation contract.

This audit only clears that specific provenance concern.  It does not promote
the policy, prove mid-ladder skill, or repair the policy's documented weakness
against balanced, reactive-defense, and spell-control opponents.

## Frozen inputs

- Initial RL checkpoint:
  `checkpoints/hog26_executed_strategy_hazard_seed1108001/policy_v2_update_000014.pt`
  - SHA-256: `2d32dae6706f3e0a569a0451dd03d7587d7e161d316278fe3e8b3cac0d1795e3`
- Matched control:
  `checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/control.pt`
  - SHA-256: `c2eaaf3c6c3bb10db33b13380e7bf36ce84c5f1505b55b98b7060b633c8b1be8`
- Retained candidate:
  `checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt`
  - SHA-256: `28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`
- Causal public sidecar:
  `datasets/derived/hog26_u46x2_reactive_slow_seed1152001/train/public_v2.npz`
  - SHA-256: `6b92f2316362f518164042a172ea7e981b0aacd40ee045f304ba595c8e520691`
- Historical fit report:
  `reports/hog26_u46x2_reactive_slow_spatial_seed1154001/fit.json`
  - SHA-256: `28513ed3faf5062c942d5abbfa67b4c420b07520d2c8c76da4516cd134bf7efa`

## Checkpoint contract

Loading all three checkpoints with `torch.load(..., weights_only=False)` and
parsing `model_config` shows:

| Checkpoint | `canonical_lane_globals` |
|---|---:|
| Initial RL checkpoint | `true` |
| Matched control | `true` |
| Retained candidate | `true` |

The historical fit report says `false`.  The current fitter derives the
effective builder setting from the loaded checkpoint config when an initial
checkpoint exists, so a false CLI default does not override a true checkpoint.

## Tensor-level sidecar audit

For every sidecar row with:

- exactly two visible own Princess Tower entity tokens (`tower:Tower`, token
  352),
- both entity HP feature confidences greater than `0.68`, and
- both own left/right global HP confidences greater than `0.68`,

the two tower entity HP fractions were ordered by canonical entity x and
compared against global features 8 and 9.

Result:

- eligible fully observed rows: **22,775**
- exact canonical left/right matches: **22,775**
- swapped-only matches: **0**
- other mismatches: **0**

Therefore the retained sidecar's entity coordinates and tower-global lanes are
internally consistent under canonical perspective on every row where both
representations are observable.

## Next action

Keep the retained Hog policy as the direct PPO parent.  Do not rebuild it only
because of the stale report flag.  The next bounded experiment should target
the proven gameplay failures directly with an anchored hard-opponent PPO
curriculum and retain exact screen/quarantine, strategy, Hog-use, and
no-regression gates.
