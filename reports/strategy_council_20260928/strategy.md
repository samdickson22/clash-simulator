# Clasher strategy: council candidate v2

Status: candidate for joint review, September 28, 2026. Astra endorses this version, incorporating the final candidate-coverage and automatic-bias safeguards requested by Fable. Fable's approval of this same version is pending. This document authorizes no implementation, native collection, training or resource launch during the council discussion.

This candidate incorporates the common conclusions of [Astra Round 2](astra-round2.md), [Astra Round 3](astra-round3.md), [Fable Round 2 and its reconciliation addendum](fable-round2.md), and the two final blocking additions from [Fable Round 3](fable-round3.md), using the statistical/controller corrections in [Astra Round 4](astra-round4.md). The coordinator clarified that Fable accepts the existing strategy and requires only defensible candidate-coverage and automatic-bias additions. Other Round 4 recommendations are not new requirements in this version. Once both members approve the same version, this document can serve as the implementation handoff. Routine choices within the specified scope belong to the implementer rather than another architecture round.

## Objective and chosen approach

Build a strong human-level Clash Royale player. First demonstrate a learned policy that adapts to changed boards, decks and levels and improves against reacting opponents. No current evidence establishes human-level strength.

Train a fresh public-information entity-attention/LSTM actor with recurrent PPO. The main lineage receives a short public-script warm start; a from-scratch lineage provides the control. A privileged oracle may supply a third initialization only after proving useful as a player and passing the relevant reference checks. Then expand into a diverse opponent league and broader decks. Develop compatible human supervision and perception alongside learning. Fast actor-only deployment is the default; search/distillation must demonstrate a benefit before entering the main path.

The compute grant supports replicated learning and evaluation on CPU simulation workers plus a GPU learner. The Mac mini's disk and chip do not constrain the experiment budget. Start with the scalar simulator; accelerated simulation is optional until workload coverage and parity are established.

Exact trajectories and identical winners under fixed replay commands are not prerequisites. Prioritize credible public-state/control semantics, consequential action rankings under reacting play, and repeatable simulator-only exploits. Small dynamics differences remain diagnostics unless they teach harmful decisions.

## Current authority and evidence boundaries

Work in `/Users/sam/Desktop/code/clasher`, consolidated main at base `95feeb0e525ee1665360df6e28116b01c3436ecf`, preserving the coordinator's existing uncommitted repairs. Old worktree paths are compatibility links, not separate source authorities. Pin the actual source and configurations before each experiment.

The external simulator reference is Null's 15.535.86; official-client equivalence is unestablished. V7 remains failed, with its original criteria, source pins, missing configurations and exposure history intact. The recovered 13 opened captures and repaired reacting branches are development evidence, not fresh acceptance or playing-strength evidence. Recovery test results do not establish full resident tensor/CUDA parity.

Create a new prospective readiness protocol and evaluator. Do not modify the historical evaluator to manufacture a v7 pass. Opened evidence can inform protocol design and noise estimates; it cannot become fresh acceptance evidence.

No gameplay fitting precedes Tier A. Contract tests and synthetic optimizer checks may precede it. No historical policy or corpus is automatically compatible with the new actor contract.

## Actor and action contract

Use `src/clasher/rl/model.py::ClasherPolicy` with fresh weights. Initial configuration:

| Component | Choice |
|---|---|
| Entity encoder | Width 128, four attention heads, four actor layers |
| Critic encoder | Existing separate privileged encoder, two layers |
| Memory | LSTM, width 256 |
| Card representation | Semantic descriptors plus current card identity |
| Coordinates | Canonical perspective and canonical lane globals |
| Public history | Four history slots, eight seen-card slots |
| Semantics/levels | Card semantics version 4; public-v3 visible levels/confidence, extended for own hand/next-card and tower levels |
| Timing/control | Five native ticks, 250 ms; categorical `slot` hierarchy |
| Disabled options | Repair/prototype/slot-choice adapters, hazard/event accumulation, deterministic resource gates, action-value heads |

These settings span model, observation builder and environment configuration; they are not all `PolicyConfig` constructor arguments. In particular, the existing deterministic resource tracker and event decoder cannot be combined with this LSTM configuration.

The actor sees own hand and visible next card, own elixir, clock, public tower state, causally observed plays, and visible entities. Start with clean values for the real-play-v2 feature subset plus levels. Static card metadata is permitted. Preserve confidence and missingness; exclude unsupported status flags, hidden timers, exact opponent resources/hands, future events and privileged simulator state. Opponent hand/cycle/elixir are beliefs based on observations, not exact actor inputs. Include previous own action but zero previous reward for every actor domain.

The privileged critic and auxiliary opponent-state prediction targets are training-only. Their values must not enter actor inputs, masks, caches or recurrent state. Equal public histories with different hidden states must produce equal actor outputs under the same inference randomness.

Use `PublicActionMaskBuilder` for actor legality. The existing action space contains four current-hand slots times 576 tile centers, wait and ability. Unsupported abilities remain masked by the declared scope. Audit coordinate round trips and placement-sensitive pulls/spell edges before scaling. Add a constrained sub-tile residual only if projection demonstrably changes useful choices; preserve original coordinates in data.

Sample the full stochastic distribution during collection and recompute the identical likelihood in PPO, including every action factor and mask. Wait can be reconsidered at the next observation. Record submitted, accepted and effective deployments separately. Illegal or rejected commands are execution failures, not opportunities for silent tactical fallback. Remove the hard-coded illegal-action penalty from this lineage's principal reward while retaining failure logging.

Evaluation defaults to this stochastic policy at temperature one with fixed evaluation RNG seeds. A deterministic decoder is a separately identified candidate, frozen before its comparison.

## Data, decks and initialization

The first learning experiment uses the 16 base cards supported by `public_scripted_opponent.py`: Archers, Cannon, DarkPrince, Fireball, Giant, Goblins, HogRider, IceGolem, IceSpirit, Knight, Log, Musketeer, Prince, Skeletons, Tesla and Zap.

Train across Hog, Giant, pressure/control and procedural decks. Sample approximately 60% structured decks, 30% role-preserving neighbors and 10% legal stress decks. Keep each parent deck and its derivatives together in one split. Hog 2.6 remains a fixed deployment/evaluation slice. Altered human-designed rosters are derivatives, not professional demonstrations. Out-of-scope archetypes are stress tests, not mandatory pilot acceptance slices.

The scripted initialization uses up to 500,000 labeled decision opportunities from complete games, including natural waits. Use public-script styles and reviewed `StrategyBot` styles, recording provenance. These are engineering teachers, not human experts. Correct timing-prior changes if sampling reweights play versus wait. The from-scratch arm uses the same actor, opponents and PPO budget.

The optional oracle arm uses the structured collection path in `imitation.py`, including behavior mixing where appropriate. `train_dagger_oracle.py` is the legacy raster entry point and is not the implementation path for this actor. Verify all reused collectors against the new contract.

Before distilling the oracle, it must:

1. Receive prospective admission for its search/candidate scope after Tier A checks.
2. Pass a 64-game paired-seat screen and, if promising, an independent 256-game confirmation against the same reacting pool and strongest scripted baseline. Require at least 0.05 match-score advantage with a 95% interval above zero.
3. Pass fresh reference checks on oracle-selected candidates before generating distillation labels.

Use uncertainty-aware soft candidate targets, with `counterfactual_policy_iteration.py::kl_regularized_candidate_target` as a reusable component to inspect. Soft labels do not by themselves solve hidden-information contradictions. A teacher's strength does not establish student learnability; the oracle student must still pass the replicated comparison. If teacher qualification fails or its scope is not admitted, defer that arm without blocking the two mandatory arms.

### Human observations

Timebox the initial audit to one working day using the existing KataCR/TV-Royale corpora and saved video. Inspect HUD-confirmed actions, public state alignment within the available frame precision, form/ruleset identity, legal masks and confidence. Group complete matches and both perspectives; keep training and evaluation disjoint.

Twenty clean sequences establish feasibility, not broad training sufficiency. Create a held-out human-observation evaluation set and use reliable training examples as a later measured, low-weight supervised prior. Low weight does not make bad labels safe. No bulk video extraction is required for the pilot.

IL_Replay remains action-only until reconstruction is defensible. The inspected 5,000-match sample has no fully compatible two-sided base/level-11 match, unknown active forms on placements and unattributed abilities. Retain forms and uncertainty. Safe uses include deck/co-occurrence analysis and coverage planning; do not relabel modern forms as base-card state/action truth.

## Learning experiment

Use synchronous recurrent PPO, initially 64 environments, 128-step chunks, 32-step burn-in, two PPO epochs, learning rate 1e-4 and clip 0.2. Log mode/card/location entropy separately. Batch packing may change with measured memory and throughput; keep effective sample accounting explicit.

The initial objective is terminal competitive score plus a small fixed potential-based shaping term. Use gamma 1, zero terminal potential and GAE lambda 0.95. Select and record the small shaping coefficient in the run configuration. Disable defense-event, elixir-spending, forced-play and illegal-action rewards in this primary comparison. Terminal-only reward and gamma 0.999 are follow-up ablations if evidence points to shaping or credit assignment, not extra mandatory pilot arms.

Carry recurrent state across matches and reset at true episode boundaries. Reconstruct chunk state through burn-in/prefixes; distinguish collection truncation from match termination. Refresh state consistently when worker policy weights change. Defense-scenario curricula remain off until their truncation semantics are correct.

Run three training seeds per admitted initialization, each for five million learner decisions. Count learner actions rather than both seats as separate learner experience. Freeze diagnostic checkpoints at one million and comparison checkpoints at five million. The two mandatory arms total 30 million decisions; the qualified oracle adds 15 million. A post-admission smoke of at most 100,000 decisions verifies execution, not algorithmic potential.

For the first million decisions, use a frozen opponent mixture of scripts and initial policies. Then introduce retained checkpoints and current self-play, targeting 25% scripts, 50% historical/checkpoint opponents and 25% current self-play once that pool exists. Scripts fill unavailable history slots. Keep opponents fixed per match and record policy versions and sampling schedules. Add PFSP after reliable improvement, maintaining historical coverage; add exploiters when the pool has useful strategic diversity. Random/no-op opponents are controls, not a major source of rewarded wins.

Evaluate a fixed opponent matrix throughout. A changing training-league win rate is not evidence of improvement.

### Levels and scope growth

Use level 11 for the first million decisions. Then vary supported card and tower levels from 10–12 in half the games, retaining a nominal half. Carry own undeployed-card levels and visible body/tower levels correctly. Extend teacher level handling before using mixed-level labels. Hold out level/deck combinations and report both nominal and mixed-level performance.

Prepare broader base-card coverage during the pilot, preserving recognizable professional-style decks and adding air, splash, swarm, buildings, spells and spawn mechanics. The existing roughly 66-card support artifacts are candidates for scope, not proof of admission. Admit new mechanic bundles before training on them. The 16-card pilot must diagnose learning-system viability, not become an indefinite substitute for broad play.

Hidden HP/damage variation follows a small parameter-specific development study. Tower-HP and timing residuals alone cannot identify the responsible dynamics parameter. Arbitrary ranges may be used later as explicitly labeled robustness stress tests, not as measured native uncertainty. Keep perturbations coherent and fixed within an episode; preserve costs, targeting and legality.

## Prospective readiness and promotion

Implement `training-readiness-v2` and a separate decision evaluator. Freeze source/config hashes, family generator, candidate generation, continuation rules, roles, tolerances and missing-case accounting before fresh outcomes.

### Tier A: scoped entry

Use 32 independent fresh families spanning the 16-card scope and tactical situations, balanced across seats. Each contains four distinct public-legal candidates evaluated under four frozen reacting continuations: 512 branches per backend. Correlated perturbations do not create additional independent families.

The candidate roles are the public controller's highest-scored immediate play, wait for the ordinary decision interval, the best play using another affordable card, and a meaningfully different legal placement of the first card, preferably displaced by at least two tiles. Preserve the controller's original recommendation as metadata, including when it recommends wait. Expose ranked public play scores with deterministic tie-breaking: the existing single-decision interface does not supply a second-ranked card, and a second-ranked tile is not a different card. Freeze root eligibility and missing-alternative handling before outcomes. An eligibility restriction such as requiring two affordable cards narrows the admitted scope and must be reported. Never replace roots after seeing outcomes or silently drop generation failures.

Use four declared continuation conditions, each a frozen ordered pair of deterministic public controller styles for (root owner, other player) drawn from balanced, pressure and defense. The default set is the 2×2 grid owner ∈ {balanced, defense} × other ∈ {pressure, balanced}, confirmed for non-wait coverage on scalar development roots before freezing; any three of its four cells include both owner styles and both other-player styles. The scripted controllers are deterministic, so response seeds do not create distinct continuations, and `compare_reacting_public_branches.response_styles` rejects more than one seed label without a geometry controller; the geometry controller is a random responder and is not used for this gate. The `training-readiness-v2` runner enumerates conditions × candidates × engines with one seed label per condition; the frozen v7 runner is not modified. Pair conditions across alternatives and engines; both players react to their own branch observations. These are four declared conditions, not four independent samples of general player strength. Avoid a forced 20-tick delay in this initial candidate set: it would impose a temporary controller commitment whose intervening action rights and cancellation semantics differ from a single-step decision.

Normalize own-minus-enemy remaining Crown HP margin by the root owner's initial total Crown HP at the root's declared tower levels, using full starting HP rather than HP remaining at the decision root. This is a per-player denominator: 10,928 HP at level 11, comprising two Princess Towers of 3,052 and a King Tower of 4,824, per `native_public_observation.TOWER_ANCHORS`. Use this same fixed root-owner denominator for all margin thresholds and measurement floors in that family: 1% is about 109 HP and 5% is about 546 HP at level 11. A family provides consequential non-wait coverage if two non-wait candidates differ on the reference in mean match score above the measurement floor, or in mean normalized HP margin by more than both the margin floor and 0.01. At least 16 of 32 families must meet this requirement. Otherwise the attempt is inconclusive, never passed; retain it as opened evidence before revising the generator and collecting a fresh attempt. The 1% threshold is a prospective practical coverage limit, not an estimate of native uncertainty. Play-versus-wait discrimination remains useful and is reported separately.

All 32 families remain in failure accounting, including those without non-wait discrimination. Report the informative-subset and per-class counts separately. Do not condition the systematic-bias check only on non-wait-informative roots, which would hide wait-versus-play errors. The full-design confidence bound below does not become a bound for that selected subset.

Require strict public serialization/calibration and legal transport checks, complete branches and correct terminal handling. Unknown channels remain missing. Integer native round-trip checks do not certify camera accuracy.

For decision regret, score wins/draws/losses as 1/0.5/0. Compare the scalar-preferred candidate's mean reference score with the reference-best candidate over the same continuations. Handle scalar ties pessimistically. A material failure is at least 0.25 mean match-score regret, or more than 5% of the root owner's initial total Crown HP in mean margin regret when scores tie. Require zero material failures and no missing declared cases. Zero failures among 32 independent sampled families gives an approximately 8.9% one-sided 95% upper bound for this protocol's narrowly defined failure event.

These are provisional practical tolerances, not established human-sensitivity limits. Inspect opened development distributions before freezing to estimate measurement/repetition noise and check feasibility. Do not automatically choose an acceptance percentile from the simulator's own error distribution. Any revision occurs before fresh collection and is documented.

Apply this mechanically specified systematic-bias rule, frozen before fresh outcomes:

1. Establish same-engine measurement/reproducibility floors on development roots by repeating identical candidate executions with identical states, policies, seeds and schedules in each engine. For score and normalized HP margin separately, take the larger of the maximum observed absolute repeat difference and the known serialization/rounding-error allowance, then the larger engine floor. The discrete win/draw/loss spacing is not measurement noise; a deterministic score floor can be zero. This finite development envelope is not a population confidence bound. For a stochastic response model, changing response seeds measures strategic variation and must not inflate the noise floor; seed labels alone do not vary the deterministic controllers used here. Unexpected material non-reproducibility must be resolved before freezing rather than absorbed into a permissive tolerance.
2. Use the four candidate-generation roles as fixed classes: immediate play, wait, alternate card and displaced placement. Rank scalar and reference candidates by mean match score, then mean HP margin. Assess scalar-best ties pessimistically; assess each tied class, counting a family at most once within a class. Choose one reference-best comparator by a frozen tie rule and use that same comparator across all four continuations.
3. A family counts as repeatable harm for a class if a scalar-preferred candidate in that class has mean reference match-score regret at least 0.125 and above the score floor, or, when mean scores tie, normalized mean margin regret greater than 1% and above the margin floor. Additionally, that reference comparator must be better in the relevant score/margin direction in at least three of four paired continuations. This requires support from both owner styles and both other-player styles. The four continuations are not four independent families.
4. Four independent families meeting that event for the same class automatically block admission. The existing single-family material-failure rule remains independently binding. A class exposed in fewer than four independent families has insufficient coverage for this repeated-pattern check; report that limitation rather than claiming the class has been statistically cleared.
5. Publish class exposures, event counts, regrets, sign patterns and ties, and review every above-floor event for mechanism or exploit. Review may add blocks, including a demonstrated repeatable exploit before the count reaches four; it may never remove an automatic block. A measurement repair preserves the original attempt and follows new-attempt rules rather than deleting inconvenient cases.

The 0.125 score, 1% margin and four-family constants are practical repeated-harm limits. They are not a calibrated significance test, a measured null flip probability or estimates of human sensitivity. No binomial tail with a plug-in development flip rate is used. This rule catches repeated harm below the single-family material threshold without treating every numerical ranking difference as a failure.

Absolute scalar/native winner mismatch and trajectory drift remain diagnostics. Repeatable simulator exploits can block implicated mechanics even when an aggregate metric passes. Failed or missing cases remain in the attempt; repair or scope changes require a new prospective attempt.

Tier A grants only its declared scalar/public-policy scope. Its optional teacher-search admission substage must explicitly cover oracle candidates. It does not grant camera acceptance, unrestricted search or broad simulator equivalence.

### Tier B: learned-policy transfer

Before continuation beyond the pilot or promotion, run a fresh policy-conditioned reference block from frozen candidate games, stratified by supported deck, phase and seat, using the same regret, measurement-floor and automatic-bias machinery. The proposed block uses 30 representative roots, with the frozen policy providing ranked play alternatives for the same candidate roles. At least 15 of those roots must provide consequential non-wait coverage; otherwise the block is inconclusive. Retain all roots in failure accounting. Separately run targeted probes of suspected exploits and frequent problematic patterns. Freeze candidate/root details before outcomes.

Representative sampling and targeted probes have separate reporting roles. Both can block promotion; only representative sampling supports a population-rate interpretation. Do not quote Tier A's 32-family bound for a differently sized or selected block. Newly admitted mechanics and levels require coverage appropriate to that expanded scope.

### Playing-strength evaluation

Use at least 512 paired-seat completed games per finalist against the fixed reacting pool and supported held-out deck families, balancing seats and clustering uncertainty by independent matchup/seed. Freeze checkpoints, decoder, opponent pool and evaluation roles before the final block.

Advance when the candidate improves mean match score over initialization by at least 0.05 with the 95% interval above zero, beats the fixed scripted pool overall, has no material declared subgroup collapse, and passes Tier B. Require corroboration in at least two of three training seeds for a claim about the training recipe. Keep nominal levels, held-out deck families and mixed-level combinations visible as separate slices.

The numeric subgroup-collapse definition and supported slice table are frozen with the evaluation configuration before outcomes. The council has accepted this prospective requirement; Fable's suggested absolute 0.40 floor and the alternative in Astra Round 4 are non-blocking recommendations, not additional requirements imposed by this version. Account explicitly for nominal versus deliberately disadvantaged level conditions when finalizing the evaluation configuration.

Log accepted/rejected commands, intervention, observation/action latency, disconnects and outcome-graded tactical reactions. Waiting and defensive-action frequencies are situation-conditioned collapse diagnostics, not promotion quotas. A level or board intervention need not change the optimal action in every state.

Human-level claims ultimately require an identified human cohort, comparable decks/levels, frozen weights, full recordings and measured observation-to-action latency. Scripted-pool wins and native reference checks remain intermediate evidence.

## First implementation milestone: M0

M0 produces a trustworthy learning path and frozen entry protocol, without fitting a gameplay policy. Preserve existing source changes and evidence throughout.

1. Complete the public contract. Carry entity levels/confidence and own hand/next-card/tower levels through `structured_obs.py`, `public_observation.py`, `public_policy_contract.py`, `model.py`, rollout storage/builders in `train_recurrent.py`, `parallel_rollout.py`, `shared_rollout_ipc.py`, imitation input builders and `eval.py`/inference. Version the contract/checkpoint. Verify shapes, dtypes, missingness, masks and round trips.
2. Complete simulator level plumbing. Connect `player.py`, `deck_pool.py`, `battle.py` and `selfplay_env.py` to the existing scaling functions, retaining level-11 defaults. Check emitted observations against the actual card/tower stats. Extend teacher metadata where mixed-level labels will be used.
3. Enforce actor hygiene. Mask to the observable feature subset, zero previous rewards in every domain and separate critic/auxiliary labels. Remove the illegal-action penalty for this lineage while logging failures. Verify hidden-state invariance and causal masks.
4. Verify recurrent PPO. Test behavior/update log-prob equality on the scalar backend, legal factorization, chunk/burn-in versus uninterrupted inference, episode reset, terminal/truncated bootstrap and critic isolation. Disable defense scenarios in the pilot. Synthetic optimizer checks are permitted; gameplay fitting is not.
5. Fix data/deck roles. Group procedural derivatives with parents, prepare the 16-card distribution and independent splits, and define immutable training/development/acceptance roles. Build a complete-game scripted demonstration adapter. Verify the structured oracle collection interface without launching oracle search or label production before admission.
6. Implement the separate readiness evaluator and protocol. Add the ranked public-candidate interface, consequential-coverage accounting, identical-execution repetition study and automatic per-class bias rule specified above. Inspect opened development data for design/noise analysis, freeze rules and pins, and preserve all historical evaluator/ledger behavior. Include the optional teacher-search admission order explicitly.
7. Benchmark the actual path. Use an untrained actor and real observation/rollout shapes on the chosen CPU/GPU machine. Measure full games/hour, retained learner decisions/sec, p95 inference, update cost and memory. Historical random-action or simple-gym microbenchmarks are not substitutes. Do not run the oracle tournament during M0 before its gate.

M0 completes when focused checks pass, one public sequence survives collection, supervised input construction, PPO input construction and inference with levels/confidence/masks/recurrence intact, benchmark evidence is saved, and the prospective protocol is frozen. Then perform Tier A under the coordinator's execution authorization. After admission, run the correctness smoke and main learning experiment. Teacher qualification is a separate admitted step, not an M0 completion dependency.

Useful existing modules include `model.py`, `structured_obs.py`, `public_action_mask.py`, `public_policy_contract.py`, `train_recurrent.py`, `parallel_rollout.py`, `imitation.py`, `eval.py`, `strategy_bots.py`, `public_scripted_opponent.py`, `oracle_planner.py`, `deck_curriculum.py`, `reward_model.py`, `public_reference_checks.py`, `calibration_families.py` and the reacting-branch comparison scripts. Reuse requires the contract updates above. No verifiers orchestration migration or runtime rewrite is needed for this milestone.

## Scheduled follow-on work and decision rules

The continuous-time likelihood is the first policy-head experiment after pilot analysis and before the broad league stage. Integrate `event_policy.py` into collection, imitation, PPO and inference without coupling it to structured memory. Keep the categorical actor as control. Verify normalization, legal masks, gradients, replayed likelihood and survival probability under subdivision of a fixed-rate interval. Five-versus-ten-tick games measure practical sensitivity; changed information/reaction opportunities preclude a blanket promise of behavioral invariance.

Design the visible-status contract extension during the pilot. Stun, slow, freeze and deployment cues require causal definitions, native/video validation and confidence/missingness. Do not expose hidden timers because an effect is visually recognizable. Add measured correlated perception errors and control latency before real deployment.

If both mandatory initialization arms fail with correct updates after five million decisions, diagnose exploration, credit assignment, opponent difficulty and representation before increasing capacity. Give the strongest supported revision a replicated follow-up. If warm-start behavior dominates early but plateaus, reduce anchoring and improve opponent diversity. If failures arise from placement resolution or missing history, fix the interface. If reference checks reveal an exploit, repair or isolate the mechanic before rewarding more of it. Candidate-value/search distillation is a later challenger under its own admission and strength comparison; a learned world model is not part of the initial strategy.

## Compute and operation

Start with one GPU learner, about 64 CPU cores for scalar actors and remote scratch/object storage. A two-hour benchmark on the actual machine determines the bottleneck. The Mac coordinates and hosts reference tooling; no assumption is made that remote native emulation is already verified.

The first ceiling for the two mandatory arms, including evaluation, is 72 GPU-hours and 4,608 CPU core-hours. Allow a proportional additional envelope for the qualified oracle arm: up to 36 GPU-hours and 2,304 CPU core-hours. These are spending ceilings, not throughput promises. If the decision target cannot fit, report achieved experience and profiling before expanding the envelope.

After useful learning and transfer evidence, the proposed broader league ceiling is two GPU learners and 128 CPU cores for seven days: at most 336 GPU-hours and 21,504 CPU core-hours, targeting three 30-million-decision replicas. Use fewer resources when the actor underutilizes the accelerator. Retain restartable jobs, rolling trajectories, selected atomic checkpoints and durable evaluation evidence. Optional tensor acceleration must establish full workload coverage and parity before replacing scalar actors.

The grant removes the old Mac-only resource premise. It does not convert this discussion document into permission to launch jobs. No automatic bulk video extraction or large accelerator cluster is required.

## Same-version approval status

Astra explicitly endorses candidate v2. Fable's final verdict, as relayed by the coordinator, accepts the existing strategy and its six prior approval points, conditional only on defensible consequential-candidate coverage and a same-engine-floored automatic per-class bias rule that review cannot waive. This revision incorporates both with the controller and statistical corrections described above.

The architecture, initialization arms, objective, budgets, teacher ordering and timing/status schedule are unchanged. No mandatory 0.40 subgroup floor, 16-family teacher cap, shaping test or additional experimental arm has been introduced from the non-blocking recommendations.

Fable must review and approve this exact version's SHA-256 before it is marked jointly approved. A prior-round agreement or promise to approve the additions is not recorded as an approval of this file's final bytes.
