# Causal real-play observation contract v2

Date: 2026-08-14  
Source HEAD: `20cc861b23937ec884fc22335c62d5b03a027f51`  
Status: implementation and held-out visual validation complete; fresh causal
policy training in progress

## Decision

The real-play actor no longer receives exact simulator-only status clocks or an
exact simulator legal-action mask. Its inputs are now restricted to quantities
that the current camera pipeline directly measures, derives causally from past
frames, or looks up from a detected public card identity. Exact state remains
available only to the asymmetric critic and oracle.

Accepted actor inputs:

- detected entity identity, team, kind, and sprite centre;
- measured/carried HP with explicit confidence;
- public static card mechanics (speed, range, sight, collision radius, damage);
- causally tracked motion direction and short occlusion prediction;
- four visible hand cards, timer phase, elixir, and tower HP;
- temporally confirmed visible spell/effect entities;
- a legal-action mask reconstructed only from visible hand, elixir, terrain,
  deploy territory, and visually tracked building occupancy.

Still withheld from the actor:

- exact stun/slow/haste durations, attack windup, charge and forced-movement
  clocks, stealth clocks, hidden-building state, and effect progress;
- exact card-refill clock, opponent hand/elixir, inferred opponent play history,
  crowns, and Champion ability state;
- simulator object IDs, targets, RNG, and future frames.
- the previous simulator-shaped reward; the recurrent actor observes its own
  previous action and the next camera state instead of a privileged scalar.

Unavailable values are zero with zero confidence. They are not filled with
neutral-looking simulator truth.

## Temporal vision and visual effects

`CausalVisionTracker` associates bodies using detected identity, team, and
predicted image-plane position. It derives motion, carries short HP/HUD gaps
with decaying confidence, predicts brief occlusions, and expires stale tracks.
Visible spell/effect detections are accepted only after two chronological
observations, reducing 68 raw effect rows to 17 confirmed rows on the held-out
replay. This kept persistent Earthquake regions while discarding most
single-frame spell confusions and flashes.

The simulator causal rollout path uses the same projection and temporal gate.
Privileged critic tensors are left exact.

## Public legal-action mask

The causal actor mask has no `BattleState` input. Building placements use
data-derived square footprints; troop/building overlap is conservative under
sprite-centre localization error. Champion ability is disabled until its UI
state is visually extracted. Carried hand identities cannot authorize a play;
the current hand must be directly observed.

A seeded audit over 20 battles and 960 player-decisions found:

- false-legal actions: **0**;
- aggregate retained exact legal choices: **90.90%**;
- median per-decision coverage: **100%**;
- 10th-percentile per-decision coverage: **93.26%**.

The audit uses the exact simulator mask only as an offline oracle. It is never
passed to the causal actor. A general `1e-9` affordability tolerance also fixes
the simulator rejecting logically affordable cards after floating-point elixir
regeneration (for example `2.999999999999996 >= 3`).

Offline imitation now follows the same rule. Public-observation sidecars can
carry their own public-only action masks, and the loader overlays those masks
instead of retaining the source simulator corpus mask. When sensor uncertainty
masks the demonstrated move, only that one recorded action is restored as
causal evidence; no other exact legal alternatives are revealed. Legacy human
type-only labels use a fixed carrier tile, so their high carrier-recovery count
does not imply a failed camera observation.

The sidecar loader independently enforces this contract. It rejects confidence
on forbidden status/timer fields, nonzero values hidden behind zero confidence,
future fifth-hand cards, misaligned masks, and unknown contract versions. It
also zeroes every causal imitation `previous_rewards` input. Causal PPO rollout
collection applies the same zero-reward-input rule while retaining the true
reward separately for optimization and advantage estimation.

## Held-out replay evidence

Source:

`datasets/external/tv_royale_raw_validation/arena_29/d0417583-846d-4659-8d3b-54e0318084ed/frames.parquet`

Extraction command:

```bash
PYTHONPATH=src:. uv run python scripts/extract_tv_royale_raw_cascade.py \
  --input-parquet datasets/external/tv_royale_raw_validation/arena_29/d0417583-846d-4659-8d3b-54e0318084ed/frames.parquet \
  --arena 29 --replay d0417583-846d-4659-8d3b-54e0318084ed \
  --output-dir reports/causal_vision_validation_contract_v2 \
  --detector-weight datasets/external/KataCR/runs/detector1_v0.7.13.pt \
  --detector-weight datasets/external/KataCR/runs/detector2_v0.7.13.pt \
  --device mps --batch-size 16 --audit-samples 6
```

Results:

- 77 decision samples and 821 visible actor entities;
- 420 measured/carried HP values (51.16% entity coverage);
- 577 motion directions (70.28% entity coverage);
- 355 tower HP measurements;
- 17 temporally confirmed effect entities;
- 41.82 seconds excluding source download, or 86.08 games/hour with this audit
  configuration;
- sidecar SHA-256:
  `85854fe0cb36c5d2013199503269c264870e40fbcbf65c3380ac7ee08bfdfa80`.

Actor-tensor audit:

`reports/causal_vision_validation_contract_v2/actor_tensor_audit/contact_sheet.jpg`

SHA-256:
`466e2c50cba16213090305e96ee275200266dbfe664d17ba85bc9d33eba99ae8`

The plotted crosses are explicitly sprite centres, never claimed hitboxes.
Visual inspection across quiet, bridge, crowded, spell, overtime, and tower
frames found the tensor centres aligned with the rendered bodies/effects. Dense
text overlaps in crowded frames, but that is an audit-renderer readability
issue rather than a tensor-geometry error.

## Training-path validation

The confidence-aware encoder consumes separate identity, feature, hand, and
global confidence tensors. A 2-worker / 4-environment parallel rollout smoke
completed one PPO update and wrote:

`reports/causal_vision_parallel_smoke/policy_v2_update_000001.pt`

SHA-256:
`e87488fac45cf9480257167df46119a058224586b34d705b21cea63480ea7adf`

This 94,596-parameter checkpoint is a wiring smoke test only and is not a
candidate policy.

The exact simulator rehearsal corpus was projected into this contract before
training:

- 121,917 aligned samples;
- 1,270,010 visible entity instances;
- HP on 62.10% and motion on 21.94% of visible instances;
- 2,277 demonstrated-action recoveries;
- sidecar SHA-256
  `6aa7356e1ffa8c1af0001bad35f46718c1d096bb95a1df76f8c499331e4021df`.

The 29,722-sample / 1,000-game human vision sidecar was also upgraded to
public-only masks. Its 20,713 recoveries correspond to the corpus's type-only
fixed placement carrier; training ignores that arbitrary location and retains
the visible hand-slot label. Upgraded sidecar SHA-256:
`05c16103a9aa64aca84dc9d3d02d709076d86200b0c4c34898bc532f9da5d996`.

Relevant gate: 164 focused structured-policy/action-mask/imitation/vision/replay
tests pass, in addition to the held-out visual audit above.

## Causal rehearsal result

The accepted warm start is:

`checkpoints/fresh_compact_causal_v2_seed1062401/causal_pretrain_e3.pt`

SHA-256:
`edffba26ce3f6814005b7bbfc701f2653eb7a753ce45b9b8eb5f978716738e0c`

It has 2,372,303 parameters and was trained for three epochs on the exact
simulator rehearsal trajectories after projecting every actor observation and
mask into the causal vision contract. The actor receives zero previous-reward
inputs; exact reward remains available only to the optimizer and critic.

A deterministic 128-complete-episode recurrent evaluation (19,586 samples,
seed 1062403) improved the matched untrained control as follows:

| Metric | Control | Causal pretrain |
| --- | ---: | ---: |
| action-type accuracy | 53.46% | 90.13% |
| action-type NLL | 0.4462 | 0.2549 |
| conditional card-slot accuracy | 46.84% | 67.08% |
| conditional location NLL | 5.0396 | 3.8054 |
| play/no-op accuracy | 58.67% | 92.23% |
| play Brier score | 0.1280 | 0.0571 |
| 10-bin play ECE | 0.1573 | 0.0333 |

The model made 7,726 action-type improvements versus 544 regressions relative
to the matched control. This establishes a valid causal warm start, not a
gameplay promotion. Its remaining weaknesses are play recall (57.30%),
played-card slot accuracy (35.92%), and correct-slot placement within one/two
tiles (19.88%/25.22%).

Full recurrent evidence:

`reports/fresh_compact_causal_v2_seed1062401/causal_pretrain_e3_recurrent_128ep.json`

## Rejected adaptation experiments

A human-video slot-only update improved conditional card-slot accuracy on a
128-episode human holdout from 47.13% to 49.38%, but regressed the simulator
rehearsal holdout from 67.08% to 64.86% and worsened action-type NLL. It is not
promoted.

The full human timing update raised rehearsal play recall from 57.30% to
68.06%, but action-type accuracy fell from 90.13% to 88.12%, Brier score
worsened from 0.0571 to 0.0712, ECE from 0.0333 to 0.0787, and it caused 585
action regressions versus 192 improvements. It is rejected.

Conservative 25% and 50% timing blends were also tested on the identical
19,586 samples. The 25% blend reached 59.99% play recall but caused 82
regressions versus 44 improvements and worsened NLL/Brier/ECE. The 50% blend
reached 62.89% recall but caused 216 regressions versus 99 improvements and
worsened every proper scoring metric further. Both are rejected; recall alone
is not a promotion criterion.

Blend evidence:

`reports/fresh_compact_causal_v2_seed1062401/causal_timing_blends_recurrent_128ep.json`

## Rejected visual-state classifier

The associated detector dataset contains 4,654 sprite crops, but only 129
attack, 27 freeze, and 36 shield examples. A pretrained 2.54M-parameter
MobileNetV3-small was trained for 12 epochs with real-arena backgrounds and
whole troop identities held out for attack/freeze. It memorized the training
sprites and failed identity transfer: late held-out attack and freeze F1 were
zero; shield had only one source identity and therefore cannot establish
identity generalization. The best mean F1 was 0.119.

Report:

`reports/visual_state_classifier_seed2301/report.json`

SHA-256:
`db7b053931f7b3a572efe4c94c7a84c44822c814f1f2752d455ec27ab2dcfafc`

Decision: do **not** integrate this classifier. Subtle animations remain a
recurrent inference problem until a materially larger, identity-diverse state
dataset is available.

## Next gate

Keep the accepted causal rehearsal checkpoint unchanged and measure its
gameplay baseline against deterministic strategy and random opponents. The
next learning phase should be causal league RL with an exact privileged critic,
public actor observations/masks, and actor previous reward permanently zero.
This is the correct place to improve play timing and defense because the policy
can optimize consequences instead of copying the human corpus's sparse and
biased decision timestamps.

Promotion still requires held-out deck/archetype gameplay gains and no
regression on the existing safety opponents. Green feature/mask tests or a
single imitation metric are insufficient.
