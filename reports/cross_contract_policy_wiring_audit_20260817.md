# Cross-contract policy wiring audit — 2026-08-17

## Decision

The accepted structured checkpoint is a valid **simulator research policy**, but
it is not yet an executable or train/live-equivalent vision policy.  The strict
live schema, current-frame cue schema, neutral spectator schema, causal replay
sidecars, simulator rollout path, and policy forward path are individually
reasonable pieces, but they do not currently form one connected contract.

Do not use the accepted checkpoint as the initializer for another long training
run.  Preserve it as a behavior benchmark.  First repair the causal-history
corpus and implement one typed current-frame-to-policy adapter; then compare the
clean lineage from the last pre-mix parent.

Pinned accepted artifact:

- `checkpoints/fresh_structured_causal_v1_seed1062701/resource_belief_gated_seed1063602/resource_u10_gate0.pt`
- SHA-256 `3353615954fdcfdb24f2ba570f1888cd6130242238391a9bcf98dcedbcfc5b88`
- 1,554,519 state-dict parameters
- actual `model_config`: confidence-aware `causal-frame-v1`, structured memory
  64, semantic-v3 hybrid cards, no public history or seen-card slots,
  deterministic public resource tracking disabled, resource-to-policy gate zero

This audit was read-only except for this report.  It ran no training or gameplay.

## Contract map

| Boundary | Actual implementation | What reaches the accepted policy |
|---|---|---|
| Exact simulator | `StructuredObservationBuilder.build()` emits actor-public tensors plus exact privileged critic tensors | Actor is degraded; critic remains exact during PPO/evaluation |
| `causal-vision-v1` | Synthetic degradation followed by a Python temporal tracker | Carried HP/HUD/towers, predicted tracks, derived displacement; not self-contained model state |
| `causal-frame-v1` | Synthetic degradation without the tracker | Exact simulator body identity/position, sampled exact HP, exact native facing mislabeled as motion, exact own hand/elixir; no visual card-play/status cue |
| Strict current-frame cues | `CurrentFramePublicSignals` has OCR clock, deployment, card-play, and combat cues | No adapter maps this object into `PolicyInputs`; cue fields are unreachable |
| Strict JSON live schema | `PublicVisionFrame` plus `LiveInferenceAdapter` protocol | No production implementation exists; only a synthetic counter adapter exists in tests |
| Neutral dual-HUD replay | Readiness schema plus `project_neutral_snapshot()` | No neutral structured snapshot has been decoded; no projection-to-policy tensor adapter exists |
| Accepted policy | Requires observation/confidence tensors, action mask, previous own action, reset, and optional event tensors | Current actor tensors work in the simulator; clock/event/live mask/controller semantics are incomplete |

## Hard blockers

### C1. The production live adapter does not exist

`src/clasher/rl/live_inference_contract.py:262-267` defines only a protocol.
Repository search finds no implementation outside the synthetic
`_InternalCounterAdapter` in `tests/test_rl_live_inference_contract.py`.
Consequently there is no authoritative code that:

- converts card strings and current entities into accepted token tensors;
- maps absolute coordinates into the acting player's canonical perspective;
- generates the public action mask without accepting an exact mask as input;
- maps current clock and card-play cues into the recurrent policy state;
- retains the policy state and its own previous selected action;
- distinguishes requested from visibly confirmed plays; or
- enforces the training decision cadence under dropped/duplicate camera frames.

**Smallest discriminating test.** Implement a minimal adapter for a frozen JSONL
trace generated from simulator truth projected into only the live schema. Run
the same sequence through (a) the adapter and (b) the direct causal-frame policy
path. Compare every `PolicyInputs` tensor, recurrent state digest, legal mask,
and action distribution at every decision.

**Promotion gate.** Zero unexplained tensor/state/action-mask differences on at
least 100 complete fixed-seed episodes, both seats, including regulation,
overtime, reset, missing OCR, a repeated visible event, and a dropped frame.
The adapter process import graph must not include `clasher.battle`.

**Reject if** the adapter needs an exact legal mask, opponent private HUD, future
frame, simulator history, externally accumulated cycle/elixir, or an unversioned
timing assumption.

### C2. Current-frame clock and play/combat cues are unreachable

`CurrentFramePublicSignals` defines clock, deployment, card-play, and combat
cues (`src/clasher/rl/causal_vision.py:138-151`).  No production caller constructs
the object, and none of those cue objects appears in `PolicyInputs`.

The only event tensors in `PolicyInputs` are one opponent card ID and confidence
(`src/clasher/rl/model.py:186-187`). They affect memory only when
`structured_deterministic_resource_enabled` is true
(`src/clasher/rl/model.py:1370-1380`). It is false in the accepted checkpoint.
The accepted config also has `public_history_slots=0`, so the simulator adapter
`_current_opponent_play_events()` sees an empty array and emits zero on every
step (`src/clasher/rl/train_recurrent.py:599-623`).

The accepted structured forward path explicitly zeros public clock/phase
globals 0–4 before encoding (`src/clasher/rl/model.py:1788-1807`) and advances
its private clock by exactly `1/750` per policy call
(`src/clasher/rl/structured_memory.py:349-352`). OCR clock values therefore
cannot influence this checkpoint. Its clock is correct only if inference calls
arrive at the exact training cadence (eight game ticks, about 0.4 seconds).

Combat/status strings in `PublicVisionFrame`, and `CurrentFrameCombatCue`, have
no mapping to the accepted 32-feature actor row or internal timers. Newly added
vision classifiers cannot affect this checkpoint without an architecture and
training change.

**Smallest A/B.** From the same clean parent, train (A) fixed-step clock only and
(B) current OCR clock with confidence plus fallback step clock. Separately add a
single typed opponent-play event and event latch behind a policy gate; do not
bundle statuses or resource exposure.

**Promotion gate.** Public clock MAE at most 1.0 second under cadence jitter and
frame drop; duplicate events produce exactly one internal pulse; opponent cycle
counter accuracy at least 95%; event-driven opponent-elixir MAE at most 0.5
before its policy gate can open. Behavior at a zero policy gate must remain bit
identical to the clean parent.

**Reject if** OCR loss makes the internal clock go backward, a repeated marker
charges spend twice, or any event tensor is derived from simulator history at
deployment.

### C3. `causal-frame-v1` is not the strict current-frame sensor domain

Accepted training sidecars contain `motion_x/y` on 278,582 of 1,270,010 visible
entities (21.93%). Simulator row channels 27–28 are exact `native_facing_units`
(`src/clasher/rl/structured_obs.py:410-416`), while the replay converter uses
inter-frame body displacement (`src/clasher/rl/tv_royale_replay.py:641-654`).
Strict `CurrentFramePublicSignals` correctly rejects externally tracked motion
(`src/clasher/rl/causal_vision.py:167-170`). These three meanings are not
equivalent.

`causal-frame-v1` also retains every eligible simulator entity, exact identity
and position, exact own hand/elixir, and exact HP/tower HP when sampled. Its
profile has zero position and HP noise. This is a simulator corruption model,
not a measured-camera distribution.

**Smallest A/B.** Run the already specified corruption sensitivity screen, with
motion zeroed versus measured displacement as separate arms. Then fit matched
small controls: current synthetic degradation; empirical detector corruption;
empirical corruption with motion removed and duplicated static row features
removed.

**Promotion gate.** Held-out value/confidence/missingness histograms by field,
card class, crowd level, arena, and team must match the vision validation set;
paired action-type/full-action KL and top-action flips must not reveal a new
single-feature dependency; gameplay must clear both strategy blocks and held-out
decks with no card-usage collapse.

**Reject if** camera errors are modeled only as independent dropout or live
confidence scores are fed into a checkpoint trained on fixed semantic constants.

### C4. The accepted lineage has causally false previous-action history

The accepted checkpoint descends from
`oracle_mix_rehearsal_seed1063503/type_e1.pt`, trained on
`datasets/derived/structured_oracle_mix_seed1063501/mix_oracle3_12k.npz`.
That historical mixed corpus replaced the actual behavior action that generated
the next state with the previous oracle/expert label. The corrected combiner now
preserves source behavior (`src/clasher/rl/imitation_mix.py:237-250`).

A direct old/new artifact comparison found exactly 2,112 of 12,288
`previous_actions` rows changed (17.1875%) and no other training array changed
apart from metadata. Corrected artifact:

- `mix_oracle3_12k_causal_v2.npz`
- SHA-256 `690dc0929420a6bcdb8a6f80cfa7ccbdc17d6f3036f82935c7d8e10008695316`

Because previous action is embedded into recurrent input
(`src/clasher/rl/model.py:1311-1330`), the old examples ask the model to explain
a state using an action that often did not produce it.

**Smallest A/B.** From the same pre-mix `structured_e3.pt`, fit identical
old-history and preserved-history one-epoch action-type arms. Do not continue
either from the accepted gate-zero descendant.

**Promotion gate.** Exact recurrent replay must reproduce source previous
actions and state chronology on every row. The clean arm must match or improve
joint/type NLL, play Brier/ECE, both frozen 24-game strategy blocks, and held-out
deck score. Independent of win rate, only the clean-history arm is eligible as a
future parent.

**Reject if** a combiner derives previous actions from labels rather than source
behavior or joins corpora with unequal decision intervals into one recurrent
sequence.

### C5. Next-card vision is new, but the accepted policy was never trained on it

The actor encoder has capacity for five visible card tokens. Nevertheless,
every inspected public sidecar in `datasets/derived`, including the 121,917-row
accepted pretraining sidecar and the 12,288-row oracle mix, has zero ID and zero
confidence in slot 4. Thus the accepted model never trained the fifth token as
Next. Its card-confidence residual output is also exactly zero, so hand/Next
confidence cannot change behavior.

There is a second hard inconsistency: `validate_real_play_feature_contract()`
accepts hand plus public Next (`src/clasher/rl/public_observation.py:314-318`), but
`load_public_observation_sidecar()` rejects any nonzero slot beyond the first
four as a hidden future card (`src/clasher/rl/imitation.py:709-719`). A new
vision sidecar with valid Next cannot enter the imitation path.

**Smallest A/B.** First add a contract test that slot 4 is public Next while slot
5 is rejected. Then train equal-budget clean arms with Next always zero versus
empirically dropped/calibrated Next. Start from a fresh or pre-Next parent; do not
turn Next on post hoc in the accepted checkpoint.

**Promotion gate.** On held-out manually labeled HUD frames, report confident
subset accuracy, coverage, NLL/Brier, and ECE; then require the Next arm to
improve recurrent action/card likelihood or gameplay without worsening the same
metrics when Next is missing or wrong. No future-refill label may enter runtime
input.

**Reject if** offline future frames backfill runtime Next, or the model performs
worse than the zero-Next arm under the measured confusion matrix.

### C6. Public masks are not yet a label-independent live contract

The policy requires an action mask and hard-masks logits
(`src/clasher/rl/model.py:1485-1510`). The live JSON parser correctly forbids an
incoming exact mask, but there is no production adapter that builds one.
`PublicActionMaskBuilder` uses public observations, yet it also depends on a
runtime card catalog/spell registry and disables any hand slot whose raw
identity confidence is below `.99` (`src/clasher/rl/public_action_mask.py:147-220`).
Honest calibrated classifier confidence need not reach `.99`, so a readable
hand can collapse to forced no-op.

Sidecar loading is fail-open: if `action_masks` is absent, the base corpus mask
survives (`src/clasher/rl/imitation.py:686-687,780-781`). The three published
77-row causal validation sidecars inspected here omit `action_masks`, so pairing
them with a simulator corpus can silently restore exact legality.

Sidecar builders also force the expert action legal when the public mask rejects
it (`scripts/build_public_observation_sidecar.py:142-149` and
`scripts/extract_tv_royale_raw_cascade.py:276-284`). This affected 2,277 of
121,917 accepted pretraining rows and 230 of 12,288 mixed-oracle rows. The
resulting policy mask is label-conditioned; in narrow masks it can reveal the
target.

**Smallest A/B.** Make masks mandatory for every causal sidecar and change only
the expert label while holding observation fixed; the policy mask must remain
byte-identical. Compare dropping masked demonstrations versus a loss-only
type/slot rescue that never enters `PolicyInputs`.

**Promotion gate.** Zero exact-mask fallbacks; zero mask changes under label
counterfactuals; zero false-legal actions on the frozen exact oracle audit;
retain at least the prior 90.90% aggregate legal-choice coverage; and less than
1% no-op-only states when the current four-card hand and elixir are accepted by
the sensor contract.

**Reject if** any policy-input bit depends on the expert label, or a raw
uncalibrated score is used as an exact legality decision.

### C7. Actor/critic separation is action-safe, but live value is uncalibrated

Exact critic entities, both hands/Next cards, exact globals, opponent elixir,
and refill cooldown remain in `StructuredObservation` during causal PPO. They
enter only the separate critic encoder and value head
(`src/clasher/rl/model.py:2195-2207`). A fixed initial-state probe confirmed that
removing all critic tensors left accepted-policy joint logits bit-identical.
This is valid asymmetric-critic training, not actor leakage.

However, when critic tensors are absent, `forward()` applies the same value head
to `actor_global` (`src/clasher/rl/model.py:2208-2209`). That actor embedding is
not the representation on which PPO trained the value function. In the bounded
probe, critic value was `0.0618174`, actor fallback `0.0689716`; the small single
state delta does not establish calibration. Real-play search must not assume the
fallback is trained merely because it returns a number.

**Smallest A/B.** Evaluate frozen actor-fallback and a separately trained
public-value head on the same held-out public trajectories. Keep policy weights
fixed.

**Promotion gate.** Public-value head must beat a constant outcome baseline by
at least 5% Brier score, have positive explained variance, ECE at most 0.05, and
improve paired actor-only search games without privileged state. Otherwise do
not expose value-guided live search.

**Reject if** real-play inference/search imports exact critic tensors or calls a
simulator-based value/lookahead path.

## Spectator neutral-state findings

The privacy direction is sound: `project_neutral_snapshot()` copies the public
absolute-world record plus only the chosen player's private HUD and excludes the
other player's fields (`scripts/audit_tv_royale_youtube_portrait.py:288-374`).
Counterfactual tests verify that changing player 1's private HUD cannot change
player 0's projection.

It is still readiness scaffolding, not training data:

- the manifest records zero decoded neutral structured snapshots and zero ready
  actor examples (`scripts/audit_tv_royale_youtube_portrait.py:1022-1030`);
- actor projections deliberately remain `absolute_world`; documented later
  canonicalization has no implemented JSON-to-policy adapter;
- the offline projection requires a complete four-card hand, Next, elixir, and
  strictly positive confidence for every field, whereas the live schema and
  confidence-aware policy can represent missing values; this will select only
  unusually clean HUD frames unless relaxed; and
- `perspective_sanitizer.py` supports only the bottom live perspective, which is
  appropriate for actual local play but cannot by itself produce the top actor
  training view.

**Promotion gate.** For each neutral snapshot, materialize two actor tensors,
canonicalize both numerically (never by flipping the raw image), keep both in
the same split group, and prove: opponent-private counterfactual invariance,
180-degree public/action equivariance, valid own hand/Next/elixir missingness,
and no raw/top-HUD pixels in either actor artifact.

## Correct parts to preserve

- The actor tensor excludes opponent hand/elixir and invisible enemy objects;
  the critic is structurally separate.
- Causal domains force previous shaped reward to zero at the model boundary
  (`src/clasher/rl/model.py:1866-1874`).
- Missing numeric values must be zero with zero confidence, preventing
  neutral-looking fabricated truth.
- The live parser recursively rejects exact masks, simulator state, critic
  state, opponent private fields, RNG, object/target IDs, and exact clocks.
- The resource-policy gate is exactly zero, so the weak learned opponent-elixir
  estimate cannot currently steer accepted actions.
- Neutral actor projection excludes the other player's private HUD by
  construction and preserves replay-level split grouping.

## Ranked next work

1. **Quarantine the accepted lineage as a benchmark.** Retrain the smallest
   old-versus-clean previous-action A/B from `structured_e3.pt`.
2. **Implement one production `PublicVisionFrame -> PolicyInputs` adapter** with
   explicit cadence, canonicalization, reset, action-mask, and model-state
   ownership. Until this exists, “live policy” claims are not testable.
3. **Make causal masks mandatory and label-independent.** Remove exact fallback
   and expert-action mutation from policy inputs.
4. **Run the no-training observation corruption screen.** Prioritize entity
   detection, HP, facing/displacement, hand/elixir, and confidence semantics.
5. **Repair and A/B the Next contract.** Accept slot 4 through the loader, then
   train with empirical missingness rather than activating it post hoc.
6. **Add clock/event channels only behind zero behavior gates.** Prove held-out
   clock, event deduplication, cycle, and elixir metrics before policy exposure.
7. **Train a public value head only if actor-only lookahead remains planned.**
8. **Decode neutral structured snapshots and both actor projections** only after
   the adapter contract is frozen, so the dataset cannot drift into a different
   tensor semantics.

## Rejection rule for future checkpoints

A checkpoint is not a real-play candidate merely because its config says
`causal-frame-v1`. Reject promotion unless its manifest pins:

- the exact live input schema and adapter hash;
- detector/token/card-buffer hashes and calibrated confidence definition;
- inference cadence and reset semantics;
- mandatory public-mask origin with no label dependence;
- per-feature train/live distribution evidence;
- clean source behavior history for every recurrent row;
- actor-only evaluation with no critic tensors; and
- paired gameplay plus held-out chronology/decks after all contract gates pass.
