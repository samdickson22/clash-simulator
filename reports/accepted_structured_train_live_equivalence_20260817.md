# Accepted structured checkpoint: train/live feature equivalence audit

Date: 2026-08-17

## Executive decision

The accepted checkpoint is **not trained on privileged opponent hand/elixir or
exact status clocks**, and its opponent-elixir belief is safely hidden from the
policy by a zero gate.  However, it is not yet a deployment-equivalent vision
policy.  Its `causal-frame-v1` training rows were produced by degrading exact
simulator observations with hand-written missingness probabilities.  Several
important retained values remain exact and noiseless, while live/YouTube values
are detector estimates with different semantics and confidence distributions.

The highest-risk gaps are:

1. exact entity identity and position with 100% entity retention in training;
2. exact HP and tower HP with dropout but **zero measurement noise**;
3. native simulator facing in channels named `motion_x/y`, versus measured
   displacement in video;
4. exact four-card own hands but **mixed Next semantics across the lineage**:
   exact during earlier simulator pretraining, then entirely missing in the
   inspected 12,288-row causal sidecar rehearsal;
5. exact own elixir with confidence 1.0;
6. fixed synthetic confidence values (`.85`, `.69`, `.60`, `1.0`) consumed by
   learned confidence projections, versus uncalibrated live scores; and
7. a public legal-action mask that requires hand confidence `>= .99`, although
   real recognition confidence should not be assumed to equal one.

Do not spend a long RL run on this input distribution.  First run the bounded
corruption A/B ladder at the end of this report, then retrain the smallest
candidate that closes the observed domain gaps.

## Accepted artifact pinned

- checkpoint:
  `checkpoints/fresh_structured_causal_v1_seed1062701/resource_belief_gated_seed1063602/resource_u10_gate0.pt`
- SHA-256: `3353615954fdcfdb24f2ba570f1888cd6130242238391a9bcf98dcedbcfc5b88`
- actual `model_config`: `causal-frame-v1`, confidence-aware, structured memory
  size 64, hybrid semantic-v3 cards, 128 entities, no public-history/seen-card
  slots, learned resource estimator, policy resource gate exactly zero
- checkpoint `args.actor_observation_domain` still says `simulator-exact`; this
  is stale upgrade provenance.  Runtime behavior follows `model_config`, but
  future artifacts should make those fields agree.

The configuration contract is at
[model.py](/Users/sam/Desktop/code/clasher/src/clasher/rl/model.py:25).  The
resource gate converts the learned belief back to the legacy constant one at
zero [model.py](/Users/sam/Desktop/code/clasher/src/clasher/rl/model.py:1891).

## Legend

- **Exact-sim**: numerically exact simulator truth used to create the actor row.
- **Measured**: obtainable from current pixels, with nonzero sensor error.
- **Lookup**: public static card data derived after visual identity; it should
  live in model weights/buffers rather than in an external runtime database.
- **Zero**: value and confidence are always zero in accepted training.
- **CF**: current-frame observation.
- **MR**: model-owned recurrent state.
- Recommendations: **KEEP**, **RANDOMIZE**, **DROP/REDEFINE**, or **KEEP ZERO**.

The 32 entity and 18 global names are authoritative in
[public_observation.py](/Users/sam/Desktop/code/clasher/src/clasher/rl/public_observation.py:15).
Accepted simulator degradation is defined in
[public_observation.py](/Users/sam/Desktop/code/clasher/src/clasher/rl/public_observation.py:348).

## Entity table and confidence channels

All retained entity values are paired with per-field confidence, while identity
has its own confidence.  Accepted training never creates detector false
positives and uses `entity_keep_probability=1.0`, so every visually eligible
simulator object is retained with exact identity confidence `.85`.  Live and
YouTube detection can miss, duplicate, misclassify, or invent objects.

| # | actor feature | accepted simulator-training source | live measurability | current YouTube neutral source | state | shift/leakage judgment and recommendation |
|---:|---|---|---|---|---|---|
| ID | `entity_ids` | Exact visible simulator identity; no FN/FP; confidence `.85` | Detector/classifier, error-prone | Arena detector exists but April-2024 vocabulary is stale | CF | **Critical shift. RANDOMIZE** FN/FP/confusions/unknowns per class; calibrate identity confidence. Public, not a privacy leak. |
| mask | `entity_mask` | Exact alive/visible list; eligible retention 100% | Detector presence | Available, incomplete | CF | **Critical shift. RANDOMIZE** count, misses, duplicates, occlusion, and packing order. |
| 0 | `x` | Exact simulator center, no noise, confidence `.85` | Sprite/body center estimate | Available | CF | **RANDOMIZE** class/scale-dependent jitter and occasional association swaps. |
| 1 | `y` | Exact simulator center, no noise, confidence `.85` | Sprite/body center estimate | Available | CF | Same as `x`; test bridge/tower/crowd separately. |
| 2 | `own_team` | Exact ownership, confidence `.85` | Team classifier/color | Available but team accuracy not separately validated | CF | **RANDOMIZE** team flips at measured rate; a flip changes strategic meaning. |
| 3 | `enemy_team` | Exact complement, confidence `.85` | Team classifier/color | Available | CF | Tie to one calibrated ownership distribution, not independent noise. |
| 4 | `troop_kind` | Exact identity-derived one-hot, confidence `.85` | Derived from detected identity | Available | CF | **KEEP**, but corrupt jointly with identity. |
| 5 | `building_kind` | Exact identity-derived one-hot, confidence `.85` | Derived from detected identity | Available | CF | **KEEP**, jointly corrupt; building misses also distort action mask. |
| 6 | `projectile_kind` | Exact identity-derived one-hot, confidence `.85` | Partial detector vocabulary | Partial/stale | CF | **RANDOMIZE heavily** or drop until projectile recall is gated. |
| 7 | `area_effect_kind` | Exact identity-derived one-hot, confidence `.85` | Partial visible-effect detector | Partial | CF | **RANDOMIZE heavily** with confusion and temporal flicker. |
| 8 | `other_kind` | Other-kind objects fail the `4:8` visible-kind eligibility check; effective zero | No proven sensor meaning | Not emitted | CF | **KEEP ZERO / remove next model**. Do not activate merely because contract permits it. |
| 9 | `hp_fraction` | Exact HP, retained independently 66%, no noise, confidence `.69` | Noisy bar-fill measurement | Implemented; about 56.5% entity coverage | CF | **Critical shift. RANDOMIZE** bias/noise/dropout conditioned on body, team, effects, and occlusion. |
| 10 | `shield_fraction` | Zero/confidence zero | Shield visual potentially measurable, not implemented | Unavailable | CF | **KEEP ZERO** until onset/amount labels exist; exact simulator shield would leak. |
| 11 | `airborne` | Zero/confidence zero despite public static identity | Inferable from identity/animation, not emitted | Unavailable as field | CF/Lookup | **KEEP ZERO** for this checkpoint; encode in model-internal card semantics in next model. |
| 12 | `deployment_pending` | Zero/confidence zero | Visual onset possible, not implemented | Unavailable | CF | **KEEP ZERO**; exact simulator deployment flag would leak. |
| 13 | `deployment_remaining_fraction` | Zero/confidence zero | Approximate animation timing only | Unavailable | MR | **KEEP ZERO**; later use detected onset + model-owned timer. |
| 14 | `stun_remaining` | Zero/confidence zero | Exact remaining time not visible | Unavailable | MR | **KEEP ZERO**; visible stun onset may seed internal timer later. |
| 15 | `slow_remaining` | Zero/confidence zero | Exact remaining time not visible | Unavailable | MR | **KEEP ZERO**; onset + internal timer only after validation. |
| 16 | `haste_remaining` | Zero/confidence zero | Exact remaining time not visible | Unavailable | MR | **KEEP ZERO**. |
| 17 | `special_move_active` | Zero/confidence zero | Some charge/jump animation visible | Unavailable | CF | **KEEP ZERO** until a classifier is trained. |
| 18 | `stealth_active` | Zero/confidence zero | Visible/partially occluded semantics vary | Unavailable | CF/MR | **KEEP ZERO**; exact stealth clock would leak. |
| 19 | `hidden_building` | Zero/confidence zero | Hidden Tesla is not directly visible | Unavailable | MR | **KEEP ZERO**; do not substitute simulator state. |
| 20 | `forced_movement` | Zero/confidence zero | Motion might indicate it, not exact | Unavailable | CF/MR | **KEEP ZERO**. |
| 21 | `attack_windup` | Zero/confidence zero | Animation onset potentially measurable | Unavailable | CF/MR | **KEEP ZERO**; later detect onset and track internally. |
| 22 | `charging` | Zero/confidence zero | Animation potentially measurable | Unavailable | CF | **KEEP ZERO** until labeled. |
| 23 | `base_speed` | Exact simulator runtime value, confidence `.85`; video converter substitutes catalog value | Not a changing pixel measurement | Synthesized from card database after ID | Lookup | Semantic and noise mismatch plus duplicate token/card-stat embedding. **DROP from row** in next model or derive inside model artifact; do not query externally. |
| 24 | `attack_range` | Exact simulator runtime value, confidence `.85`; video converter substitutes catalog value | Not directly measured per frame | Synthesized after ID | Lookup | Same: **DROP from dynamic row** or generate internally. |
| 25 | `sight_range` | Exact simulator runtime value, confidence `.85`; video converter substitutes catalog value | Not directly measured per frame | Synthesized after ID | Lookup | Same. |
| 26 | `collision_radius` | Exact simulator/static value, confidence `.85` | Artwork box is not hitbox | Synthesized after ID | Lookup | Same; never infer from detector bounding-box size. |
| 27 | `motion_x` | Exact **native facing**, sampled 36%, confidence `.60` | Current frame alone cannot measure; temporal vision gives displacement | Adjacent-frame displacement available | CF/MR | **Semantic mismatch. DROP/REDEFINE.** Train on observed displacement, or zero both domains for the first A/B. |
| 28 | `motion_y` | Exact native facing, sampled 36%, confidence `.60` | Temporal displacement | Adjacent-frame displacement available | CF/MR | Same critical mismatch. |
| 29 | `effect_progress` | Zero/confidence zero | Exact progress unavailable | Unavailable | MR | **KEEP ZERO**; onset + internal timer later. |
| 30 | `base_damage` | Exact simulator runtime damage, confidence `.85`; video converter substitutes catalog value | Not a changing pixel measurement | Synthesized after ID | Lookup | **DROP from dynamic row** or internalize; can diverge for buffs, spawned units, and projectile payloads. |
| 31 | `tower_active` | Zero/confidence zero | King activation is publicly visible but classifier absent | Not exported as entity feature | CF/MR | **KEEP ZERO** until a public activation event is gated. |

The exact simulator row construction is visible in
[structured_obs.py](/Users/sam/Desktop/code/clasher/src/clasher/rl/structured_obs.py:357).
The current YouTube converter writes detector centers, measured HP, static
lookups, and inter-frame displacement in
[tv_royale_replay.py](/Users/sam/Desktop/code/clasher/src/clasher/rl/tv_royale_replay.py:600).

## Own cards and confidence

| actor input | accepted training | live measurability | YouTube neutral availability | state | recommendation |
|---|---|---|---|---|---|
| four `hand_ids` | Exact simulator hand, always present, confidence 1.0 | Visible HUD classifier | Existing lower-player extraction; both-player neutral HUD is canary work, not yet quality-gated | CF | **Critical shift.** Inject slot dropout, swaps, grayscale/selection ambiguity, and unknown IDs from held-out confusion matrix. |
| visible `Next` ID | **Mixed lineage:** exact simulator queue head with confidence 1 during earlier exact-simulator pretraining; ID `0` and confidence `0` on every row of the inspected 12,288-row `mix_oracle3_12k_public_v2.npz` rehearsal sidecar | Visible small Next icon | New baseline exists, but the inspected published sidecar has zero Next coverage | CF | Not “always exact.” The risk is inconsistent semantics and missingness across stages. Either reach high recall/calibration first or train with explicit, versioned empirical Next dropout. Do not backfill future evidence into live inputs. |
| `hand_id_confidence` | Current four slots are exact/confidence 1 in simulator degradation. Next was 1 in early exact-sim rows and 0 in the inspected causal sidecar | Raw template/classifier score should vary | Raw scores exist in newer HUD code but published sidecars promoted accepted current-hand IDs to 1 | CF | The accepted card-confidence residual final layer is exactly zero, so confidence currently has no policy effect. Still calibrate before enabling; identity errors remain harmful. |
| internal card stats/semantics | Exact semantic-v3 table embedded in checkpoint plus learned ID embedding | No external lookup needed after export | Available during offline tokenization | model weights | **KEEP.** This is the correct place for memorized cost/range/role similarity. Remove duplicate per-entity static inputs. |

The exact simulator builder exports hand plus queue head
[structured_obs.py](/Users/sam/Desktop/code/clasher/src/clasher/rl/structured_obs.py:501).
Current degradation code now preserves all five with confidence one
[public_observation.py](/Users/sam/Desktop/code/clasher/src/clasher/rl/public_observation.py:412),
but that is not a faithful description of every historical training stage.
Direct inspection found:

- base `mix_oracle3_12k.npz`: slot 4 nonzero on 12,288/12,288 rows;
- causal `mix_oracle3_12k_public_v2.npz`: slot 4 ID and confidence both zero on
  12,288/12,288 rows.

The initial audit also found a live-contract inconsistency: the general
real-play validator permitted five public visible slots (four hand plus Next),
while `load_public_observation_sidecar()` rejected nonzero slot four.  That
loader was corrected concurrently in the shared tree to use
`VISIBLE_CARD_SLOTS`; the focused audit test now proves the same public Next row
passes both boundaries.  This source fix does **not** retroactively add Next
labels to old schema-v2 artifacts.  Their zero ID/confidence remains missing
supervision and must remain so in manifests and training statistics.

## Global table and confidence channels

The structured policy explicitly zeros global channels 0–4 and their
confidences before actor encoding
[model.py](/Users/sam/Desktop/code/clasher/src/clasher/rl/model.py:1788).
They are therefore listed for schema completeness but are inert in this
accepted artifact.

| # | actor global | accepted simulator-training source | live measurability | current YouTube neutral source | state | shift/leakage judgment and recommendation |
|---:|---|---|---|---|---|---|
| 0 | `battle_progress` | Exact simulator time, confidence 1; then zeroed | Public clock OCR possible | Current converter uses source frame index; true OCR missing | MR | Encoder-inert. Structured cell uses its own fixed decision counter. **KEEP zeroed** until OCR synchronization is trained with dropout/jitter. |
| 1 | `battle_remaining` | Exact simulator value, then zeroed | Public clock | Frame-index proxy | MR | Same. |
| 2 | `double_elixir` | Exact phase, then zeroed | Public clock-derived | Frame-index proxy | MR | Same. |
| 3 | `triple_elixir` | Exact phase, then zeroed | Public clock-derived | Frame-index proxy | MR | Same. |
| 4 | `overtime` | Exact phase, then zeroed | Public clock-derived | Frame-index proxy | MR | Same. |
| 5 | `own_elixir` | Exact simulator value, confidence 1.0 | Visible HUD OCR/bar | Available for legacy lower HUD; raw confidence currently promoted to 1 | CF | **Critical shift. RANDOMIZE** quantization/OCR error/dropout; preserve raw calibrated confidence. |
| 6 | `own_crowns` | Zero/confidence zero | Publicly visible | Not exported | CF | **KEEP ZERO** until current-frame extraction is reliable. |
| 7 | `enemy_crowns` | Zero/confidence zero | Publicly visible | Not exported | CF | **KEEP ZERO**. |
| 8 | `own_left_tower_hp` | Exact fraction, independent 66% keep, no noise, confidence `.69` | Bar/OCR measurement | Implemented | CF | **RANDOMIZE** correlated visibility, bar bias, OCR error, and tower-type effects. |
| 9 | `own_right_tower_hp` | Same | Same | Implemented | CF | Same. |
| 10 | `own_king_tower_hp` | Same | Same | Implemented | CF | Same. |
| 11 | `enemy_left_tower_hp` | Same | Same | Implemented | CF | Same; also changes public deploy-zone mask on destruction. |
| 12 | `enemy_right_tower_hp` | Same | Same | Implemented | CF | Same. |
| 13 | `enemy_king_tower_hp` | Same | Same | Implemented | CF | Same. |
| 14 | `champion_cooldown` | Zero/confidence zero | Own ability UI could expose readiness, not exact clock | Unavailable | CF/MR | **KEEP ZERO**; exact simulator cooldown would leak. |
| 15 | `champion_duration` | Zero/confidence zero | Visual ability state/onset possible | Unavailable | MR | **KEEP ZERO**. |
| 16 | `next_card_refill` | Zero/confidence zero | Exact internal refill clock not directly displayed | Unavailable | MR | **KEEP ZERO**. |
| 17 | `enemy_king_alive` | Zero/confidence zero in accepted degradation | Publicly visible | Converter can infer from detected tower | CF | **Do not turn on for this checkpoint.** Retrain with noisy detection or rely on tower HP. |

## Other actor inputs

| input | accepted training source | deployability | risk and recommendation |
|---|---|---|---|
| `action_mask` | Rebuilt from degraded public hand/elixir/towers/building centers, not `BattleState` | Can be rebuilt from current own HUD and arena | Public, but still distribution-shifted. The `.99` direct-hand-confidence threshold means honest sub-.99 vision confidence can force no-op. Separate confirmed-current-slot validity from calibrated probability; train on mask errors and prove expert-label independence. |
| `previous_actions` | Actor's own prior selected action and tile | Always known to controller/model | **KEEP**, preferably fold into exported recurrent state so inference does not require an external history accumulator. |
| `previous_rewards` | Environment reward exists in rollout storage but is forcibly zero for causal actor | Not observable | Correctly blocked; **KEEP ZERO**. |
| `episode_starts` | Exact environment reset | Controller knows match boundary | **KEEP** as reset signal; test false/missed resets in live controller. |
| recurrent clock | Structured-cell channel increments exactly `1/750` per decision | Model-owned | **KEEP**, but only exact if inference cadence matches training. Sync to public clock with noise/dropout in successor model. |
| learned opponent elixir | Learned from encoded observations; reported live MAE/correlation weak | Model-owned | Policy gate is exactly zero, so policy sees constant one. **KEEP gated off** until deterministic event-driven tracker passes held-out replay. |
| opponent history/seen cards | Width zero in accepted config | Not required | No current leakage in accepted checkpoint. Future version must consume current-frame play events and accumulate internally. |
| opponent play-event input | Not present/used by accepted config | Current detector not yet quality-gated | Add only with precision/recall/duplicate/timestamp gate; no simulator history arrays. |
| exact critic tensors | Exact Markov state during learner training only | Never deployed to actor | Legitimate asymmetric critic. Add actor/critic byte-boundary tests so sidecar overlays cannot inherit critic or exact masks. |

The public action-mask implementation and its strict hand-confidence rule are in
[public_action_mask.py](/Users/sam/Desktop/code/clasher/src/clasher/rl/public_action_mask.py:45).
Previous reward is explicitly erased at the actor boundary
[model.py](/Users/sam/Desktop/code/clasher/src/clasher/rl/model.py:1866).

## Confidence semantics: confirmed deployment shift

The checkpoint does not merely carry confidence arrays—it learned to use some
of them:

- entity-confidence projection final weight norm: `1.363636`, bias norm
  `0.086327`;
- global-confidence projection final weight norm: `0.950222`, bias norm
  `0.070181`;
- hand/card-confidence final weight and bias are exactly zero.

Thus replacing fixed simulator constants with raw live scores can change entity
and global tokens immediately.  Training confidence currently acts partly as a
feature-type code: `.85` means identity/position/static, `.69` means HP, `.60`
means facing/motion, and `0` means missing.  Live confidence instead mixes model
score, association geometry, template margin, and visibility.  Those numbers
are not calibrated to the same event.

Recommendation:

1. define confidence as estimated probability that the emitted value is within
   a named tolerance, separately for identity, position, HP, and HUD fields;
2. calibrate on held-out human labels;
3. sample simulator confidence from those empirical conditional distributions;
4. corrupt values and confidences jointly, including overconfident errors;
5. retain explicit zero-confidence/zero-value missingness; and
6. compare a confidence-disabled A/B, because bad confidence can be worse than
   no confidence.

## Minimal A/B ladder before further training

### Gate A — accepted checkpoint corruption sensitivity, no training

On a fixed held-out simulator state/recurrent corpus, apply one corruption at a
time and report paired action-type KL, full-action KL, top-action flip rate, and
value drift:

1. zero `motion_x/y`;
2. replace exact facing with causal observed displacement;
3. vary Next across its actual mixed lineage and empirical live missing/error
   rate rather than assuming either always-present or always-missing;
4. apply entity FN/FP/identity confusion and position jitter;
5. add empirical HP/tower-HP noise plus correlated missingness;
6. replace fixed confidence constants with held-out measured confidence;
7. drop duplicated static entity channels 23–26 and 30; and
8. perturb own elixir/hand IDs within measured OCR/template errors.

This should run before any weight update.  It identifies which mismatches are
actually load-bearing in the accepted model.

### Gate B — three small fresh/rehearsal candidates

Train the same bounded imitation/rehearsal budget and seed set:

- **B0 control:** current degradation;
- **B1 semantic alignment:** zero motion, empirical Next/HP/tower dropout and
  noise, entity detection corruptions, continuous calibrated confidence;
- **B2 simplified:** B1 plus remove duplicated static entity channels and
  confidence residuals.

Do not bundle deterministic opponent elixir/cycle yet; isolate observation
equivalence first.

### Promotion gates

1. held-out manually labeled vision: identity/team precision-recall, position
   error, HP/tower MAE and coverage, hand/Next accuracy, elixir MAE, confidence
   calibration error;
2. train/live tensor audit: feature-wise value/confidence histograms and
   missingness co-occurrence, split by card class and arena;
3. held-out human replay: action-type/card/placement/timing metrics without
   simulator fields or future labels;
4. paired gameplay: strategy roster plus held-out decks, no card-usage collapse;
5. visual recording inspection; and
6. only after these, a longer diversified RL run.

The smallest likely useful change is **not** a larger architecture.  It is B1:
make training observations statistically and semantically resemble the values
the deployed vision system can actually produce.
