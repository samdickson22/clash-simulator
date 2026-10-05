# Clasher model and pipeline architecture decision registry — 2026-08-17

This is a living, evidence-bound audit of choices on the path to a policy that
can play a mid-ladder human.  A green offline metric, invariant test, or
simulator matrix cannot promote a model without matched complete-game evidence.

## A1. Action representation

**Current design.**  The Gym boundary encodes a placement as
`hand_slot * 576 + tile`, plus wait and champion ability.  The policy does not
learn 2,306 unrelated logits: it already factorizes
`P(slot/type) * P(tile | slot)` and composes the exact joint distribution for
PPO and action masking.

**Measured cost.**  The retained 1,536,447-parameter structured checkpoint has
12,742 parameters in `action_type_head`; `card_query`, tile projection, tile
key, tile FiLM, and location bias together add 92,417.  Action decoding is not
the dominant parameter or simulator-throughput cost.

**Known defect.**  Physical hand-slot identity is a severe shortcut.  The
accepted 6.19M diagnostic parent converted legal-affordable Hog windows at
0/23, 18/20, 4/4, and 32/32 in slots 0--3, and preserved card plus tile under
all slot permutations on only 51.07% of decisions.

**Rejected interventions.**  Post-hoc hard equivariance, permutation
distillation, timing-query replacement, full-dose slot permutation, 25% slot
permutation, and a fresh conditional-slot-only architecture all improved some
symmetry/offline metrics but regressed complete games.  The exact fresh
conditional-slot architecture went 0--72 with 98.48--100% playable no-op.
These failures rule out another retrofit or offline-only symmetry sweep.

**Next discriminating A/B.**  Train from initialization on the same new
two-actor replay corpus and simulator-native recurrent states:

- control: current four slot/type logits plus conditional tile heatmaps;
- candidate: explicit play/wait/ability gate, shared pointer score over the
  four current hand-card tokens, and the same card-conditioned 18x32 heatmap.

The flat Gym ID remains unchanged.  Encoder width, total parameters (within
5%), optimizer, data order, seeds, action masks, placement decoder, and update
budget must match.

**Promotion gates.**  Three seeds; exact card-permutation equivariance;
play/no-op calibration; card identity accuracy; within-one/two-tile placement;
per-slot utilization for every designated win condition; matched random,
balanced, reactive-defense, bridge, slow-push, spell, split-lane, and Hog game
blocks; held-out deck/archetype chronology; no regression in crowns, incoming
tower danger, defense-event success, or worst-workload record.

## A2. Spatial action distribution

**Decision.**  Retain the categorical 18x32 heatmap until a matched experiment
beats it.  Clash placement is multimodal; direct `(x, y)` regression can average
two good lanes into one bad center placement.  Continuous coordinates remain
in the neutral extracted world state, while expert actions are quantized using
the simulator's existing canonical action-space transform.

**Allowed alternative.**  A coarse-to-fine categorical decoder may be tested
later if it preserves exact legal masks and improves H100 learner throughput or
held-out spatial accuracy.  It cannot be promoted from FLOPs alone.

## A3. Replay state and player perspective

**Decision.**  Extract one neutral absolute-coordinate match state from each
spectator frame: public arena/clock plus both players' HUD-derived private state
and actions.  Project it into two structured actor examples.  Player-one
canonicalization reuses the existing 180-degree transforms in
`StructuredObservationBuilder` and `DiscreteTileActionSpace`; source images and
HUDs are not flipped or reconstructed.

The actor receives public state plus its own four-slot hand, Next card, integer
and fractional elixir, and visible evolution-cycle/readiness state.  Printed
card costs and grayscale affordability are current-frame recognition and
consistency evidence; static official cost still comes from the compositional
card descriptor rather than becoming a second independent semantic lookup.
Visible hero and evolution variants are mechanics-bearing state and must not be
silently collapsed to the root-card family.  Represent them as the shared base
card descriptor plus an explicit typed variant/readiness/progress channel (or
an exactly equivalent typed variant token with shared parameters); unknown
variant art fails closed.
Opponent hand/Next/elixir/evolution may supervise offline labels or a privileged
critic but must not enter actor tensors.  Transient selected-card glow, slot
disappearance, and Next-to-slot refill are action-label evidence only and must
not enter the pre-action actor state.  Both projections from one match remain
in the same split.

## A4. Temporal state

**Current decision.**  Use the small model-owned structured recurrent state for
exact clock continuity, opponent elixir arithmetic, revealed-card cycle
counters, confidence, and learned residual belief.  Do not use an external
inference accumulator or a generic LSTM solely to rediscover deterministic
rules.  Vision emits current-frame measurements/events; recurrence remains
inside the serialized policy.

**Open gate.**  The cycle/resource channels remain behind behavior-preserving
zero-output policy gates until current-frame event accuracy and complete-game
rehearsal prove that opening them helps.

## A5. Human-video source

**Current decision.**  The permission-cleared YouTube channel is the intended
human-training source if its high-resolution canary passes state/action label
quality.  Hugging Face has zero future training probability once replacement
is proven; retain only a compact out-of-domain regression set until the new
lineage passes gameplay.  Do not redownload 1.458 TB merely to cross-deduplicate
a corpus that will not be mixed into training.

## A6. Card and entity representation

**Current design.**  Every visible card/entity token combines a learned identity
embedding, public immutable mechanics features, current dynamic entity features,
token kind, and (for cards) a slot embedding.  Static mechanics are not a large
input burden: they are projected once per token, and they let Giant-like cards
share useful geometry/durability/targeting structure without preventing the
identity embedding from learning exceptions.

**Evidence.**  The older architecture tournament does not support either
"mechanics always help" or "identity is enough."  Identity-only attention beat
the matched hybrid on the first seed, then failed to repeat.  A zero-initialized
mechanics residual improved the local split and regressed both chronology and
broad independent corpora.  It also failed to improve rare-card transfer.
Wide pooled/hybrid did best among tested rare-card candidates, but later failed
gameplay through extreme playable no-op behavior.

**Decision.**  Retain learned identity plus normalized public mechanics in a
fresh model.  Do not add another globally active mechanics residual to an old
checkpoint.  The next useful mechanics experiment is an auxiliary or
contrastive representation objective: cards with similar public mechanics
should begin nearby while identity remains free to encode discrete mechanics
and matchup-specific behavior.

**Gate.**  Compare hybrid control against hybrid plus mechanics contrastive
pretraining at matched width/seed/data.  Report rare-card and entirely held-out
card/archetype performance, not only aggregate NLL.  Reject if held-out card
choice, spatial accuracy, gameplay, or calibration regresses even if embedding
neighbors look intuitive.

## A7. Entity encoder and attention topology

**Current design.**  Global self-attention covers the global token, five visible
card tokens, and every valid entity; trailing padding can be trimmed per batch.
This is globally relational, not local attention.

**Evidence.**  DeepSets/pooled encoders were 2.8--4.8x faster in learner-kernel
timing and improved likelihood in some independent screens.  Their deterministic
card choice remained weaker, and the best wide pooled gameplay smoke no-op'ed on
98.14% of playable decisions and lost both held-out games.  Conversely, trimming
unused entity padding preserves the attention architecture and improved the
multi-process actor path by about 21% and imitation training by 1.45x in the
production trial.

**Decision.**  Keep global entity attention as the behavioral control and enable
shape trimming in fresh-lineage training.  Do not promote DeepSets from speed or
NLL.  Reconsider a cheaper set encoder only with equal-budget, multi-seed complete
game evidence on the new corpus.

## A8. Critic privilege boundary

**Current design.**  PPO uses an asymmetric critic with exact full simulator
entities, both players' hand/Next cards, and opponent elixir/refill state.  The
actor excludes those private fields.  This is valid centralized training, but
the critic cannot be treated as a deployable live value function.

**Decision.**  Keep the privileged critic for simulator PPO only while measuring
whether it actually reduces variance.  Train a separate public-state value/Q
model for live inference or search.  Human-video examples may provide both HUDs
to an offline training critic, but actor tensors must be projected to the
corresponding player's own HUD before batching.

**A/B.**  Privileged critic versus actor-public critic with identical actors and
rollouts.  Promote privilege only if it improves sample efficiency or policy
strength without worsening held-out public-state calibration.  Never use the
privileged critic during live action selection.

## A9. Reward and training target hierarchy

**Current design.**  Terminal crowns/wins are supplemented by public potential
shaping for tower pressure, board value, danger, and localized defensive outcome
episodes.  Prior counterfactual work found a concrete failure where board-value
shaping credited a deployment without debiting spent elixir, producing almost
all-play targets; fixing resource accounting removed that artifact but did not
make short-horizon labels predictive of gameplay.

**Decision.**  Terminal outcome remains the authority.  Dense shaping is a
variance-reduction aid, never a behavioral objective by itself.  Any new term
must pass reward-gaming unit scenarios, action-frequency calibration, defense
gates, and matched complete games.  Prefer localized event credit or auxiliary
prediction losses over permanently increasing global reward weights.

## A10. Inference search and value lookahead

**Evidence.**  A public state-value search improved a 20-game validation block
from 15--5 to 17--3 and an eight-game held-out screen from 5--3 to 7--1.  It then
turned wins into losses on expanded held-out and fresh quarantine decks.  The
outcome model generalized observationally (held-out AUC 0.746; paired AUC 0.806)
but failed as a counterfactual action value.  A separate abstaining short-horizon
heuristic search also caused losses despite overriding only about 0.16% of
decisions.

**Decision.**  Do not attach state-value or heuristic lookahead to the current
actor.  A future search experiment requires action-conditioned counterfactual
training: branch diverse legal root actions with matched continuation randomness,
train a Q/ranking model on realized relative outcomes, calibrate uncertainty,
and allow abstention.  It still must pass a fresh no-regression quarantine.

## A11. Checkpoint lineage and experiment accounting

The currently retained structured gate-zero artifact reports only update 10 and
8,960 transitions, but it is a wrapper over several imitation, oracle type-head,
and PPO ancestors.  Its local counters therefore do not express total effective
training or data exposure.

**Decision.**  Every fresh experiment must write an append-only lineage manifest
with parent hashes, cumulative simulator transitions, imitation examples/epochs,
corpus and split hashes, trainable parameter scopes, optimizer resets, reward
profile, and all promotion/rejection reports.  Architecture decisions must not
compare artifacts by filename update number or local `total_transitions` alone.

## A12. Imitation examples, no-op sampling, and missing labels

**Measured mismatch.**  The current 1,000-game TV type/timing training split has
10,446 rows across 451 episodes.  It is 53.02% plays and 46.98% no-ops, but has
only five unique action IDs because every placement uses a type-only placeholder.
The strict location split has 2,617 real placements and 689 unique actions, but
every row is a singleton episode and there are no wait examples.  The existing
121,917-row simulator pretrain is 90.49% no-op; even conditional on a legal play,
57.76% of its labels are no-op.

These sources answer different questions.  Concatenating them under one ordinary
joint cross-entropy silently makes placeholder tiles, missing timing, and real
spatial labels look equivalent.

**Decision.**  The new YouTube neutral corpus must preserve fixed-cadence causal
sequences and expose separate supervision masks:

- every accepted decision frame supervises play/wait/ability;
- play frames with resolved hand transition supervise the semantic card pointer;
- only high-confidence deployment anchors supervise the tile heatmap;
- future confirmation may create a label, but never an input feature;
- uncertain/missing labels contribute zero to that component, not a fake tile or
  no-op;
- no-op sampling must preserve empirical timing while using explicit class/dose
  weighting rather than discarding most quiet frames.

**A/B.**  Compare the existing joint objective with a hierarchical masked loss on
identical sequences.  The primary offline gates are play reliability/calibration,
card accuracy conditional on play, and spatial likelihood/tolerance conditional
on a trusted location.  Complete-game gates decide promotion.

**Prototype status.**  `src/clasher/rl/hierarchical_imitation.py` now implements
the bounded loss contract without wiring it into the historical trainer.  It
factors only the label-independent public action mask; accepts separate trusted
decision, card, and tile targets; requires `-1` for every unknown component;
normalizes each head over its own trusted denominator; returns differentiable
zero for an empty component; and fails closed if a trusted label is not
public-legal.  Tests cover zero gradients for missing labels, hand permutation,
mask immutability, broken trust implications, and all-head backpropagation.
Fresh F0--F3 integration and matched training remain required before promotion.
Evidence: `reports/hierarchical_masked_imitation_prototype_20260817.md`.

## A13. Entity capacity and H100 batch shape

Actual accepted human states are small relative to the 128-slot capacity.  In the
TV type training split the visible entity count is median 9, p95 15, maximum 30;
the location split is median 9, p95 15, maximum 24.  Simulator pretraining is
median 10, p95 17, but reaches 67 in crowded states.  A fixed 128-token batch
therefore spends most attention FLOPs on padding.

**Decision.**  Keep capacity 128 as a fail-closed correctness ceiling, but pack or
bucket each batch to its actual maximum (for example 8/16/24/32/64/128 compile
buckets).  Preserve crowded simulator states rather than lowering the ceiling.
For H100 training, batch across games by bucket and keep sequence/split identity;
do not pad every example to the global worst case.

## A14. Deck curriculum and what "held out" means

**Current asset.**  The procedural curriculum contains 1,720 strict training
decks across eight archetypes, with card exposure ratio reduced from 23.51x to
5.83x.  It is signature-disjoint from 82 validation and 151 whole-archetype
holdout decks.  Graveyard, Lava Hound, Royal Hogs, and X-Bow are deliberately
absent from RL training.

**Decision.**  This is a strong *architecture-selection* split, but it cannot be
the final skill curriculum.  Permanently withholding four enabled win conditions
asks zero-shot transfer to substitute for learning gameplay humans actually use.
Use the whole-archetype holdout while selecting representations/objectives; once
a design is frozen, admit all enabled archetypes to final training and create a
new quarantine over unseen deck compositions, matchup pairs, players/time, and
later chronology.  Maintain a smaller rotating zero-shot-card probe as a research
metric, not as the final production training restriction.

**League requirement.**  Balance training simultaneously by archetype, designated
win-condition use, card exposure, and matchup difficulty.  PFSP must include a
population of historical neural policies as well as deterministic strategy bots;
otherwise the learner can specialize to a small set of scripted reactions.  A
candidate advances only on worst-archetype and worst-opponent performance, not
mean win rate alone.

## A15. Recurrent causal-history integrity

**Confirmed bug.**  The historical `combine_imitation_corpora()` reset each
episode start correctly, but then replaced every non-start `previous_actions`
value with the previous row's *expert/oracle label*.  The oracle sources used a
0.1 expert probability, so their states usually followed behavior-policy actions,
not oracle actions.  The rewrite fabricated a recurrent history inconsistent with
the observed state.

Across the three 4,096-row source corpora, source behavior history disagreed with
the prior expert label on about 19.43% slow-push, 19.45% reactive, and 12.89%
split-lane rows.  Regenerating the 12,288-row mix while preserving source behavior
changes 2,112 `previous_actions` values (17.1875%) and no other training array.

**Fix and quarantine.**  The combiner now preserves source `previous_actions` for
non-start rows and records `previous_action_policy=preserve-source-behavior`.
Focused tests, Ruff, and mypy pass.  The clean artifact is
`datasets/derived/structured_oracle_mix_seed1063501/mix_oracle3_12k_causal_v2.npz`
(SHA-256 `690dc0929420a6bcdb8a6f80cfa7ccbdc17d6f3036f82935c7d8e10008695316`).
The old promoted gameplay result remains an observed result, but neither it nor
its gate-zero descendants are clean causal-training controls.  Do not continue
training from that lineage or the old mixed corpus.

**Required A/B.**  From the same pre-mix parent, fit old-history and preserved-
history arms with identical seeds/order/scope, then compare recurrent likelihood,
state replay, and complete games.  New architecture experiments use only the
preserved-history corpus regardless of whether the old arm happens to win.

## A16. Train/live observation equivalence

**Confirmed shift.**  The retained checkpoint says `causal-frame-v1`, but its
simulator degradation still keeps every visible entity with exact identity and
position, supplies exact HP/tower HP whenever those fields are retained (dropout
but zero noise), uses exact native facing where video supplies displacement, and
supplies exact own hand and elixir.  The lineage is inconsistent for public
Next: earlier exact-simulator pretraining included it, while the 12,288-row
causal sidecar zeros slot 5 throughout because the legacy loader rejected a
nonzero fifth slot.  The loader defect is now fixed for future corpora: exactly
four hand slots plus public Next are allowed, and only additional private slots
are rejected.  Historical sidecars are not rewritten.  Confidence values are
fixed synthetic constants rather than calibrated sensor probabilities.  The learned
entity/global confidence residuals have nonzero output weights, so this mismatch
can directly change behavior.

Channels 23--26 and 30 also duplicate immutable speed/range/sight/radius/damage
already available in the model's card-semantic table.  They should be internal
model data, not noisy per-frame dynamic measurements.  Current exact remaining
status/attack/deploy clocks correctly stay zero; future versions may detect a
public onset and maintain time inside model state, never copy simulator clocks.

**Resolved mask issue.**  `PublicActionMaskBuilder` previously removed a hand
slot when raw recognition confidence was below `0.99`.  Training sidecars
commonly promoted accepted identities to confidence 1, while honest live
classifier scores need not reach .99, turning uncertain-but-accepted cards into
forced no-op.  Contract v2 now separates accepted identity from calibrated
probability: a nonzero card token with any positive confidence is present, and
zero confidence fails closed.  The confidence remains a policy input but no
longer independently erases an accepted card from the legal-action mask.

**Decision.**  Do not launch long RL against the existing synthetic observation
distribution.  First run a no-training corruption-sensitivity audit, then matched
fresh/rehearsal arms:

- B0: current degradation control;
- B1: observed displacement or zero motion, empirical detector misses/confusions
  and position jitter, calibrated Next availability, HP/tower dropout plus noise,
  hand/elixir errors, and
  calibrated continuous confidence;
- B2: B1 plus removal of duplicate static entity channels and confidence residuals.

Select on held-out manually labeled vision, train/live tensor distributions,
human action/card/placement/timing, and paired complete games.  The smallest
likely improvement is B1, not a larger network.

## A17. Canonical perspective consistency

**Confirmed defect.**  The retained checkpoint uses
`canonical_perspective=true` but `canonical_lane_globals=false`.  Player-one
entity positions/vectors are rotated 180 degrees, while left/right own and enemy
tower-HP globals keep source-world labels.  A damaged tower can therefore appear
on canonical right in the entity set and canonical left in the scalar vector.

**Decision.**  Every fresh simulator and neutral-video actor projection uses both
flags true.  Do not rewrite old checkpoint tensors.  Before training, asymmetric
six-tower states, moving entities, projectiles/effects, and corner deployments
must give exact team swap, position/vector rotation, left/right scalar swap, and
all-576-tile action encode/decode round trips.  Both actor examples remain in one
split group.

**Gate status: closed for fresh policies.**  The recurrent trainer had a real
wiring defect: a fresh causal `PolicyConfig` recorded
`canonical_lane_globals=true` while its shared `StructuredObservationBuilder`
used `false` and was injected into the environments.  The trainer now computes
one lane-frame selector used by both builder and config; resumed true/false
checkpoints retain their recorded convention and fresh simulator-exact runs stay
legacy false.  Exhaustive tests cover 4,608 action round trips, all 576 positions
through structured/live actor projection, asymmetric six-tower globals, typed
entities/effects/projectiles at all corners, and native facing-vector rotation.
Evidence: `reports/canonical_projection_parity_gate_a17_20260817.md`.

## A18. Current-client vocabulary and compositional entities

**Confirmed gap.**  The retained vocabulary is derived from 66 configured cards
and contains 155 card/payload tokens, while the packaged current catalog exposes
171 definitions.  Royal Giant is current and semantically supported but absent
from the checkpoint vocabulary, so it maps to `<unknown>`.  Evolution and hero
alternate payloads are deliberately skipped by the old closure.

**Decision.**  Freeze stable IDs from the exact current-client catalog plus all
playable variants/forms and reachable spawned payloads before extraction/training.
Known current bodies/actions may never silently map to `<unknown>`.  Encode
entities compositionally as `(base/source card, variant/form, typed subtype)`
for troop, spawned child, projectile, persistent area, building, and unsupported
decorative objects.  A learned residual may encode genuine discrete exceptions.
Adding a new card must append/migrate IDs explicitly, never reindex silently.

**Vocabulary status.**  The frozen current-client graph now contains 494 actor
tokens: 315 arena detector targets, 177 HUD card actions, and the two reserved
tokens.  It is derived from the exact client-15.546.41 gamedata and retains 14
hero and 41 evolution forms as typed identities.  The retained 155-token
checkpoint misses 77 of 144 canonical card roots; Royal Giant and its typed
body/projectile/push forms no longer collapse to `<unknown>` in the new graph.
This is a stable schema and annotation target, not proof that the April-2024
detector can recognize all 494 tokens.  Evidence:
`reports/current_client_youtube_stable_vocabulary_v1.json` and
`reports/current_client_detector_upgrade_manifest_v1.json`.

The exact client CDN now also supplies technical portrait authority for all 14
Hero HUD variants and all 41 Evolution portraits, fingerprint-hash verified for
client 15.546.41.  That resolves identity/schema ambiguity but not permission or
model accuracy: the copyrighted art remains review-only pending separate
legal/operational approval, and replay-disjoint recognition is still required.
Evidence: `reports/current_client_variant_art_authority_20260817.md`.

**Representation A/B.**  Current summed identity+mechanics token versus normalized
mechanics base plus a bounded learned identity-residual stream and learned fusion.
The retained geometry shows why: mean identity norm is about 11.23 versus 2.20
for base mechanics and 0.81 for semantic extras, so nearly orthogonal identity
vectors dominate even when the mechanics projections of related cards have
cosine near one.  Entire cards/variants and spawned payload IDs must be held out
to test compositional transfer; embedding-neighbor beauty cannot promote.

## A19. Discount-correct shaping and elixir leak incentive

**Confirmed mathematical issue.**  The environment emits
`Phi(s_next) - Phi(s)` while PPO discounts at `gamma=0.995`.  Policy-invariant
potential shaping requires `gamma * Phi(s_next) - Phi(s)` with absorbing terminal
potential zero.  The current return therefore retains a small occupancy and
terminal-residue incentive unrelated to the intended game objective.

The elixir-leak penalty is also large enough to dominate the terminal result: a
full-elixir no-op can cost 0.010 before and 0.005 after a decision window, up to
about 11.25 over 300 seconds versus terminal win reward 1.  Zero-sum arithmetic
does not prove strategic correctness; it can reward spending for its own sake.

**A/B.**  After causal-data and observation fixes, run exactly three matched arms:
legacy objective-v1 + leak; gamma-correct objective-v1 + leak; gamma-correct
objective-v1 with leak disabled.  Add no new handcrafted defense terms.  Require
complete-game outcomes, full-elixir wait/spend calibration, play rate, defense,
and every win-condition utilization; reward curves cannot promote.

## A20. Frozen corruption-sensitivity evidence

A reproducible no-training screen now covers all 12,288 rows/48 episodes of the
clean-history oracle mix, using the retained checkpoint and historical causal
observation sidecar.  This is synthetic sensitivity evidence only; the sidecar's
historical masks are label-conditioned and the noise magnitudes are not empirical
camera calibration.

| Perturbation | Top-action flips | Flip rate | Mean joint KL |
|---|---:|---:|---:|
| zero duplicated static entity channels 23--26,30 | 754 | 6.136% | 0.07412 |
| restore exact public Next from base corpus | 220 | 1.790% | 0.00493 |
| zero legacy facing/motion channels | 27 | 0.220% | 0.000125 |
| position+HP+own-elixir synthetic noise | 16 | 0.130% | 0.0000382 |
| replace fixed confidence constants with binary-present | 15 | 0.122% | 0.0000315 |
| own-elixir noise alone | 14 | 0.114% | 0.0000363 |
| HP/tower-HP noise alone | 1 | 0.008% | 0.000000104 |
| normalized position jitter alone | 0 | 0% | 0.00000000227 |

The old checkpoint materially depends on duplicated static rows, so they cannot
be zeroed as a retrofit; B2 must retrain from initialization with internal
mechanics.  Next's 1.79% flip rate confirms that the exact-pretrain/zero-sidecar
contract mismatch is load-bearing.  Small independent noise sensitivity does not
prove live robustness because detector misses, confusion, association, and mask
errors were not simulated.

Evidence:
`reports/accepted_structured_corruption_sensitivity_all48_seed1064201.json`.

## A21. Causal public masks are mandatory and label-independent

**Confirmed leak.**  A missing sidecar mask previously inherited the exact base
simulator mask.  Three mask writers also forcibly made the expert target legal,
affecting 2,277/121,917 accepted-pretrain rows and 230/12,288 oracle-mix rows.
Thus a policy-input bit could depend on the target label.

**Fix.**  Causal sidecar masks are now mandatory and carry
`PUBLIC_ACTION_MASK_CONTRACT_VERSION=2`.  Unversioned and v1 historical masks
fail closed.  Build/extract/upgrade paths never legalize an expert target; they write a
separate `expert_action_masked` label-metadata array and report zero
label-conditioned mutations.  Counterfactual expert-label tests require the
policy mask to remain byte-identical.  Masked demonstrations must later be
filtered or used only by a loss path that does not enter `PolicyInputs`.

V2 resolves the former raw `.99` legality threshold: the recognizer emits a
nonzero card token only after accepting its identity, any positive confidence
marks that accepted public slot as present, and zero confidence fails closed.
The measured confidence remains a policy feature; it no longer independently
erases an accepted card from the legal-action mask.

## A22. Live adapter is part of the model contract, not deployment glue

`src/clasher/rl/structured_live_adapter.py` now implements the first concrete
current-frame-only boundary from a validated `PublicVisionFrame` to canonical
confidence-aware `PolicyInputs`, a mandatory contract-v2 public mask,
model-owned recurrent state, previous own action/reset/cadence, and a verified
legal action.  It has no input for an exact simulator mask, expert label,
critic tensor, opponent-private HUD state, future frame, or reward.  A fresh
import of the adapter loads neither `BattleState` nor `structured_obs`; directly
constructed frame objects are reserialized and revalidated at the boundary.

The accepted checkpoint is still only a compatibility target, not a deployable
winner.  It ignores the new current-frame clock/play/combat cues: deterministic
resource tracking is off, history width is zero, its clock globals are zeroed,
and its fallback clock increments per invocation.  The adapter reports those
cues as unsupported or ignored instead of fabricating state.

**Bounded contract gate: passed.**  A 100-trace simulator-projected harness now
covers 50 traces per seat and regulation/overtime/triple/tiebreak phases.  Across
350 accepted recurrent steps it compares 8,050 input fields, 350 masks/actions,
and 350 hidden/cell updates exactly; it also checks resets, dropped/jittered and
duplicate frames, repeated cues, unknown cards/entities, confidence failures,
and 700 rejected privileged-label injections.  The harness exposed and fixed a
second lane bug: the live adapter had always canonicalized actor-1 tower globals
even for legacy `canonical_lane_globals=false` checkpoints.  Tower assignment is
now config-aware while entity coordinates remain canonical.  Two runs were
byte-identical with zero failures.

This is short synthetic state-machine parity, not live detector or gameplay
evidence.  The same gate must run again on the fresh `canonical_lane_globals=true`
model, current-client variant closure, empirical confidence/missingness, and
natural long traces.  Unsupported cues must remain typed as unsupported until
that model owns their deterministic/recurrent update.

Evidence: `reports/structured_live_inference_adapter_20260817.md` and
`reports/structured_live_trace_equivalence_gate_20260817.md`.

## A23. Empirical corruption schedule is narrow and joint

The first deterministic live-distribution audit covers the retained permissioned
3204-frame YouTube replay, 6408 actor HUD rows, the accepted manual action gold,
the selected entity annotation review, and both current simulator-derived causal
corpora (121,917 + 12,288 rows).  It reads no expert action, reward, target mask,
future frame, or opponent-private actor input.

The actor-facing missingness is materially larger than the previous independent
synthetic noise profile: the four hand slots are accepted on 64.20%, 55.13%,
59.69%, and 67.23% of actor rows, Next on 67.95%, visible clock on 83.49%, and
elixir on 98.17%.  Missingness co-occurs differently across media-time quartiles
and live entity-count terciles.  On accepted manual gold, card identity is 54/55
with one miss and zero proven wrong identities; 89/89 reviewed deployment tiles
are exact.  Withheld identities are unknown, not negatives.  Detector-box typed
identity (28.99%), HP visibility (19.45%), and typed-tower HP visibility (80.11%)
are coverage statistics, not entity recall or value-error estimates.

**B1 decision.**  A bounded diagnostic may sample one complete retained
actor-frame pattern within a matched time/load stratum and jointly apply only own
hand, own Next, own elixir, and public-clock presence plus their observed scores.
Present fields retain the simulator value; missing fields use their ordinary
sentinel and zero confidence.  Every simulator actor row receives a live pattern,
so no unsupported clean/corrupt mixing weight is invented.  Selection is
counter-based from seed/epoch/episode/row and may not inspect labels or targets.

Entity dropout, false-identity substitution, position jitter, HP/tower-HP noise,
elixir-value noise, clock-value noise, and a temporal run-length model remain
disabled: the one replay has no exhaustive entity/HP/elixir ground truth or
replay-disjoint calibration.  B1 is not promotable until those blockers are
closed; this prevents a detector confidence proxy from becoming fabricated
training truth.

Evidence: `reports/b1_empirical_corruption_schedule_20260817.json` and
`reports/b1_empirical_corruption_schedule_20260817.md`.  Reproducer:
`scripts/analyze_empirical_corruption_schedule.py`.

## A24. Fresh model size and live latency budget

The accepted structured policy has 1,536,447 trainable parameters, of which
1,009,378 belong to the deployable actor/recurrence/action path and 527,069 are
privileged critic, value, or auxiliary training heads.  On representative
packed states from the 121,917-row causal corpus, batch-one CPU inference is
about 1.45 ms at median entity load and 1.98 ms p95 at the 67-entity maximum.
MPS is stable but slower for this small call (roughly 8.4--9.5 ms inference plus
about 1.6 ms tensor ingress), so live policy inference stays on CPU while MPS or
CUDA handles vision/training.

The fresh 494-token F0--F3 family is budgeted at 1.645M--1.670M total and
1.053M--1.077M deployable parameters.  The gate/pointer variants span only
1.48%, within the required 5% match.  Their 400 ms live budget is <=20 ms p95
ordinary inference, <=25 ms crowded inference, and <=30 ms crowded combined
serialization plus inference.  The exact historical 6.19M accepted artifact is
absent; an available 6.17M family reference remains fast but supplies no skill
argument for spending roughly four times the deployable parameters.  No H200
latency is inferred from MPS.

Evidence: `reports/live_policy_parameter_latency_budget_20260817.md` and
`reports/live_policy_parameter_latency_budget_raw_20260817.json`.

## Open audit queue

1. H100 actor/learner synchronization after the PyTorch gym lands.
