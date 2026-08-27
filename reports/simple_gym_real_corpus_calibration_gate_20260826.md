# Simple Gym real-corpus calibration gate

Refresh date: 2026-08-27

## Decision

`fail`

The read-only gate now covers every manifest in two complete, disjoint local
clocked corpora: 42 matches, 111,404 neutral 10-Hz rows, 95,500 accepted clock
rows, 1,525 valid visual play events, 1,380 aligned actor targets, and 111,426
actor projection/mask rows. Artifact integrity and the bounded structural
channels pass. The overall gate fails because the expanded regulation-to-
overtime sample does not meet the configured confidence bound, while exact
public-mask engine equivalence remains unavailable rather than being upgraded
from contract-only evidence.

## Engine boundary

The gate compiled the actual standard simple setup on CPU from
`training_decks/simple_gym_supported_v1.json`. All 66 public roots compiled as
training-supported typed actions. The shared engine contract is a 50-ms logic
tick, 3,600-tick regulation, 6,000-tick tiebreak, canonical lane globals, and
public-mask contract v2. The callable tensor provider identifies its semantics
as `public-action-mask-v2/tensor-actor-projection-v1`.

| Channel | Result | Evidence |
| --- | --- | --- |
| Artifact integrity | pass | All 42 manifests' neutral, action, event, and 84 actor-trajectory artifacts matched declared SHA-256 and row counts. All match IDs were disjoint. |
| 100-ms sampling | pass | 111,362/111,362 adjacent neutral rows were exactly 100 ms apart; 95% Wilson lower bound 0.999966. |
| Public-clock local rate | pass | 95,418/95,421 non-reset accepted-clock pairs were within one displayed second of elapsed time; p95 error 0.9 s, 95% lower bound 0.999908. |
| Regulation to overtime | fail | All 37 observed transitions were exactly `1 -> 120` and at most 1.0 s from the engine's 180-s boundary. The sample clears the 30-example floor, but its 95% Wilson lower bound is 0.905942, below 0.95. |
| Overtime to tiebreak | unavailable | No independently labelled 5:00 terminal boundary or tiebreak outcome exists. |
| Play timestamps | pass | 1,525/1,525 valid visual play timestamps were on the 100-ms grid. This does not prove onset accuracy. |
| Typed action identity | bounded pass | 996 targets across 58 engine keys mapped without root collapse; 384 current-corpus actions are outside the enabled engine pool. Nine represented engine keys have at least 30 examples. This is typed-key compatibility, not classifier-accuracy proof. |
| Slot/action encoding | pass | 1,380/1,380 targets exactly matched `slot * 576 + y * 18 + x`; 95% lower bound 0.997224. |
| Public mask v2 | contract only | All 111,426 actor rows join to neutral public state and carry structurally valid stored v2 masks. The corpus mask contains 1,076/1,380 targets and 798/996 engine-overlap targets. Exact tensor-provider equality is unavailable for the reasons below. |
| Canonical orientation | pass | 1,525/1,525 events matched actor 0 identity orientation and actor 1's 180-degree `(17-x, 31-y)` transform; 95% lower bound 0.997487. |
| Coarse placement encoding | bounded pass | 1,525/1,525 points were within one tile of their encoded center; median 0.286652 tile, p95 0.482535, max 0.702271. Tile and point share a visual source, so this is encoding sanity rather than independent geometry accuracy. |

## Overtime sample expansion

The original complete 29-match corpus contributed 26/26 successful observed
resets. The entire additional 13-match clocked corpus is disjoint and contributes
11/11; no match or reset was selected after observing its result. The combined
denominator is therefore 37/37.

That clears the declared 30-example count floor but does not clear the separate
`minimum_wilson_95_lower = 0.95` gate. With zero failures, 73 total successes are
needed to reach that bound, so the current channel needs 36 additional all-
success examples. The denominator was expanded by whole-corpus inclusion and
duplicate match IDs are a hard integrity failure.

## Public-mask mapping audit

The committed `SimplePublicMaskV2Provider` is callable, and the corpus supplies
substantial bridge evidence:

- 84 actor-trajectory artifacts contain 111,426 rows;
- every actor row joins by `snapshot_id` to neutral public entities;
- every row carries a structurally valid stored label-independent v2 mask;
- all 42 manifests pin the same vocabulary SHA-256, and the locally present
  vocabulary artifact matches it exactly.

This is still insufficient to instantiate the provider without guessing:

- zero actor rows serialize the complete tensor projection, specifically
  `actor.global_features[11:13]` for left/right Crown Tower HP/alive state;
- the stored NumPy builder confidence-gated tower-zone extensions when those
  fields were unavailable, while the tensor provider interprets zero HP as a
  destroyed tower, so filling zeros would change placement legality;
- zero manifests pin the tensor provider semantics ID;
- zero manifests pin its semantics digest;
- zero manifests pin its typed card/entity lookup digest and card-data
  authority.

Stable string keys and a matching vocabulary hash are not substitutes for those
missing semantics. Running the tensor provider would require inventing tower
state or lookup authority, so an engine-versus-real equality rate would be a
fabricated metric. The truthful channel remains `contract_only` with
`engine_equivalence = unavailable`.

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
  --additional-corpus-root /Users/sam/Desktop/code/clasher/datasets/derived/tv_royale_youtube_1000_causal_clocked_20260826 \
  --engine-manifest training_decks/simple_gym_supported_v1.json \
  --vocabulary-manifest /Users/sam/Desktop/code/clasher/reports/current_client_youtube_stable_vocabulary_v1.json
```

- Corpus artifact-set SHA-256: `f30c79067ca4e3a05e07e56ebf50ebf3d9421d365073082d640f96f3398cdda9`
- Engine manifest SHA-256: `c93de9989841743b535fe5fde182abe19e1983c8f67a0a27d0c191ea9ccd212f`
- Vocabulary manifest SHA-256: `960c1c1d68dea56786b0e196c5fc772b298fa16db168a81ca6c6d36c60c54704`
- JSON stdout SHA-256: `7fa965238c3c251ddc7ebb6114516d63b984b74c5c20fd261bf2adf55236bbbe`
- Runtime: 15.94 seconds wall time while corpus artifacts were opened read-only.
