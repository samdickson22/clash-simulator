# Structured internal-state policy, 2026-08-14

## Decision

Promote the type-only causal-oracle challenger as the current research parent:
`checkpoints/fresh_structured_causal_v1_seed1062701/slowpush_oracle_type_seed1063206/type_e3.pt`,
SHA-256 `f52d55189bee4f095b7861cd4d16185a3c86be84b89f4f0251baf3e339b08aad`.
It replaces the dense
LSTM with a model-owned decision clock, a bounded internal resource belief, and
independent input-driven leaky state channels. Inference receives only the
current causal frame and the model's prior private state. It receives no exact
external match clock, opponent elixir, reward, or simulator history.

This is a promising research parent, not a mid-ladder or human-level promotion.
The first diverse-league PPO continuation did not beat the clean imitation
parent and is rejected. A later type-only oracle repair passed two independent
strategy blocks and the held-out-archetype preservation gate.

## Architecture and causal boundary

- Structured checkpoint: `checkpoints/fresh_structured_causal_v1_seed1062701/structured_e3.pt`
- SHA-256: `83481eaf1a6cad76b6417c86a0238fbdcfb1e0683892bdfd71e67f9854337f1a`
- Total parameters: 1,536,446
- Persistent-state parameters: 8,250
- Persistent state: 64 channels
- Dense LSTM/GRU modules: zero
- Actor domain: `causal-frame-v1`
- Deterministic clock channel: state channel zero
- Resource-belief channel: state channel one
- Remaining channels: independent learned-timescale accumulators, with no
  learned previous-state-to-candidate matrix

The matched LSTM has 2,351,751 total parameters and 526,336 LSTM parameters.
Its weights-identical causal-frame derivative is
`checkpoints/fresh_structured_causal_v1_seed1062701/lstm_causal_frame_e3.pt`,
SHA-256 `3f2840a1d9b95a4691698ffddfee18b7273a3c5bf8dc51037cb28afb3215fd63`.
Only the checkpoint observation-domain declaration differs from the source
LSTM; every model-state tensor was verified exactly equal.

## Offline recurrent comparison

The strict comparison used 128 complete held-out recurrent episodes, 19,586
samples, and identical seed 1062403. Full evidence is in
`reports/fresh_structured_causal_v1_seed1062701/recurrent_128ep_vs_lstm.json`.

| Metric | LSTM | Structured |
|---|---:|---:|
| Joint NLL | 0.6302 | **0.6256** |
| Action-type accuracy | **90.13%** | 89.01% |
| Play recall | 57.30% | **60.46%** |
| Played-card slot accuracy | 35.92% | **40.79%** |
| Placement within one tile | 19.88% | **35.79%** |
| Placement within two tiles | 25.22% | **40.23%** |

The structured core therefore traded about 1.1 percentage points of action
timing accuracy for lower total NLL and materially better card/placement
behavior.

## Live internal-state probe

The six-strategy live probe covered 2,064 policy decisions. The internal clock
was exact to floating-point accumulation error: correlation was effectively
1.0, MAE was `7.16e-7`, and RMSE was `1.06e-6`.

The first resource accumulator was not trained by imitation and remained at
full. A gradient-boundary correction plus ten PPO auxiliary updates reduced
held-out MAE from 0.843 to 0.253, but correlation remained only 0.074. Training
the whole 64-channel memory to update 30 worsened MAE to 0.529. A separate
learned frame-difference/event-comparator architecture also failed (correlation
approximately zero and worse imitation placement metrics). Both experimental
lineages are rejected, and the event-comparator option was removed from
production source.

This means the current structured policy has an exact useful internal clock,
but not an exact opponent-elixir estimator. The generic leaky state remains
useful to the policy; it must not be described as calibrated opponent elixir.

## Matched strategy gameplay

Protocol: four games per public-information strategy, paired seats, identical
decks and seeds beginning at 1063001, deterministic inference, objective-v1.

| Policy | W-L | Mean score | Mean crown diff/game |
|---|---:|---:|---:|
| Structured parent | **12-12** | **0.500** | -0.208 |
| Weights-identical LSTM on causal-frame | 2-22 | 0.083 | substantially negative |

The structured parent went 3-1 against bridge-pressure, 3-1 against
spell-control, 2-2 against split-lane, 3-1 against balanced, 1-3 against
reactive-defense, and 0-4 against slow-push. This is the strongest direct
evidence for selecting it over the LSTM, but four games per matchup is still a
screen rather than a skill estimate.

Reports:

- `reports/fresh_structured_causal_v1_seed1062701/strategy_screen_4x6.json`
- `reports/fresh_structured_causal_v1_seed1062701/lstm_causal_frame_strategy_screen_4x6.json`

## Diverse-league PPO result

The bounded pilot used the 1,720-deck card-balanced training pool, all six
strategy bots plus random, 28 environments, seven CPU actors, an MPS learner,
35,840 transitions, LR `1e-5`, objective-v1, and a 0.1 frozen-parent policy-KL
anchor. Update 20 ended stably (anchor KL 0.00469, clip fraction 0.004) but
stability did not imply improvement.

| Checkpoint | W-L | Mean score | Mean crown diff/game | Mean defensive action rate |
|---|---:|---:|---:|---:|
| Parent | **12-12** | **0.500** | -0.208 | 0.066 |
| Update 10 | **12-12** | **0.500** | **-0.125** | 0.078 |
| Update 20 | 9-15 | 0.375 | **-0.125** | **0.081** |

Update 10 improved balanced from 3-1 to 4-0 and raised defensive response, but
regressed bridge-pressure from 3-1 to 2-2 and remained 0-4 against slow-push.
Update 20 won one slow-push game but broadly regressed. Neither is promoted.

## Causal-oracle type repair and promotion

A 4,096-state corpus was collected from structured-parent games against
slow-push over the 1,720-deck training pool. A depth-2/four-simulation planner
provided causal expert actions while the behavior policy continued to own the
visited state distribution. The public sidecar retained the real-play
confidence contract. Full spatial imitation failed because 762 supervised
placements were insufficient to learn the planner's locations; that arm
remained 0-4 against slow-push and is rejected.

The successful arm trained only the existing six-way action-type head for
three epochs at LR `5e-5`. All encoders, structured state, card queries, and
placement weights remained frozen.

On the first four-game-per-strategy block, the challenger improved 12-12 to
13-11, slow-push 0-4 to 1-3, mean crown differential -0.208 to +0.125, and mean
defensive action rate 0.066 to 0.081. On a completely new seed block, it
improved 7-17 to 10-14 while matching or improving every individual matchup.
Combined over 48 matched games, the parent scored 19-29 and the challenger
23-25.

On 128 full held-out human-replay episodes, play recall improved 60.46% to
65.73% and played-card slot accuracy improved 40.79% to 43.74%. The cost was a
small action-type accuracy drop from 89.01% to 88.70%, exact accuracy from
86.01% to 85.45%, and worse calibration. Placement accuracy was effectively
unchanged.

On eight whole-archetype held-out games against balanced, both policies scored
5-3 from the same seats and seeds. The challenger improved crown differential
from +0.25 to +0.50. This preserves the frozen generalization gate but is too
small to estimate human skill.

Evidence:

- `reports/fresh_structured_causal_v1_seed1062701/slowpush_oracle_type_e3_strategy_screen_4x6.json`
- `reports/fresh_structured_causal_v1_seed1062701/slowpush_oracle_type_e3_confirm_seed1064001_4x6.json`
- `reports/fresh_structured_causal_v1_seed1062701/slowpush_type_vs_parent_recurrent_128ep.json`
- `reports/fresh_structured_causal_v1_seed1062701/slowpush_type_heldout_balanced8_seed1065001.json`
- `reports/fresh_structured_causal_v1_seed1062701/parent_heldout_balanced8_seed1065001.json`

## Reactive-defense causal repair and second promotion

A second independent 4,096-state causal corpus was collected from the promoted
slow-push repair against reactive-defense. As in the first successful repair,
only the six-way action-type head was trained for three epochs at LR `5e-5`;
the structured state, encoders, placement policy, and value function remained
frozen.

The challenger improved on both frozen strategy blocks. Across 48 matched games
the slow-push-repair parent scored 23-25, while the reactive-repair challenger
scored **27-21**. It preserved the reactive-defense score at 3-5 and improved
slow-push from 4-4 to 5-3, balanced from 3-5 to 7-1, and aggregate crown
differential. Spell-control fell from 6-2 to 5-3, so this is not a monotonic
matchup improvement.

On 128 complete held-out human-replay episodes, play recall improved from
65.73% to **70.50%** and played-card slot accuracy from 43.74% to **47.00%**.
The cost was action-type accuracy falling from 88.70% to 88.49%, exact accuracy
from 85.45% to 84.97%, and worse likelihood/calibration. This is a measured
aggression-versus-calibration tradeoff rather than a clean imitation win.

On the frozen 582-deck whole-archetype holdout against balanced, the challenger
scored **6-2** with +0.75 crowns/game, versus the promoted parent's 5-3 with
+0.50 crowns/game. It therefore passes the held-out generalization gate and is
promoted as the current research parent:

`checkpoints/fresh_structured_causal_v1_seed1062701/reactive_oracle_type_seed1063303/type_e3.pt`

This promotion does not establish human or mid-ladder skill. Its evidence is
48 matched roster games, 128 held-out replay episodes, and eight held-out-deck
games.

Evidence:

- `reports/fresh_structured_causal_v1_seed1062701/reactive_oracle_type_e3_strategy_screen_4x6.json`
- `reports/fresh_structured_causal_v1_seed1062701/reactive_oracle_type_e3_confirm_seed1064001_4x6.json`
- `reports/fresh_structured_causal_v1_seed1062701/reactive_type_vs_slowpush_type_recurrent_128ep.json`
- `reports/fresh_structured_causal_v1_seed1062701/reactive_type_heldout_balanced8_seed1065001.json`

## Next evidence-backed move

Continue from the promoted reactive-repair parent, but stop stacking narrow
single-corpus repairs without replay. The next bounded experiment should train
the same small action-type scope on a balanced mixture of the slow-push,
reactive-defense, and a new weak-matchup causal corpus, plus a human-replay
retention term. This directly tests whether the gameplay gains can accumulate
without the observed likelihood/calibration drift. The two frozen roster
blocks, recurrent human replay, and whole-archetype held-out decks remain hard
promotion gates. More undirected PPO on the same objective is not justified.

## Three-corpus rehearsal repair and third promotion

A third 4,096-state causal corpus was collected against split-lane using the
same depth-2/four-simulation planner, interval-eight timeline, 1,720-deck pool,
and confidence-aware public observation contract. The slow-push,
reactive-defense, and split-lane corpora were then combined by complete episode
into a balanced 12,288-state, 48-episode rehearsal set.

Directly mixing the human replay corpus was rejected fail-closed because it
uses a different observation interval; forcing it into the same recurrent
sequences would give the model-owned clock contradictory step semantics.
Instead, the frozen parent KL remained the retention term and complete human
replay stayed a hard external gate.

Two arms were tested:

- A conservative one-epoch action-type-head update from the promoted parent at
  LR `2.5e-5` and parent KL `0.2`.
- A three-epoch consolidated fit from the original structured checkpoint at LR
  `5e-5` and parent KL `0.1`.

Both scored 9-3 in the rapid roster screen, but the consolidated arm learned an
unsafe planner-imitation shortcut: against reactive-defense it never waited
when any placement was legal. On a bounded recurrent replay check it reached
94.3% play recall by overplaying, with materially worse likelihood,
calibration, and conditional card choice. That lineage is rejected.

The conservative rehearsal arm cleared both frozen strategy blocks. Across 48
matched games it scored **30-18**, versus **27-21** for the promoted parent. It
preserved bridge-pressure at 4-4, slow-push at 5-3, and spell-control at 5-3;
improved reactive-defense from 3-5 to **4-4**, split-lane from 3-5 to **4-4**,
and balanced from 7-1 to **8-0**.

On 128 complete held-out human-replay episodes, play recall improved from
70.50% to **74.33%**, played-card slot accuracy from 47.00% to **49.79%**, and
conditional card choice improved slightly. Exact accuracy fell from 84.97% to
84.55%, action-type accuracy from 88.49% to 88.33%, and likelihood/calibration
worsened. The frozen whole-archetype holdout remained **6-2**; crown
differential moved from +0.75 to +0.625. The unchanged held-out record plus the
three-game roster gain passes the promotion rule, but the calibration and crown
tradeoffs are retained explicitly.

The current research parent is therefore:

`checkpoints/fresh_structured_causal_v1_seed1062701/oracle_mix_rehearsal_seed1063503/type_e1.pt`

Evidence:

- `reports/fresh_structured_causal_v1_seed1062701/mix_oracle3_12k_manifest.json`
- `reports/fresh_structured_causal_v1_seed1062701/oracle_mix_arms_recurrent_32ep.json`
- `reports/fresh_structured_causal_v1_seed1062701/oracle_mix_rehearsal_e1_strategy_screen_4x6.json`
- `reports/fresh_structured_causal_v1_seed1062701/oracle_mix_rehearsal_e1_confirm_seed1064001_4x6.json`
- `reports/fresh_structured_causal_v1_seed1062701/oracle_mix_rehearsal_vs_parent_recurrent_128ep.json`
- `reports/fresh_structured_causal_v1_seed1062701/oracle_mix_rehearsal_heldout_balanced8_seed1065001.json`

## Revised next move

Do not stack another global action-type repair immediately. The three-corpus
rehearsal improved every previously losing roster matchup without reopening
slow-push, but repeated type-head updates continue to worsen play calibration.
The next architecture experiment should target the still-uncalibrated
model-owned opponent-resource accumulator and measure whether a better internal
belief reduces timing errors without changing the action head. Any subsequent
policy repair should use calibrated mixed supervision or localized heads, not
another unconstrained shift of the global play/wait threshold.

## Decoupled model-owned resource belief

The promoted rehearsal parent still kept its opponent-resource channel exactly
at 1.0 on 2,122 live decisions (MAE 0.789, correlation 0), even though its
model-owned clock remained effectively exact. A bounded diverse-league fit was
therefore run with only 128 trainable parameters: the internal spend detector
and regen scalar. Update 10 was the best saved point. On the same parent
trajectories it reduced MAE to **0.266** and raised correlation to **0.064**.
Update 20 regressed to MAE 0.375/correlation 0.033 and is rejected; the planned
50-update schedule was stopped after the curve reversed.

Directly substituting the improved belief into the action network failed. Full
exposure scored 13-11 versus the parent’s 15-9 on the first roster block,
reopening bridge-pressure and balanced. This exposed an architecture bug: the
policy had learned while that channel was always one, so calibrated values were
out of distribution even though the estimator itself improved.

A zero-initialized internal policy gate now separates belief learning from
belief use. At gate zero the policy receives the legacy constant-one resource
input while the actual persistent estimate remains available for auxiliary
training and diagnostics. Across 32 complete recurrent episodes, the gate-zero
checkpoint produced **zero action changes** and bit-identical policy metrics
relative to the promoted parent.

Predeclared fixed gate exposures were then evaluated. A 25% gate fell from 9-3
to 8-4 in the rapid screen. A 50% gate matched 15-9 on the first full block but
fell to 13-11 on the independent block, producing 28-20 combined versus the
gate-zero parent’s 30-18. Full, half, and quarter exposure are all rejected.

The behavior-identical research successor is therefore:

`checkpoints/fresh_structured_causal_v1_seed1062701/resource_belief_gated_seed1063602/resource_u10_gate0.pt`

SHA-256:
`3353615954fdcfdb24f2ba570f1888cd6130242238391a9bcf98dcedbcfc5b88`

It is still not a calibrated card-counting model. It has a coarse, internally
tracked resource signal with no external elixir calculation, deliberately
disconnected from policy decisions until better held-out prediction evidence
exists.

Evidence:

- `reports/fresh_structured_causal_v1_seed1062701/oracle_mix_rehearsal_live_state_seed1063601.json`
- `reports/fresh_structured_causal_v1_seed1062701/resource_belief_gate0_live_state_seed1063601.json`
- `reports/fresh_structured_causal_v1_seed1062701/resource_gate0_parent_exact_recurrent_32ep.json`
- `reports/fresh_structured_causal_v1_seed1062701/resource_belief_gate25_strategy_screen_2x6.json`
- `reports/fresh_structured_causal_v1_seed1062701/resource_belief_gate50_strategy_screen_4x6.json`
- `reports/fresh_structured_causal_v1_seed1062701/resource_belief_gate50_confirm_seed1064001_4x6.json`
- `reports/fresh_structured_causal_v1_seed1062701/resource_belief_u10_strategy_screen_4x6.json`

## Current next move

Improve resource prediction before reopening the gate. The current 0.064 live
correlation is useful evidence that an internal estimator can learn, but far
below the standard needed to steer actions. The likely next experiment is an
event-sensitive internal update trained on longer diverse sequences, while
keeping the zero gate and the 30-18 policy frozen. Separately, future action
learning should use localized timing features rather than globally shifting the
six-way action head again.

## Rejected pooled event-delta estimator

A version-two resource estimator tested whether explicit before/after deltas in
the pooled recurrent input could improve the weak gate-zero belief. Two matched
10,083-parameter arms used 128-step diverse-league sequences: spend-only and
spend plus a bounded signed correction. Both remained behind gate zero, so
policy actions were frozen throughout training.

The apparent training improvements did not generalize to the frozen six-game
live probe:

| Estimator | Correlation | MAE | Prediction mean |
|---|---:|---:|---:|
| v1 gate-zero parent | **+0.064** | 0.266 | 0.155 |
| v2 spend update 20 | -0.021 | 0.284 | 0.217 |
| v2 spend update 30 | +0.043 | **0.218** | 0.061 |
| v2 correction update 20 | -0.154 | 0.317 | 0.421 |
| v2 correction update 30 | -0.024 | 0.225 | 0.338 |

The lower-MAE checkpoints achieved it through strongly biased low/high
predictions rather than better temporal tracking. None beat the parent’s live
correlation, so all four checkpoints are rejected. The version-two path and
its CLI surface were removed from production source instead of retaining dead
architecture.

Evidence:

- `reports/fresh_structured_causal_v1_seed1062701/resource_event_v2_spend_u20_live_state_seed1063601.json`
- `reports/fresh_structured_causal_v1_seed1062701/resource_event_v2_spend_u30_live_state_seed1063601.json`
- `reports/fresh_structured_causal_v1_seed1062701/resource_event_v2_correct_u20_live_state_seed1063601.json`
- `reports/fresh_structured_causal_v1_seed1062701/resource_event_v2_correct_u30_live_state_seed1063601.json`

## Revised resource direction

Do not add another generic pooled-frame delta MLP. The pooled actor context has
already discarded the cleanest causal signal: which visible enemy entity is in
the first frame of deployment. The next bounded resource experiment should use
a model-internal, permutation-invariant event head over current enemy entity
tokens gated by deployment state, infer one normalized spend per new event,
and feed that into the private accumulator behind gate zero. This remains an
internal neural calculation over vision-derived entity inputs; it does not
provide externally calculated elixir.

## Rejected deployment flag and entity-set trace

The current-frame deployment proposal was audited before training. Across six
frozen games and 178 actual opponent plays, `placement_pending`, remaining
deployment fraction, and effect progress were already zero at the next
eight-tick decision frame. The proposed mask detected zero events and had 0%
recall, so the path was removed without a training run.

A model-owned entity-multiset trace was then tested. Positive enemy-token count
changes recovered 137/178 plays (77% recall), but combat projectiles, spawns,
and deaths produced 483 false events (22% precision). A learned 64-dimensional
token trace and signed-delta head was trained behind gate zero on the same
128-step diverse league. It failed the frozen live probe:

| Estimator | Correlation | MAE | Prediction mean |
|---|---:|---:|---:|
| v1 gate-zero parent | **+0.064** | **0.266** | 0.155 |
| entity trace update 20 | -0.189 | 0.454 | 0.520 |
| entity trace update 30 | -0.125 | 0.394 | 0.464 |

The trace learned mildly positive within-game correlations but inverted
cross-matchup calibration and was worse on every aggregate selection metric.
Its production config, modules, CLI, and tests were removed. The checkpoint
artifacts remain only as rejected evidence inside the retained structured
lineage.

Evidence:

- `reports/fresh_structured_causal_v1_seed1062701/resource_entity_trace_u20_live_state_seed1063601.json`
- `reports/fresh_structured_causal_v1_seed1062701/resource_entity_trace_u30_live_state_seed1063601.json`

## Resource conclusion

At the current eight-tick visual decision cadence, the available entity frame
does not support a reliable model-owned opponent-elixir accumulator. Keep the
v1 estimate private at gate zero and stop spending policy-research cycles on
this auxiliary until the real vision pipeline supplies a directly observed
card-play event. That event may be extracted from pixels as an observation,
but no externally calculated elixir value should be supplied. Work now returns
to the actual skill bottlenecks: action timing, defense, matchup diversity, and
held-out human/generalization evidence.

## Rejected adapter-only timing pilot

A zero-initialized 1,158-parameter action-type adapter was trained with the
1.55M-parameter gate-zero base frozen. Twelve diverse league workers emphasized
bridge-pressure, reactive-defense, and split-lane; the interval-eight
three-oracle corpus supplied type rehearsal; live parent KL constrained drift.

On a 32-episode human replay screen, update 15 was the only viable checkpoint:
action-type accuracy improved 73.44% to 73.84%, play recall 85.14% to 88.65%,
and played-card slot accuracy 54.05% to 57.57%, with 30 changed decisions.
Updates 20/25/30 increasingly overplayed and lost replay accuracy/calibration,
so they were rejected before gameplay.

Update 15 then failed the frozen rapid roster at **8-4**, versus the parent’s
**9-3**. Reactive-defense regressed from 2-0 to 1-1; every other matchup record
was unchanged. The adapter lineage is rejected. This is further evidence that
small global play/wait shifts can improve imitation metrics while worsening
actual games.

Evidence:

- `reports/fresh_structured_causal_v1_seed1062701/timing_adapter_recurrent_32ep.json`
- `reports/fresh_structured_causal_v1_seed1062701/timing_adapter_u15_strategy_screen_2x6.json`

## Current research decision

Stop stacking global action-type repairs. The gate-zero rehearsal policy remains
the accepted behavior baseline. The next improvement must come from better
state/action data or a representation that localizes tactical corrections by
card, lane, and threat context, followed by the same replay, roster, and
held-out-deck gates.
