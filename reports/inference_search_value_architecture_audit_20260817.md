# Clasher inference search and value architecture audit — 2026-08-17

## Decision

Keep the accepted policy **search-free at live inference**. The repository has
useful exact branching, cloning, oracle, public-outcome, and action-ranking
infrastructure, but every controller tried so far either regressed matched games,
was neutral after fresh evaluation, or depends on simulator-private information
that is unavailable in a real match.

Search remains valuable in two roles:

1. offline counterfactual teacher and failure diagnosis; and
2. a future, selectively invoked controller only after it is actor-visible,
   belief-conditioned, batched through the accepted tensor simulator, calibrated
   on terminal counterfactuals, and strictly better than a cheap learned reranker.

Do not attach the current state-value search, location lookahead, Thompson oracle,
or public action-value head to the live policy.

## Evidence inspected

- `src/clasher/rl/value_guided_search.py`
- `src/clasher/rl/location_lookahead.py`
- `src/clasher/rl/oracle_planner.py`
- `src/clasher/rl/action_value.py`
- `src/clasher/rl/counterfactual_corpus.py`
- `src/clasher/battle.py`
- `reports/student_state_generalization_search_seed1058201/decision.md`
- `reports/student_state_action_value_seed1061301/decision.md`
- `reports/rl_v2_training.md`
- `reports/simulator_optimization_f872.md`
- the active read-only PyTorch worktree's
  `reports/pytorch_simulator_audit_20260814.md`, current oracle ingress, resident
  fork primitives, and production benchmark gate

No training, evaluation, benchmark, checkpoint mutation, or production-source
edit was performed. A PyTorch resident movement parity test was already consuming
one CPU while this source audit ran, so no timing loop was started.

## Current stack and disposition

| Component | Current implementation | Evidence | Decision |
| --- | --- | --- | --- |
| Exact snapshot | `BattleState.clone()` deep-copies mutable battle/RNG state while sharing frozen card definitions | Six-tower snapshot about 9.96 ms to 0.359 ms; shallow oracle 114.65 ms to 53.85 ms with identical actions | Keep; exact enabling infrastructure |
| Fixed-depth oracle | Joint two-player Thompson bandits; default depth 10, 48 simulations, up to 96 sampled actions; heuristic leaf potential | Stable-root fixed an unvisited-root-arm defect, but imitation from its labels did not improve gameplay reliably | Offline teacher/diagnostic only |
| Recurrent state-value reranker | Up to six root actions, recurrent rollout, separate terminal-outcome head, minimum-gain and optional base-risk gates | Validation 15-5 to 17-3 and first heldout 5-3 to 7-1, then win-to-loss failures on expanded heldout and fresh quarantine | Reject controller; keep outcome head as diagnostic |
| Location-only lookahead | Preserve policy card/time; clone top locations, advance 32-96 ticks with no opponent deployment, score defense-v2 potential | Guarded version was neutral 48-48 on fresh validation plus heldout, changed only 0.01%-0.05% of decisions, and raised historical wall time 896.2 s to 1108.8 s | Close current no-response family |
| Learned public action-value head | 26.7K-164.5K parameter action-conditioned rankers over frozen public policy features | Best 64-wide head had 56.52% validation pair accuracy; smoke improved, but Graveyard win became loss and Graveyard/X-Bow stayed unused 0/4 | Reject all three fitted heads |
| Full-reset terminal counterfactuals | Replay from battle start after one changed action, then verify terminal result | Often finds genuinely winning single-action alternatives; localized repairs have produced exact improvements, while dense/global repairs frequently caused collateral regressions | Keep for data and diagnosis, not online selection |
| Tensor simulator | Resident tensor state/forks and oracle backend ingress exist in the separate PyTorch worktree | Completion criterion remains full enabled closure, zero fallback, exact differential gates, and lower 95% CI at least 2x for rollout plus oracle; no accepted production claim yet | Do not design latency promises around it yet |

## Critical real-play boundary

The current `RecurrentValueGuidedSearch` is not actor-visible end to end:

- it builds observations and legal masks for both players from the exact cloned
  environment (`value_guided_search.py:159-190`, `365-397`);
- its nonterminal outcome estimate consumes paired features from both player
  perspectives (`265-293`); and
- its opponent continuation receives the exact opponent action mask
  (`329-348`, `420-426`).

Each player legitimately knows its own hand and elixir inside a simulator match,
but the searching player does not know the opponent's private view in a live
match. Taken together, the paired observations expose both private sides. This
does not invalidate offline evaluation or teacher collection. It does invalidate
the current implementation as a live controller.

The fixed-depth oracle is even more explicitly privileged: legal actions for both
players are derived from the complete `BattleState`, and both joint actions are
planned at every tree depth (`oracle_planner.py:135-203`, `208-239`). That is
appropriate for a privileged simulator teacher, never for live inference.

`LocationLookahead` avoids reading hidden opponent state only by assuming no new
opponent action for its short horizon (`location_lookahead.py:27-34`, `112-123`).
The assumption, rather than information leakage, is why that family fails to model
real counterplay.

Any future live search must be initialized only from:

- current public visual state;
- the player's own hand, Next, elixir, and model-owned recurrent state; and
- a distribution over opponent-private state/actions inferred from public play
  history, never the simulator's true opponent hand, cycle, or elixir.

## Why the tried value controllers failed

### Observational value is not counterfactual value

The selected public outcome head was a competent observational predictor:
heldout AUC 0.746 and paired heldout AUC 0.806. Yet its search changed a known win
into a loss, and even the emergency gate that overrode only when base predicted
win probability was at most 0.65 failed on a fresh 395-deck quarantine. Branches
after an alternative action are off the frozen policy's data distribution. A
state-value model can rank familiar states while assigning the wrong causal
effect to an intervention.

### The action-conditioned correction was real but underpowered

The subsequent experiment did train the right object in principle: an
action-conditioned ranker on exact terminal preferences. The data, however, had
only 369 train roots, 205 validation roots, 1,519/874 pairwise preferences, and
40/16 decisive improvements. All three widths stayed around 55%-57% pair
accuracy. The 64-wide controller made a good smoke improvement, then regressed a
heldout Graveyard game and did not fix the weak-card behaviors it targeted.

This rejects the current frozen-feature sparse-ranker recipe. It does not prove
that terminal counterfactual preferences are useless. The stronger next use is a
conservative actor update with preference/KL training and abundant base-optimal
anchors, or a much larger uncertainty-calibrated reranker trained from a fresh
lineage.

### Short public-board potential misses responses and delayed consequences

Two-location/32-tick and four-location/64-96-tick lookahead can see immediate
geometry, but not the opponent's next deployment, full push development, card
cycle, or recurrent trajectory. A tuned 0.002 gain threshold removed known
development regressions and then delivered exactly 48-48 on fresh validation and
heldout games. It also cost about 23.7% more historical evaluation wall time.
More thresholds or a slightly longer horizon are not a new hypothesis.

### Oracle quality, not only oracle speed, is limiting

`FixedDepthThompsonOracle` backs up the shaped `reward_win_prob_p0` leaf after a
small number of decision intervals, rather than a terminally calibrated value.
Stable root candidates fixed the concrete unsimulated-final-arm defect, but the
resulting DAgger fits still did not beat their gameplay control. Clone speedups
made the planner about 2.13x faster in the shallow fixed probe without fixing
labels. Faster wrong or weakly causal labels are not a promotion.

## Architecture decision registry

### S0. No online search

**Status:** retained control and current live recommendation.

**Reason:** it is the only option with no hidden-state dependency, no search
latency, and no demonstrated controller regression.

**Rejection condition:** replace only when a candidate passes all visibility,
causal-ranking, latency, fresh-quarantine, weak-card, and complete-game gates
below.

### S1. Heuristic location lookahead

**Status:** rejected in its current no-opponent-response form.

**Smallest legitimate reopen:** none on another `(top_k, horizon, threshold)`
sweep. Reopen only with sampled public-belief opponent responses and a terminally
calibrated leaf.

**Immediate rejection:** any candidate still freezes the opponent through the
horizon, tunes a threshold on changed trajectories, or merely reduces the override
rate toward zero.

### S2. Generic state-value reranking

**Status:** rejected as a causal controller; outcome head retained for reporting.

**Smallest legitimate reopen:** a direct comparison on the same terminally
labeled counterfactual roots between state value, action-conditioned value, and
realized branch return. The state-value arm must match action-value ranking, not
just outcome AUC.

**Promotion metric:** deck-disjoint pairwise action-order accuracy and regret;
observational AUC/Brier alone cannot promote.

### S3. Learned action-value reranker without simulation at inference

**Status:** promising class, current implementation rejected.

**Smallest discriminating A/B:** from a fresh actor lineage, collect at least
10,000 deck/signature-disjoint roots with the base action plus one legal candidate
per hand card, no-op, and ability (maximum six). Use common continuation seeds and
terminal lexicographic labels. Compare:

- control: frozen actor;
- A: current single public action-value head;
- B: three-head ensemble plus actor sequence features, trained with pairwise
  terminal preference and explicit base-optimal anchors; and
- C: conservative preference update to the actor under a recurrent KL/BC anchor.

This experiment is GPU-cheap relative to simulator collection. Its purpose is to
decide whether a cheap learned controller captures the useful part of search.

**Offline gate:** on untouched decks and archetypes:

- pairwise accuracy at least 65% and at least 8 percentage points above the
  current 56.52% reference;
- at least 25% reduction in chosen-action terminal regret versus the actor;
- lower 95% confidence bound of positive-override precision at least 75%;
- no archetype with negative mean terminal preference; and
- weak-card action coverage for Giant, Graveyard, Lava Hound, X-Bow, Royal Hogs,
  Battle Ram, Goblin Barrel, and Hog, not just aggregate accuracy.

**Reject:** another small corpus, a threshold that produces fewer than 25
untouched overrides, any targeted card remaining unused, or any heldout
win-to-loss flip.

### S4. Selective tactical simulation search

**Status:** defer until the PyTorch simulator passes its own acceptance gate.

**Candidate design:** belief-safe batched root search, not the current sequential
paired-private implementation.

1. Generate at most six controlled-player roots: base; strongest legal candidate
   for each other hand card; no-op; ability. Add a second spatial location only
   when the location distribution is genuinely multimodal.
2. Sample opponent-private particles from public card history/cycle/resource
   belief. Never copy the true opponent-private simulator state.
3. For each particle, sample a small opponent-response ensemble (human-clone,
   current league policy, and conservative tactical response) with common RNG
   across controlled actions.
4. Advance all branches as one resident tensor batch for 8-16 decisions or an
   earlier tactical event boundary.
5. Score with an actor-visible terminal-outcome ensemble and use a conservative
   lower confidence bound. Override only when every reasonable response model
   supports the gain.

**Smallest A/B:** 2,000 untouched tactical roots; six actions x four hidden-state/
opponent particles x two RNG samples = at most 48 branches per root. Compare no
search, the learned reranker from S3, and simulated reranking at horizons 8 and
16 decisions. A 32-decision/terminal subset is the authority for horizon bias.

**Search gate:** simulation search must beat the cheap S3 reranker by at least
five points of pairwise accuracy or 15% relative terminal-regret reduction.
Otherwise keep the cheaper model-only controller.

**Live latency gate:** at the intended live batch/device:

- ordinary actor p95 at most 20 ms;
- queried search p95 at most 100 ms and hard maximum 200 ms;
- search on at most 10% of decisions;
- total average decision compute overhead at most 25%; and
- zero Python fallback, zero parity mismatch, and no state resynchronization in
  the measured search region.

The 100/200 ms limits reserve most of the 400 ms decision interval for vision,
transport, scheduling jitter, and action dispatch.

### S5. PUCT/MCTS with the exact simulator

**Status:** deferred behind S4; not ruled out long term.

The flat action boundary has 2,306 IDs, simultaneous opponent actions multiply
branching, and hidden opponent state turns the problem into belief-space search.
Unprioritized Thompson sampling is therefore a poor live architecture. If shallow
batched search succeeds, the next tree should use the policy as a prior, progressive
widening over card type before location, transpositions only on an exact sufficient
state key, and sampled opponent responses.

**Smallest discriminating A/B:** under exactly the same branch-transition budget,
compare one-ply batched reranking against depth-4 PUCT with progressive widening.
Promote PUCT only if it improves terminal regret by at least 15% and stays inside
the same p95 latency budget. More nodes alone are not evidence.

**Reject immediately:** use of the current quantized `_state_key` as an exact
transposition key. It omits hand/cycle and other legality-critical state, so it is
safe for the current approximate tree but not exact cache reuse.

### S6. MuZero-style learned dynamics

**Status:** ruled out for the current stage.

Clasher already has an exact simulator under active tensorization. A learned
dynamics model would add model bias, require large trajectory data, and still not
solve partial observability. Revisit only if the exact tensor simulator cannot
meet the live branch budget after full closure, and only against an exact-simulator
teacher. Do not replace an exact simulator merely to make the architecture resemble
a standard planning paper.

## Opponent modelling decision

Current search evaluations know the deterministic strategy opponent or run the
policy from the opponent's exact private view. That is useful for matched tests but
too optimistic for deployment. Three alternatives are ordered as follows:

1. **Public-belief policy ensemble:** preferred. Sample possible hand/cycle/resource
   states consistent with public history and query several frozen opponent models.
2. **Robust response set:** useful for tactical safety. Score the controlled action
   by a lower quantile or minimum over plausible responses, with a policy-prior
   floor to avoid impossible adversarial moves.
3. **Single most-likely opponent:** cheapest but rejected as the sole authority;
   confident wrong predictions will create exactly the rare catastrophic override
   already observed.

Opponent-model calibration must be evaluated separately: top-k action coverage,
hand/cycle belief coverage, resource interval coverage, and response NLL on entirely
heldout human games. Search is disabled when the true subsequent action falls
outside the response set too often for its predeclared coverage target.

## Compute scaling and H100 implications

### What is CPU-bound today

- Python `BattleState` cloning and per-entity native ticks dominate branch
  simulation.
- `BattleState.clone()` removed card-catalog copying and made snapshots 27.7x
  faster, but the shallow oracle improved only 2.13x. The remaining cost is branch
  evolution, legality, and leaf work, not checkpoint copying.
- Current main-checkout search loops candidates and simulations sequentially.
  A faster GPU does little for that Python object loop.

### What becomes GPU-friendly

- tens to hundreds of resident branches from one root;
- batched policy/opponent/value inference over those branches;
- branch selection and reductions that remain on-device; and
- concurrent root-state collection during offline counterfactual generation.

The active PyTorch branch now has tensor fork primitives and explicit oracle
backend ingress, but its current planner still clones one scalar battle per
simulation and advances simulations sequentially. Resident batched branch fanout
is an architectural requirement, not an optional final optimization.

### Acceptance boundary for the simulator dependency

Do not quote an H100 search speedup until all of these are true:

- every enabled/reachable search state is supported;
- unsupported fallbacks are exactly zero;
- complete off/shadow/on differential hashes and RNG states match;
- oracle branches remain resident from fork through reward/value projection;
- paired production rollout and oracle lower 95% confidence bound is at least
  2x, matching the simulator worktree's existing gate; and
- a branch-batch scaling curve identifies the batch size where CUDA overtakes
  CPU, including transfer and synchronization time.

An H100 is most valuable for running many branches or many independent
experiments. It is not expected to materially accelerate the single small actor
forward pass.

## Complete-game promotion gate for any future controller

All arms use identical decks, seeds, seats, vision/public-state inputs, and
opponent random streams. A candidate advances only in this order:

1. **Visibility audit:** no opponent-private tensor, exact hand, exact elixir, or
   true opponent recurrent state enters selection. Public belief is recomputed
   from the same causal event sequence as live inference.
2. **Counterfactual offline gate:** meet S3/S4 ranking, regret, coverage, and
   calibration thresholds on signature-disjoint roots.
3. **48-game six-strategy screen:** no baseline win becomes a loss, at least two
   losses become wins, crown differential improves by at least five, and every
   workload's crown differential is nondecreasing.
4. **96-game fresh quarantine:** no reproducible win-to-loss flip, at least four
   loss-to-win flips, at least eight additional crowns, and positive paired-score
   bootstrap lower bound.
5. **Historical and human proxy:** replay the established 168-game matrix plus
   heldout decks/archetypes and weak-card suites. Any reproducible tactical
   regression rejects; aggregate gains cannot hide a Graveyard/X-Bow/Hog usage
   failure.
6. **Latency and fallback:** meet the p95/pmax/average overhead limits on the
   intended deployment device with zero simulator fallback.

Every search report must log query reason, candidates, predicted gain and
uncertainty, hidden-state particles, opponent responses, realized subsequent
action, latency, and whether the base/candidate terminal record changed. A nearly
always-abstaining controller is a no-op, not a success.

## Ranked roadmap

1. **Do not add online search to the current accepted policy.** Preserve a clean
   no-search deployment baseline.
2. **Use exact full-reset counterfactuals as offline evidence.** They have the best
   record of finding genuinely winning interventions, but keep fitting global
   policy changes conservative and recurrently anchored.
3. **Before collecting more search data, freeze the causal interface.** Define an
   actor-visible root state and public-belief opponent particle format shared by
   vision, policy, corpus, and evaluator.
4. **Run the larger S3 preference experiment.** It is the cheapest way to test
   whether terminal counterfactual knowledge can improve decisions without live
   simulation.
5. **Wait for the tensor simulator's independent acceptance gate.** Then implement
   resident branch batching and run the bounded S4 A/B, rather than porting the
   existing private-state sequential search.
6. **Only if S4 beats S3, test PUCT under an equal transition/latency budget.**
7. **Do not pursue MuZero, more no-response location thresholds, a generic state
   value as Q, or a full-strength always-on search controller.**

The likely mid-ladder path remains a stronger policy plus better causal training
data. Search is a later tactical amplifier, not a substitute for card use,
defense, opponent belief, or a calibrated actor.
