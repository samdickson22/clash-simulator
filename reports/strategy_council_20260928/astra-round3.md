# Astra, Round 3: proposed final reconciliation

I agree to the shared architecture and overall strategy in Fable Round 2: a fresh public-information entity/LSTM actor, scripted initialization with an empirically qualified oracle challenger and a from-scratch control, recurrent PPO, then broader-deck league training. The grant funds replicated learning and evaluation. Human observations and better runtime throughput proceed alongside that work. Search must earn its teaching role.

I can sign the concrete reconciliation below. This carries forward our settled points rather than restating them. It does not claim Fable has already accepted these final resolutions. The remaining changes to Fable's proposed common plan concern experiment size, admission ordering and evaluation semantics, not a competing architecture.

## 1. Settle the teacher question with a conditional third arm

Accept Fable's correction that `imitation.py collect` supplies a structured oracle collection path. My criticism of `train_dagger_oracle.py` remains correct but does not imply that a new oracle collector must be written from scratch. Review the existing structured path against the new observation contract before reuse.

The main comparison is scripted warm start versus no warm start. Add an oracle warm start only after it passes a teacher screen. Use 64 paired-seat games as a cheap screen, followed by an independent 256-game confirmation if promising. Compare against the same frozen reacting opponent pool and strongest scripted baseline; admit the oracle if its match-score advantage is at least 0.05 with a 95% interval above zero. Score uncertainty by independent match seed, not by treating both seats as unrelated samples.

A privileged teacher passing that test has established player strength, not student learnability. The oracle-initialized student must still win the same replicated PPO comparison. Preserve public-history ambiguity and uncertain labels; do not turn near-tied search outcomes into mandatory hard actions.

Resolve the gate circularity explicitly. Tier A precedes fitting. Its frozen protocol may additionally admit a bounded teacher-search evaluation after public/ranking checks cover that teacher's candidate scope. Validate oracle-selected candidates on fresh reference roots before generating distillation labels. This is a declared search-admission substage, not an exception hidden under “teacher measurement.” If that scope is not admitted, defer the oracle arm and run the other two. Tier B remains the learned-policy continuation/promotion gate; it cannot also be the sole prerequisite for the teacher that initializes that policy.

## 2. One focused pilot, not the full factorial

Use one reward specification initially: terminal match score plus a small fixed potential-based term, gamma 1, zero terminal potential, GAE lambda 0.95. This preserves the finite-game competitive objective. Gamma 0.999 and terminal-only reward are follow-up ablations if credit assignment or shaping becomes the suspected limitation. They need not double the first experiment.

Run three seeds per admitted initialization for five million learner decisions each. Two mandatory arms total 30 million decisions; the qualified oracle adds 15 million. Preserve the one-million-decision checkpoint as a diagnostic and the five-million checkpoint for comparison. A 100,000-decision smoke after admission is a software check, never evidence against a learning method.

Carry forward the corrected LSTM configuration, five-tick cadence, full stochastic action likelihood, public history, reward-input zeroing, level plumbing, parent-grouped splits and recurrent correctness work. Default evaluation uses the same stochastic policy at temperature one, with fixed evaluation RNG seeds. A deterministic decoder is a separately identified candidate; do not change decoders after looking at acceptance outcomes.

Use the first million decisions at level 11. Then introduce supported level variation in half the games, preserving a nominal half. This makes mixed-level adaptation part of the chosen strategy rather than another large factorial. Extend teacher level handling before using mixed-level teacher labels. Broader mechanics/deck admission follows the pilot; do not demand competence against unsupported held-out archetypes in the 16-card experiment.

## 3. Readiness must catch meaningful systematic errors

Accept a separate versioned evaluator and protocol. Preserve v7 and its evaluator unchanged. Adopt my Round 2 refinement: 32 independent families, four candidates and four frozen reacting continuations, rather than two. Material failure means at least 0.25 mean match-score regret, or more than 5% initial total Crown HP in mean margin regret when scores tie. Require zero material failures, complete cases and passing public checks. These are provisional engineering tolerances, frozen before fresh outcomes, with the narrow approximately 8.9% zero-failure bound stated honestly.

I accept Fable's demand to inspect opened development distributions before freezing. I do not accept setting the acceptance threshold automatically to a percentile of observed simulator error. That can make a consistently poor simulator define its own acceptable error. Use those distributions to estimate measurement/repetition noise and check threshold feasibility; retain separately chosen practical regret limits. If development demonstrates that a proposed limit is inappropriate, revise it before collection and document why.

I share the concern about small systematic bias, but “any strict regret in more than 8/32 families” is too sensitive to arbitrarily small differences. Make it a predeclared review trigger. Block admission when the affected action class has a repeatable harmful ranking reversal exceeding the development-derived noise floor across independent families and reacting continuations. Publish candidate-class results and investigate every trigger before admission. A tiny numerical ordering difference alone is insufficient. Freeze the noise-floor calculation, multiplicity handling and adjudication rule with the protocol; do not choose them after fresh results.

Tier B uses fresh roots from the frozen candidate's games. Separate randomly sampled representative roots from targeted exploit probes. Both can block promotion, but only the former support a population-rate statement. Absolute winner mismatch remains diagnostic. This is the policy-focused fidelity standard on which we agree.

## 4. Accept scheduled timing/status work; reject unjustified jitter

I accept a concrete schedule: the continuous-time likelihood integration is the first policy-head experiment after the pilot analysis and before the broad league stage. Wire the standalone `event_policy.py` distribution into collection, imitation, PPO and inference without structured-memory coupling. Keep the categorical actor as the control.

Its mathematical acceptance checks should verify likelihood normalization, legal masks, gradients, log-prob replay and equal survival probability when an unchanged rate interval is subdivided. Five-versus-ten-tick games test practical sensitivity. They cannot establish exact behavioral invariance when different observation cadences expose different information or permit different reactions. Do not promise that stronger property.

I also accept a named visible-status contract extension, designed during the pilot. Add stun/slow/freeze/deployment cues only with causal observation definitions, confidence/missingness and native/video validation. “Visible in principle” does not authorize exposing hidden engine timers. Contract numbering is an implementation detail; the extension is explicitly on the schedule.

Level randomization proceeds now as above. Hidden HP/damage jitter waits for a small parameter-specific development study. Tower-HP or timing residuals cannot uniquely identify an HP/damage perturbation: movement, targeting and timing errors can cause those same residuals. We can later run a coherent episode-fixed balance-variation arm, but must label arbitrary ranges as robustness stress tests, not measured native uncertainty. This study can proceed alongside the pilot without blocking it.

## 5. Promotion and grant envelope

Remove mandatory no-op and defensive-action-frequency thresholds. Keep them as diagnostics stratified by tactical context. Correct defense can require waiting. Promote on completed-game strength and reliable execution, not on how often the policy acts.

For finalists, use at least 512 paired-seat games against the fixed pool and supported held-out deck families. Require at least 0.05 mean match-score improvement over initialization with the 95% interval above zero, overall superiority to the fixed scripted pool, no material declared subgroup collapse, and Tier B passing. Require corroboration in at least two of three training seeds for a recipe claim. Keep random/no-op opponents as controls. Interventions should test appropriate outcome-sensitive responses; changing a level need not change the optimal action in every position.

Accept the one-day human-data audit and a held-out human-observation evaluation set. Twenty clean sequences demonstrate feasibility, not sufficiency for a broad imitation prior. Training and evaluation sequences must be disjoint; low-weight supervision still requires reliable labels.

Use one GPU learner and about 64 CPU cores initially, with remote storage. Retain the proposed 72 GPU-hour/4,608 CPU-core-hour ceiling for the two mandatory arms; allow a proportional additional ceiling for the qualified oracle arm. Derive actual scheduling from measured end-to-end throughput, not historical per-core extrapolations or unsupported dollar estimates. The later two-GPU/seven-day league envelope remains a ceiling contingent on useful learning and transfer. No automatic video-extraction job is part of this plan.

The throughput work may proceed alongside learning, but scalar actors plus GPU learning are sufficient to start. Tensor execution must demonstrate workload coverage and parity before replacing them.

## Agreement status

I explicitly agree to this reconciled strategy. My prior that scripts are the better first teacher need not be shared; the qualified third arm resolves that uncertainty without blocking the main experiment.

Joint agreement is pending Fable's acceptance of these specific changes: the focused two-or-three-arm pilot, gamma-1 primary objective, explicit teacher-search admission order, four-continuation regret gate with a noise-aware systematic-bias review, removal of activity quotas, and parameter-grounded rather than residual-inferred dynamics variation. Timing and visible-status scheduling are accepted. I see no remaining need for another architecture proposal.
