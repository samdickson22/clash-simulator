# Independent Clasher architecture decision audit — 2026-08-17

## Scope and authority

This report audits the model and learning pipeline that should precede a serious
H100 training campaign.  It is not a checkpoint promotion and it does not claim
human skill.  Production source and checkpoints were left untouched by this
audit.  While the audit was running, the parent task independently corrected the
recurrent-corpus history defect described below and published a new corpus; that
fix is treated as current evidence rather than duplicated here.

The retained behavior baseline is:

`checkpoints/fresh_structured_causal_v1_seed1062701/resource_belief_gated_seed1063602/resource_u10_gate0.pt`

- SHA-256: `3353615954fdcfdb24f2ba570f1888cd6130242238391a9bcf98dcedbcfc5b88`
- trainable parameters: 1,536,447
- state-dict elements including buffers: 1,554,519
- actor: 128-wide, three-layer global attention, causal-frame confidence inputs
- memory: 64-channel structured state, no LSTM/GRU
- action: four positional slot logits plus wait/ability and four conditional
  18-by-32 placement maps
- behavior evidence: 30-18 over two six-strategy blocks and 6-2 on a small
  whole-archetype screen

That is a useful research parent, not a mid-ladder policy.  Its recent success
came from conservative action-type rehearsal, not a successful long PPO run.

## Executive decision

Do not spend the grant simply extending the retained lineage.  Build one fresh,
matched architecture family around the following design:

1. one current-client neutral match state, projected into two private-safe actor
   views with exact canonical geometry;
2. global attention over packed entity, hand, Next, own-roster, global, and typed
   belief tokens;
3. mechanics-primary compositional card/entity descriptors plus a bounded learned
   identity residual;
4. typed model-owned recurrence for clock fallback, public play-event deduplication,
   revealed deck/cycle, resource uncertainty, and entity continuity, plus a small
   learned residual rather than a dense 384-unit LSTM;
5. a learned play/wait/ability gate, a shared slot-equivariant card pointer, and
   the existing exact card-conditioned 18-by-32 categorical placement map;
6. causal BC/rehearsal first, then short stratified PFSP PPO phases with a separate
   privileged critic and immutable rollback points; and
7. no live search until an actor-visible counterfactual action ranker and the
   tensor simulator each pass independent gates.

The first experiments should isolate these changes.  A single "new architecture"
bundle would make another failure uninterpretable.

## Blocking correctness findings

### C0 — Recurrent oracle history was fabricated; now corrected

The old 12,288-row three-oracle mixture replaced every non-start
`previous_actions[t]` with the previous oracle label even though oracle actions
were executed only 10% of the time.  Source actual-history disagreement was
792/4,077 (19.43%) for slow-push, 794/4,082 (19.45%) for reactive-defense, and
526/4,081 (12.89%) for split-lane.  The old combined corpus forced this to zero.

The parent task corrected `combine_imitation_corpora`, added
`previous_action_policy=preserve-source-behavior`, and generated:

`datasets/derived/structured_oracle_mix_seed1063501/mix_oracle3_12k_causal_v2.npz`

SHA-256:
`690dc0929420a6bcdb8a6f80cfa7ccbdc17d6f3036f82935c7d8e10008695316`.
Exactly 2,112 of 12,288 previous actions differ from the old mixture and no other
training array differs.  This clean one-variable replacement is the immediate
training A/B.  The old checkpoint's complete-game results remain observations,
but its claimed causal rehearsal mechanism is contaminated until the clean fit is
evaluated.

### C1 — Actor-one lane globals use inconsistent coordinates

The retained checkpoint uses `canonical_perspective=true` but
`canonical_lane_globals=false`.  Actor-one entities rotate 180 degrees while
left/right tower-health scalars do not swap.  A damaged canonical-right tower can
therefore appear in the canonical-left global slot.

Every fresh simulator and neutral-video projection must enable canonical lane
globals.  The exact gate is a fully asymmetric state: all six tower HP values,
entities/vectors in both lanes, projectiles/effects, and every one of 576 action
tiles must survive rotate/team-swap/project/round-trip exactly.  Both actor views
from one game must remain in one data split.

### C2 — Current vocabulary is not a current-game vocabulary

The retained checkpoint has 155 tokens built from 66 configured cards, while the
packaged catalog contains 171 definitions.  Royal Giant exists in current data
but maps to `<unknown>` in this checkpoint.  Evolutions and hero forms are
explicitly skipped, and sparse spawned payloads often have flat IDs with no
immutable mechanics.

Before large extraction/training, freeze a current-client manifest covering every
permitted video action, form/evolution, and reachable spawned subtype.  Require
zero unknown known-card actions/bodies in a manually adjudicated canary.  Encode
entities compositionally as `(base/source card, variant, typed subtype)` rather
than asking a sparse random ID to relearn source mechanics.

### C3 — Train and live feature distributions are not equivalent

Accepted causal training used degraded exact simulator rows, not detector-shaped
rows.  It still had exact entity identity and position with no false positives,
exact own hand/Next/elixir, exact retained HP with dropout but no measurement
noise, fixed synthetic confidence values, and simulator facing in fields that
live video interprets as displacement.  Its card-confidence branch is exactly
zero, so a low-confidence wrong hand card enters at full strength.

The first fresh observation A/B must therefore be corruption matched: empirical
entity misses/confusions/duplicates, position and HP error, correlated tower-HP
missingness, hand/Next mistakes, honest confidence calibration, and visible
elixir error.  Remove the duplicate per-entity static speed/range/sight/collision/
damage fields in one arm; those belong in the serialized mechanics descriptor.
Do this before widening the network or launching long PPO.

### C4 — New typed cycle state is carried but not used by the action path

The current dirty source contains a parameter-free `StructuredPublicStateTracker`
that correctly stores revealed card IDs, play counts, availability, uncertain
event mass, clock, and exact cost/regen updates.  In `_run_memory`, that tracker
is returned in `hidden`, while the structured action output is `cell`.  Thus
cycle state persists but does not directly condition actions; only its resource
side effect can reach the cell.

Do not claim opponent-cycle use until a closed-gate parity test proves unchanged
behavior and an opened typed-token path proves that card IDs/counts/availability
actually affect policy logits.  Missed events should produce an interval or
distribution, not a falsely exact point estimate.

### C5 — Reward shaping is not gamma-correct and leak cost may dominate

The environment applies `Phi(s_next)-Phi(s)` while PPO uses `gamma=0.995`.
Policy-invariant discounted shaping is `gamma*Phi(s_next)-Phi(s)` with zero
absorbing terminal potential.  Separately, full-elixir no-op leak penalties can
theoretically sum to 1.125 reward over 30 seconds and 11.25 over a five-minute
match, versus a terminal win reward of one.  Arithmetic is zero-sum, but the
incentive can still reward strategically bad spending.

After the clean-history fit, run exactly three matched reward arms: current
objective-v1, gamma-correct objective-v1 with leak unchanged, and gamma-correct
objective-v1 with leak disabled.  Do not add defense-v4 or tune several weights.

### C6 — The live adapter and label-independent public mask do not exist yet

`LiveInferenceAdapter` is currently a protocol with only a synthetic test
implementation.  There is no production path from `PublicVisionFrame` to token
tensors, confidence, canonical perspective, public action mask, recurrent state,
previous own action, and final action.  The accepted checkpoint also cannot use
the new clock/card-play/combat cue objects: deterministic event/resource tracking
is disabled, history width is zero, clock globals are zeroed, and its private
clock advances once per policy call.

The current causal mask path is also not target-independent.  A sidecar without
`action_masks` can inherit the exact base simulator mask, while sidecar builders
make the demonstrated expert action legal when the public mask rejects it.  That
affected 2,277/121,917 accepted pretraining rows and 230/12,288 oracle-mixture
rows.  The policy input can therefore reveal part of the label.  In addition,
the policy accepts five card tokens but inspected sidecars keep the public Next
slot zero, and the imitation loader still rejects a nonzero slot four.

Before any fresh vision training, implement one typed adapter and require public
masks on every causal row.  Holding the observation fixed while changing only the
expert label must leave the mask byte-identical.  Missing masks must fail closed,
not inherit exact truth.  A label rejected by the public mask may be omitted or
used in a loss-only target path; it must never mutate `PolicyInputs`.

## Architecture decision registry

| ID | Decision | Current evidence | Smallest discriminating test | Reject when |
|---|---|---|---|---|
| R1 | Use neutral absolute state then two actor-safe projections | Existing canonical transforms are sound; lane globals are not | Exact asymmetric rotate/team/privacy round trip | Any coordinate, lane, split, or private-state mismatch |
| R2 | Keep global attention, pack active entities | Historical active width median 13, p95 20, max 50; trimming gained about 21% actor and 1.45x training; pooled alternatives failed games | Dense versus packed logits/state parity, then only profile-driven topology A/B | Silent truncation, changed actions, or pooled offline win with gameplay loss |
| R3 | Mechanics-primary two-stream card encoding plus bounded identity residual | ID norm 11.23 dominates base mechanics 2.20 and semantic 0.81; mechanics alone group related cards, but residual retrofits failed | Three-seed fresh summed-hybrid versus normalized two-stream, with whole card IDs held out | Rare/zero-shot gains do not repeat or common-card/gameplay quality regresses |
| R4 | Add compositional spawned subtype identity | Flat payload IDs can have zero stat descriptors | Hold out payload IDs while retaining source card/subtype | Mechanically distinct payloads collide or spawn-heavy games regress |
| R5 | Confidence must attenuate identity, not merely add a residual | Retained hand-confidence branch is inert | Additive confidence versus confidence mixture under empirical corruption | Candidate becomes passive under uncertainty or clean play regresses |
| R6 | Provide the known own eight-card roster at reset | Current actor sees only hand plus Next and must rediscover its own deck | Unordered roster token A/B on unseen deck combinations | It becomes a deck-signature lookup and fails whole-archetype transfer |
| M1 | Keep typed recurrence; do not restore the 384 LSTM | Structured beat matched LSTM on NLL/play/card/location and 12-12 versus 2-22 | Typed state plus learned residual widths 0/16/32/62 versus compact LSTM, three seeds | Stateless misses public history or residual/LSTM adds no paired-game value |
| M2 | Sync public clock when visible, internal timestamp fallback when absent | Fixed decision clock was exact in simulator but is fragile to dropped/variable frames | Clock/OCR dropout/jitter sequences and variable inference cadence | Invocation count is mistaken for elapsed time |
| M3 | Represent opponent hand/resource as belief/interval | Learned resource best accepted MAE 2.66 elixir, corr .064; opening gates failed | Exact-event, vision-event, and controlled-corruption tracker comparison | Point estimate is uncalibrated or gate worsens complete games |
| M4 | Add typed per-entity recurrent slots after global tracker | Current global state cannot carry multiple occluded identities/status onsets | Crossing/occlusion/status sequences plus manually audited video | Association switches/error do not improve or actions regress |
| A1 | Keep flat 2,306 ID only as environment serialization | Policy already factorizes type and tile | Exact encode/decode/mask parity | Replay/action compatibility or legal support changes |
| A2 | Fresh learned play/wait/ability gate | Default argmax compares one slot to wait and has probability-splitting bias; decoder-only play-gate did not rescue old models | Three-way gate from initialization, matched control and three seeds | Any seed reaches >=95% playable no-op or indiscriminate overplay |
| A3 | Shared slot-equivariant card pointer | Proven Hog conversion by physical slot: 0/23, 18/20, 4/4, 32/32 | All 24 hand permutations on >=1,000 recurrent states plus fresh gameplay | Equivariance fails or offline symmetry again yields <25% breadth score |
| A4 | Retain exact card-conditioned 18-by-32 categorical heatmap | Multimodal, irregular legal support; output is not the main parameter/sim cost | No change in first head A/B | None; this is the control |
| A5 | Defer coarse-to-fine; reject direct XY regression now | Continuous mean can land between valid modes; exact projected PPO mass is hard | Only trigger coarse-to-fine if tile path is >=15% learner time | <1.25x throughput, support mismatch, or >0.5-point spatial loss |
| O1 | Preserve executed histories and complete episodes in BC/DAgger | Old mixture changed 13-19% of causal histories; now fixed | Clean-history one-epoch type-head fit | Any hidden row/target difference or recurrent/gameplay regression |
| O2 | Keep factorized type and location supervision | Exact 2,306 CE already equals exact type plus conditional-tile NLL | Exact CE versus spatial-v1 only on strict location labels | Type-only rows train location or smoothing harms buildings/rolling spells |
| O3 | Use short PPO consequence phases with immutable rollback | Many numerically stable PPO runs regressed gameplay | 20-update control versus policy-KL plus recurrent-rehearsal anchor | Protection is inert or any external workload regresses |
| O4 | Retain separate privileged critic; pretrain on complete outcomes | Valid centralized-training boundary; state-value reranking failed causally | Frozen identical actor, pretrained versus current critic, same PPO budget | Only critic loss improves or actor/gameplay does not |
| O5 | Stratified PFSP, not hardest-only allocation | Long mixed phases later collapsed; targeted rehearsal worked better | 25% safety, 25% strategies, 25% informative historical, 15% recent/self, 10% random versus current allocation | Worst opponent, human calibration, or held-out decks regress |
| O6 | Keep 1,720-deck pool; add matchup balancing | Eight training archetypes, 62 cards, four frozen archetypes; exposure ratio reduced to 5.83x | Matchup-balanced versus card/archetype-balanced at equal marginals | Any frozen overlap or worst matchup cell regresses |
| D1 | Implement one typed live adapter | Current live schema and cue schema have no production policy consumer | 100 complete projected episodes through adapter and direct causal path, both seats | Any unexplained tensor/state/mask/action difference or simulator import |
| D2 | Make causal masks mandatory and label-independent | Exact fallback and expert-action repair contaminate actor inputs | Counterfactual-label invariance plus exact-oracle legality audit | Any mask bit depends on the target, or absent sidecar mask falls back |
| D3 | Train public Next explicitly or keep it absent | Five-token encoder exists, but inspected sidecars keep slot four zero and loader rejects it | Zero-Next versus empirical-confidence/dropout Next on held-out HUD labels | Future backfill enters runtime, or noisy Next is worse than zero-Next |
| S1 | Keep live inference search-free now | State-value search and action-value heads caused fresh win-to-loss flips; location lookahead was 48-48 and +23.7% wall | No online experiment yet | Current control remains authority |
| S2 | Use terminal counterfactuals as offline teacher | Existing exact roots find useful interventions but current ranker had only 369 train roots and 56.52% pair accuracy | >=10k roots: frozen actor vs ensemble reranker vs conservative preference update | <65% pair accuracy, <25% regret reduction, or any heldout targeted-card collapse |
| S3 | Later test belief-safe batched tactical search | Current search reads both players' exact observations/masks; not live-deployable | At most 6 actions x 4 belief particles x 2 RNG, horizons 8/16, tensor resident | Private leakage, fallback, p95 >100 ms, max >200 ms, or no gain over cheap reranker |
| S4 | Defer PUCT; reject MuZero now | Exact simulator exists; belief-space branching is large | PUCT only after shallow search wins under equal transitions/latency | No >=15% regret improvement at equal budget |

## Predeclared first architecture factorial

Use the new neutral/current-client/corruption-matched data contract for every arm.
Do not compare a corrected candidate with a legacy-data control.

- **F0:** current summed hybrid representation, structured memory, current
  positional slot/type head, current heatmap.
- **F1:** F0 plus a learned three-way play/wait/ability gate; positional card
  choice retained.  Diagnostic only.
- **F2:** F0 plus a shared slot-equivariant card pointer; play mass derived using
  the control formulation.  Diagnostic only.
- **F3:** learned gate plus shared pointer, unchanged heatmap.  Preferred action
  candidate.
- **F4:** F3 plus mechanics-primary two-stream card representation and bounded
  identity residual.  Run only after F3 passes the collapse screen, so action
  and representation effects remain separable.
- **Memory subfactor:** on the winning head/representation, compare typed state
  with 0, 16, and 32 learned residual channels; retain the 62-channel and compact
  LSTM as controls only.

All arms use three fixed seeds, identical full episodes, data order, optimizer
examples, exact masks, critic targets, parameter count within 5%, and the same
bounded PPO transitions.  Neither final human nor fresh quarantine records may
select the architecture.

## Universal staged gates

### Stage 0 — structural and causal

- zero opponent-private actor tensors, exact masks, simulator objects, rewards,
  future labels, or external accumulated history;
- one production current-frame-to-policy adapter with zero unexplained differences
  against the direct causal path; mandatory public masks with zero label dependence
  and zero exact-mask fallback;
- exact two-perspective canonical/privacy round trip;
- zero unknown current-client card actions/bodies on adjudicated canary;
- 100% card-and-tile preservation under all 24 hand permutations, maximum
  slot/location logit error `3e-5`, and mode-probability error `1e-6` for the
  pointer candidate;
- zero illegal actions and zero silent entity truncation;
- bit-identical closed-gate upgrade behavior over 128 recurrent episodes.

Failure here rejects implementation before training.

### Stage 1 — offline and collapse screen

- three seeds and complete recurrent sequences;
- action-type NLL no worse by more than `0.01`, accuracy no worse than `-0.5`
  point, play Brier no worse than `+0.005`, ECE no worse than `+0.01`;
- conditional card accuracy and within-two-tile accuracy no worse than `-1.0`
  point on validation, chronology, whole-archetype, and completely held-out card
  identities;
- 12 random plus 12 balanced paired-seat games per seed;
- reject any seed with >=95% playable no-op, <=1% playable no-op without matched
  human cadence, or fewer than 5% threatened responses.

Stage 1 can reject; it cannot promote.

### Stage 2 — development advance

- established 72-game random/strategy/Hog breadth matrix per seed;
- 48 matched six-strategy games, 24 direct parent games, and at least the frozen
  held-out tripwire;
- candidate score and crown margin at least control for every seed in aggregate;
- no workload loses more than one game or two crowns; no held-out archetype record
  loss;
- defense-event success no worse than two points, no worse mean defensive outcome
  or incoming tower danger, and threatened action rate within two points;
- every designated win condition and every physical slot with at least two legal-
  affordable windows has at least one use and >=25% conversion;
- learner examples/s >=95% of control, rollout decisions/s >=98%, parameters
  within 5%.

### Stage 3 — promotion

- at least 216 fixed external games plus >=96 direct held-out candidate/control
  games per seed and a fresh multi-deck/archetype quarantine;
- paired score-difference bootstrap 95% lower bound above zero overall;
- held-out/quarantine score-difference lower bound above `-0.02`, no worse worst
  opponent/archetype, no losing seat aggregate;
- no reproducible baseline win-to-loss tactical regression;
- replay/calibration, card-frequency/zero-shot, placement, defense, passivity, and
  all 12 win-condition gates remain satisfied;
- one-shot selection: failed promotion records become quarantine evidence, not a
  tuning set.

Only this stage can replace the accepted research parent.  Mid-ladder-human skill
still requires real-client matches against consenting humans under a separately
defined protocol.

## Ranked experiment roadmap

1. **Clean-history rehearsal rerun.** Start both old-history and causal-v2 arms
   from the same pre-mixture `structured_e3.pt`; same seed, one-epoch type-head
   scope, targets, and ordering.  This is cheap and may invalidate the current
   behavioral parent.
2. **Typed live adapter and public-mask contract.** Implement current-frame to
   `PolicyInputs`, recurrent ownership, reset/cadence, public mask, and action;
   require mask presence and target-label invariance.
3. **Canonical/current-client contract gates.** Fix lane semantics for the fresh
   lineage, freeze full variant/spawn vocabulary, and prove neutral-to-two-actor
   privacy and action round trips.
4. **Corruption-matched observation A/B.** Current synthetic degradation versus
   empirical detector/HUD errors, then the compact dynamic schema/confidence mix.
5. **Public Next contract A/B.** Repair slot-four loading, then compare absent
   Next with empirically corrupted/confidence-calibrated Next; never future-fill
   runtime input.
6. **Fresh action factorial F0-F3.** Explicit mode gate and shared pointer from
   initialization, full heatmap unchanged.
7. **Fresh card representation F4.** Mechanics-primary two-stream plus bounded
   identity residual, with whole card IDs and variants held out.
8. **Typed memory residual sweep.** 0/16/32/62 channels plus compact LSTM control;
   expose cycle/resource tokens only after exact closed-gate evidence.
9. **Principled reward screen.** Current versus gamma-correct versus gamma-correct
   without leak.
10. **Critic outcome pretraining, stratified PFSP, then matchup-balanced sampling.**
   Each is a separate bounded A/B with immutable rollback.
11. **Scale the winning pipeline on H100.** Increase seeds/data/width only after it
   passes Stage 2; the grant is best used for parallel matched experiments, not
   one opaque long run.
12. **Counterfactual learned reranker, then selective tensor search.** Search is a
    later tactical amplifier.  Do not pursue MuZero or current private-state
    search.

## Specialized audit reports

- `reports/observation_representation_architecture_audit_20260818.md`
- `reports/architecture_audit_memory_belief_20260817.md`
- `reports/action_architecture_audit_20260817.md`
- `reports/learning_objectives_curriculum_audit_20260817.md`
- `reports/inference_search_value_architecture_audit_20260817.md`
- `reports/cross_contract_policy_wiring_audit_20260817.md`
- `reports/accepted_structured_train_live_equivalence_20260817.md`

## Bottom line

The likely winning architecture is not radically larger and not radically
simpler.  It is more explicit: current measured state is separated from immutable
mechanics; deterministic public bookkeeping is separated from learned tactical
memory; play timing is separated from card identity; card identity is separated
from physical hand slot; and observational value is separated from causal action
value.  Those boundaries address the failures the repository has actually
measured.  H100 scale becomes useful after these small matched experiments select
a causally valid pipeline.
