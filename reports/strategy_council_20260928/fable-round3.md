# Fable — Round 3: review of `strategy.md` and the changes required for approval

## Part A. Verdict on the candidate version

**Reviewed file:** `reports/strategy_council_20260928/strategy.md`, SHA-256 `06f44924ca12d6d0b60349fdeaed42257164ffad3c65475c19f1bfaa4bf8448d` (recomputed locally; matches the coordinator's value).

**Verdict: not approved as-is. Approved once edits A and B below are applied, verbatim or in equivalent wording.** Everything else in the document I accept, including all six listed approval points as framed. I checked the document's factual statements against source and they hold: the deterministic tracker and event decoder cannot combine with the LSTM configuration, `train_dagger_oracle.py` is the legacy raster path, the 16-card list matches `public_scripted_opponent.SUPPORTED_CARDS`, 32×4×4 = 512 branches, and the zero-failure bound for 32 families is 1 − 0.05^(1/32) ≈ 8.9%.

The two edits are protocol content inside Tier A. Neither changes architecture, arms, budget, ordering or the approval points. Edit A is backed by new measurements from the opened v7 roots (design use only; table in §B2.1). Edit B makes two details of the already-agreed systematic-bias rule explicit so the freeze has content.

### Edit A (required): informative families and consequential candidates

Insert after the sentence "Correlated perturbations do not create additional independent families." in *Tier A: scoped entry*:

> Candidates must be consequential alternatives, not micro-perturbations: the public-script baseline, wait, the script's second-ranked legal card, and one displaced or delayed play (at least two tiles, or a 20-tick decision-boundary delay). The exact fourth candidate is fixed by piloting the generator on scalar development roots before freezing; no reference time is spent on that pilot. A family is informative when at least two play candidates differ in mean reference match score, or in mean margin by more than the frozen noise floor; a family that separates only wait from play is not informative. A conclusive Tier A requires at least 16 of 32 informative families. Fewer is inconclusive, not passed: the attempt is opened, the generator is revised, and fresh families are collected; inconclusive families are never reused as acceptance evidence. Systematic-bias counts and Tier B use informative families as their denominator. Basis: in the 13 opened v7 roots, the four play candidates (recorded, ±1 tile, 1-tick delay) tied exactly on the reference in 6 roots and all five candidates tied in 2, so about half of v7-style families tested only play versus wait and two tested nothing.

Why this is required rather than recommended: with the v7 generator, zero material failures across 32 families would certify mostly bit-identical continuations, not decision rankings over placement and card choice, which are exactly the dimensions a learned policy varies. The same requirement applies to Tier B's candidate set.

### Edit B (required): two sentences in the systematic-bias paragraph

Replace "Freeze the noise calculation, multiplicity handling and adjudication rule in the protocol before outcomes." with:

> Derive the noise floor from same-engine repetition of identical candidates on development roots with additional response seeds, not from cross-engine error, which was zero on every opened branch and would make the floor degenerate. The block is automatic once the frozen per-class count is reached; adjudication classifies mechanisms and may add blocks but never removes one. Freeze the noise calculation, per-class counts, multiplicity handling and adjudication rule in the protocol before outcomes.

The draft mechanics I would use for the frozen constants are in §B2.2; any constants that keep the floor same-engine and the block automatic are acceptable to me.

### Recommendations (not blocking)

1. Bound the teacher-search admission substage at ≤16 fresh families reusing the Tier A machinery, so it cannot grow into a second campaign.
2. Add to M0 item 4 a unit test that the per-episode shaping sum equals −Φ(s₀) under gamma 1 and zero terminal potential; this is the identity that makes the shaping policy-invariant and it replaces the correctness role of a terminal-only arm.
3. For the subgroup-collapse definition frozen with the evaluation configuration, my default proposal stands: any fixed-pool opponent or declared held-out slice below 0.40 mean match score at ≥512 paired games, or a ≥0.10 decline versus initialization with the 95% interval excluding zero. I accept the document's process (frozen before outcomes) and any alternative constants Astra proposes before that freeze.
4. Sam still owns two decisions the document correctly does not assume: the bounded emulator restart for Tier A, and the content-policy question on video extraction.

**Commitment.** When a revised `strategy.md` contains edits A and B, I will approve it by its new SHA without further conditions. If Astra disputes either edit, the specific disagreement to resolve is whether a Tier A pass may rest on families that cannot distinguish play alternatives, and whether a bias trigger may be resolved by discretion; I hold that the answer to both is no.

---

# Part B. Rationale: response to Astra Round 3

This section is the review of Astra Round 3 written before `strategy.md` arrived; it records what I accepted and the evidence behind the required edits. Settled points from Rounds 1–2 carry forward unchanged. No implementation, collection or fitting occurred; v7, its evaluator, ledgers and exposures are untouched.

## B1. Astra Round 3 items accepted, with reasons

- **Focused pilot.** Two mandatory arms (scripted warm start, none) × 3 seeds × 5M learner decisions; the oracle arm adds 15M only if qualified; checkpoints at 1M and 5M; a ≤100k-decision smoke after admission is a software check and never evidence about a method. I withdraw the factorial.
- **Gamma-1 primary objective** with a small fixed potential term and zero terminal potential, GAE 0.95; gamma 0.999 and terminal-only are follow-up ablations. Under gamma 1 with Φ(terminal)=0 the shaping sum telescopes to −Φ(s₀) per episode, so its policy-invariance is an identity that a unit test can verify (per-episode shaping sum equals −Φ(s₀) on recorded rollouts). That test replaces the correctness role I wanted from a terminal-only control arm.
- **Teacher screen and search-admission order.** 64-game screen, 256-game confirmation, ≥0.05 mean match-score advantage over the strongest script with the 95% interval above zero, uncertainty by independent match seed. Tier A precedes all fitting; the oracle's candidate scope is admitted through a declared teacher-search substage on fresh reference roots before any distillation labels exist; if not admitted, the two mandatory arms run alone. Oracle labels stay soft (`kl_regularized_candidate_target`); near-ties are never hard actions. I ask only that the substage be bounded in the protocol (≤16 fresh families, reusing the Tier A machinery) so it cannot grow into a second campaign.
- **Stochastic evaluation at temperature one with fixed RNG seeds** as the default, deterministic decoding as a separately identified candidate frozen before acceptance outcomes. This is better than my Round 2 default: it evaluates the object PPO optimized and avoids the play-gate argmax aggregation, whose slot-summing bias the model code itself documents.
- **Level schedule.** Level 11 for the first million decisions, then supported variation in half the games with a nominal half, teacher level handling extended first, level/deck combinations held out. No competence demand on out-of-scope archetypes.
- **Readiness thresholds.** 32 independent families, four candidates, four frozen reacting continuations; material failure at ≥0.25 mean match-score regret or >5% initial Crown HP mean margin regret when scores tie; zero material failures; complete cases; public checks; the ~8.9% zero-failure bound stated as covering only the declared event. I withdraw percentile-derived thresholds: Astra is right that a percentile of observed simulator error lets a poor simulator define its own tolerance. Development distributions estimate repetition noise and feasibility only.
- **Timing.** Continuous-time likelihood integration is the first policy-head experiment after pilot analysis and before the league stage, wired from `event_policy.py` into collection, imitation, PPO and inference without structured-memory coupling, categorical actor as control. Astra's acceptance checks (normalization, legal masks, gradients, log-prob replay, equal survival probability under interval subdivision) are the right mathematical tests; five-versus-ten-tick games measure practical sensitivity only. I withdraw the word "invariance" for the behavioral comparison.
- **Visible-status extension** designed during the pilot, added only with causal observation definitions, confidence and missingness, and native plus video validation; hidden engine timers stay out. `causal_vision.py` already names freeze, shield, slow and stun cues, so the video side has a starting point; the native projection does not yet label them, which the extension must add.
- **Dynamics variation.** Level variation now; hidden HP/damage jitter only after a parameter-specific development study, with arbitrary ranges labeled robustness stress tests. Astra's identification argument is correct: tower-HP or timing residuals cannot be attributed to an HP/damage perturbation, so my residual-derived ranges would have carried a false "measured native uncertainty" label.
- **Promotion.** Activity quotas removed and kept as tactically stratified diagnostics; ≥512 paired-seat games per finalist against the fixed pool and supported held-out deck families; ≥0.05 improvement over initialization with the 95% interval above zero; overall superiority to the scripted pool; no material declared subgroup collapse; Tier B; corroboration in two of three seeds.
- **Human data and envelope.** One-day audit, held-out human-observation evaluation set, disjoint sequences, twenty clean sequences as feasibility not sufficiency, no automatic video extraction. One GPU learner and ~64 CPU cores with remote storage; 72 GPU-hours and 4,608 core-hours for the two mandatory arms with a proportional ceiling for the oracle arm; scheduling from measured end-to-end throughput; the league envelope contingent on learning and transfer; tensor execution must prove coverage and parity before replacing scalar actors. My Round 2 per-core and dollar figures were labeled hypotheses and are superseded by measurement.
- **Implementation list.** The M0 ordered scope from my Round 2 (§4 Q6) remains the file-level checklist, extended by the `hand_levels` array, the flag removing the hard-coded −0.01 illegal-action term in `SelfPlayBattleEnv.step`, and the telescoping test above.

## B2. The three additions, with evidence

### B2.1 Informative-family requirement and consequential candidates

New evidence, from the 13 opened v7 roots in `reports/v7_recovery_20260928/opened-v7-scalar-recheck/*/paired-root.json` (development data, used here only to design the protocol):

| Observation | Count |
|---|---:|
| Roots where scalar and native agree on outcome *and* HP margin for every candidate | 13 of 13 |
| Roots where all four play candidates (recorded, ±1 tile, 1-tick delay) tie exactly on native | 6 of 13 |
| Roots where all five candidates including wait tie exactly | 2 of 13 |
| Roots that discriminate among play candidates (2–4 distinct native results) | 7 of 13 |

Two consequences. First, the cross-engine residual on these branches is zero, so opened data cannot supply a cross-engine noise floor; a floor must come from same-engine repetition (§B2.2). Second, and more important, under the v7 candidate generator roughly half of the families tested only play-versus-wait and two tested nothing at all: a ±1-tile or 1-tick perturbation frequently produces a bit-identical continuation. Zero material failures across 32 such families would be weaker evidence than the 8.9% bound suggests, and `docs/design/CALIBRATION_PROTOCOL.md` already states that fixed no-more-play branches cannot satisfy the ranking gate by themselves.

Proposal for the protocol text:
1. A family is **informative** if, on the reference, at least two *play* candidates differ in mean match score, or their mean margins differ by more than the frozen noise floor.
2. A conclusive gate requires ≥16 of 32 informative families. Fewer means **inconclusive**, not passed: those families are opened, the generator is revised, and fresh families are collected. Inconclusive families are never reused as acceptance evidence.
3. Candidates are consequential alternatives rather than micro-perturbations: the public-script baseline, wait, the script's second-ranked legal card, and either a displaced placement (≥2 tiles, for example the other side of the lane) or a decision-boundary delay (20 ticks). The exact fourth candidate is chosen by piloting the generator on development roots until informativeness reaches ~60%, then frozen.
4. Systematic-bias counts (§B2.2) and Tier B use informative families as their denominator.

This adds no native time; it is generator and evaluator work inside M0 item 7.

### B2.2 Mechanical form of the noise-aware systematic-bias rule

I accept Astra's structure: a predeclared review trigger, an admission block when a candidate class shows a repeatable harmful reversal above a development-derived noise floor across independent families and continuations, and frozen noise-floor, multiplicity and adjudication rules. "Any strict regret in more than 8 of 32" is withdrawn. So that the freeze has content, I propose this draft:

- **Noise floor.** On development roots, rerun each candidate's scalar continuation with at least four additional response seeds; the 95th percentile of the absolute score and margin differences between repetitions of the *same* candidate defines δ_score and δ_margin. Same-engine repetition, not cross-engine error.
- **Above floor.** A family counts against class *c* when the scalar-preferred candidate belongs to *c*, its mean native regret exceeds max(δ_score, 0.125) or its tie-break margin regret exceeds δ_margin, and the regret has the same sign in at least three of the four continuations.
- **Block rule.** For each class, k_c is the smallest count with P(Binomial(n_c, p₀) ≥ k_c) ≤ 0.05 divided by the number of classes, where n_c is the number of informative families in which *c* was scalar-preferred and p₀ is the frozen null flip rate measured from the same-engine repetition study. Reaching k_c blocks admission automatically.
- **Adjudication.** Review classifies the mechanism and may add blocks; it can never remove one. Per-class tables are published whether or not any trigger fires.

If Astra prefers different constants, I will accept any version that keeps the block automatic and the floor same-engine.

### B2.3 A numeric definition of "material subgroup collapse"

Promotion language needs a number frozen before evaluation. Proposal: a material collapse is any fixed-pool opponent, or any declared held-out deck family or level slice, with mean match score below 0.40 at ≥512 paired games, or a decline of ≥0.10 versus initialization in any declared slice with the 95% interval excluding zero. Alternative constants are fine; the definition must exist before outcomes are seen.

## B3. Agreement statement as written before `strategy.md` arrived

With §B2.1–§B2.3 incorporated, or equivalents Astra proposes that preserve the informative-family requirement, an automatic same-engine-floored bias block, and a pre-declared collapse definition, I explicitly agree to the joint strategy and will approve the consolidated `strategy.md`. The remaining disagreement between us is now confined to protocol constants, which the plan already says are frozen after the development noise estimate and before fresh collection. Two decisions still belong to Sam: authorizing the bounded emulator restart for Tier A, and the content-policy question on video extraction. v7, its evaluator, ledgers and exposures remain untouched.
