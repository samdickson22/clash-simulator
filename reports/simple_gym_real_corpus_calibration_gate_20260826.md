# Simple Gym real-corpus calibration gate

Date: 2026-08-26

## Decision

`insufficient_evidence`

The new read-only gate covered all 29 locally materialized matches: 76,148
neutral 10-Hz rows, 65,285 accepted clock rows, 1,007 valid visual play events,
and 918 aligned actor targets. The bounded structural channels below pass, but
the full calibration gate does not. Only 26 regulation-to-overtime transitions
exist, below the declared 30-example minimum, and this worktree has no callable
real-frame-to-simple-engine public-mask adapter.

## Engine boundary

The gate compiled the actual standard simple setup on CPU from
`training_decks/simple_gym_supported_v1.json`. All 66 public roots compiled as
training-supported typed actions. The shared engine contract is a 50-ms logic
tick, 3,600-tick regulation, 6,000-tick tiebreak, canonical lane globals, and
public-mask contract v2.

| Channel | Result | Evidence |
| --- | --- | --- |
| Artifact integrity | pass | All local neutral/action/event artifacts matched manifest SHA-256 and row counts. |
| 100-ms sampling | pass | 76,119/76,119 adjacent neutral rows were exactly 100 ms apart; 95% Wilson lower bound 0.999950. |
| Public-clock local rate | pass | 65,227/65,230 non-reset accepted-clock pairs were within one displayed second of elapsed time; p95 error 0.9 s, 95% lower bound 0.999865. |
| Regulation to overtime | insufficient evidence | All 26 observed transitions were exactly 1 -> 120 and at most 1.0 s from the engine's 180-s boundary, but 26 is below 30; 95% lower bound 0.871271. |
| Overtime to tiebreak | unavailable | No independently labelled 5:00 terminal boundary or tiebreak outcome exists. |
| Play timestamps | pass | 1,007/1,007 valid visual play timestamps were on the 100-ms grid. This does not prove onset accuracy. |
| Typed action identity | bounded pass | 645 targets across 52 engine keys mapped without root collapse; 273 current-corpus actions are outside the enabled engine pool. Only four represented engine keys have at least 30 examples. This is typed-key compatibility, not classifier-accuracy proof. |
| Slot/action encoding | pass | 918/918 targets exactly matched `slot * 576 + y * 18 + x`; 95% lower bound 0.995833. |
| Public mask v2 | contract only | All 29 manifests declare label-independent contract v2. The corpus mask contains 710/918 targets and 513/645 engine-overlap targets. Engine equality is unavailable without a real-frame adapter. |
| Canonical orientation | pass | 1,007/1,007 events matched actor 0 identity orientation and actor 1's 180-degree `(17-x, 31-y)` transform; 95% lower bound 0.996200. |
| Coarse placement encoding | bounded pass | 1,007/1,007 points were within one tile of their encoded center; median 0.254017 tile, p95 0.481086, max 0.698717. Tile and point share a visual source, so this is encoding sanity rather than independent geometry accuracy. |

## Explicit non-gates

The corpus does not currently provide independent acceptance evidence for:

- play-onset alignment despite 100-ms quantization;
- manually associated visible entity trajectories or hitboxes;
- exact HP values, damage deltas, healing, or shields;
- projectile source/target, flight time, chains, pierce, or splash contact;
- status onset/duration, readiness, or hidden RNG;
- crowns, winner, terminal reason, tiebreak damage, or outcome distribution;
- Hero/Evolution variant-specific action accuracy.

These channels are unavailable, not passes. Serialized mechanics, invariants,
seeded deterministic episodes, and policy-visible consistency remain their
current authorities.

## Reproduction

```sh
uv run --frozen --python 3.12 python -m scripts.calibrate_simple_gym_real_corpus \
  /Users/sam/Desktop/code/clasher/datasets/derived/tv_royale_youtube_persistent_batch_causal_clocked_20260825 \
  --engine-manifest training_decks/simple_gym_supported_v1.json
```

- Corpus artifact-set SHA-256: `d2db0c537f1a003ee2468e3a82c8d1a763e82fd9d27681d1e7de227a27f7b9b2`
- Engine manifest SHA-256: `c93de9989841743b535fe5fde182abe19e1983c8f67a0a27d0c191ea9ccd212f`
- JSON stdout SHA-256 from this run: `221d5e7036f82fadb45213f410547282182b64f075d150d64546209f53210291`
- Runtime: 6.67 seconds wall time while the active main training job was left untouched.
