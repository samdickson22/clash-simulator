# Astra, Round 1, September 28

I recommend a compact entity-attention/LSTM actor, bootstrapped with public scripted demonstrations, then synchronous recurrent PPO against frozen reacting opponents. Pursue compatible human observations alongside it, but do not make modern replay reconstruction the prerequisite for our first learned player. This is a proposed change to the human-imitation-first default, not consensus or training authorization.

The first empirical question is whether a small learned policy can respond usefully to changed boards and improve beyond its initialization within a measured local budget. Human-level strength remains the eventual objective.

## Evidence and alternatives

I inspected the required handoff/design/recovery files and the source modules named below. Existing test counts are recovery-report evidence, not tests rerun for this council. V7 remains failed; its 13 opened captures provide development evidence only. Null's 15.535.86 is the external reference, without an official-client equivalence claim.

Three materially different combinations deserve consideration:

| Combination | What it buys | Why choose or defer |
|---|---|---|
| Entity attention + LSTM; scripted warm start, then recurrent PPO | Reuses the actor, scalar environment and updater; learns timing and reactions without requiring a solved human-data pipeline | Recommended bounded experiment. Script imitation supplies elementary behavior, not expert strategy; PPO must demonstrate improvement beyond it |
| Public structured belief + candidate action-value model; reacting branch improvement and distillation | Makes local alternatives inspectable and can use expensive supervision efficiently | Strong challenger if PPO cannot improve. Requires calibrated rankings, credible opponent beliefs, and affordable branching; short scripted continuations can systematically prefer bad sacrifices |
| Spatial CNN + temporal transformer; observed-video behavioral cloning followed by offline/online improvement | Learns placements from actual human-visible states and reduces dependence on replay reconstruction | Attractive transfer route, but aligned compatible observations are the bottleneck. A new encoder plus offline policy improvement would confound architecture and data quality in the first experiment |

I would not start with a learned world model or an asynchronous league. Those introduce additional failure sources before we have a useful baseline. The hypothesis behind the recommendation is that useful tactical feedback is already available from the repaired scalar simulator. It is unproven.

## Actor, memory and controls

Use `rl/model.py::ClasherPolicy` with its existing 128-wide, four-layer attention encoder and 256-wide LSTM. Start fresh, with repair adapters, deterministic resource gates, hazard gating and action-value heads disabled. Preserve card semantics and current-hand conditioning. Compare a feedforward memory ablation only after the recurrent baseline works.

The actor receives own hand/next card/elixir, public clock and tower state, visible entities with position/health/status/level confidence, and causally observed play history. Opponent elixir and cycle are uncertain beliefs derived from that history. Never provide exact hidden hands, targets, future events, scenario IDs or simulator rewards to recurrent inputs. Set `previous_rewards` to zero. The critic may receive separately typed privileged state; actor features, masks and caches may not depend on it. Test equal public histories with different hidden states for equal actor outputs.

Reuse `structured_obs.py`, `public_observation.py`, `public_policy_contract.py` and `public_action_mask.py`. Use the reference-observable feature subset, with missing values/confidence preserved. The clean simulator-exact domain is an optimistic diagnostic, not the deployment contract. Native integer round-trip checks in `public_reference_checks.py` certify serialization, not camera accuracy.

Start at five native logic ticks, 250 ms in `battle.py`, choosing wait, current hand slot, then card-conditioned tile. `action_space.py` already exposes four slots times 576 tile centers plus wait/ability. Disable unsupported abilities through scope and legality. Sample the complete stochastic distribution during PPO and score that same distribution in updates. Keep waits interruptible at each observation. Record submission, acceptance and effective deployment separately.

The current hazard option is not a drop-in continuous-time likelihood: it requires structured memory, and `train_recurrent.py::ppo_update` conditions on the stored play gate. Therefore defer hazard timing until the categorical control works. Compare two- versus five-tick cadence at equal simulated duration later. Audit sub-tile placement loss on pulls and spell edges; add a residual head only if tile projection changes useful choices. Invalid actions must count as execution failures, not silently become tactical fallbacks.

Carry memory through complete episodes. Training chunks need burn-in or replayed prefixes and a verified reset convention. The current updater reuses stored initial states across optimization epochs; it does not establish updated-policy burn-in correctness. Keep the first updates small and verify full-sequence versus chunked likelihoods before scaling.

## Scope, levels and data

Start with the 16 base cards supported by `public_scripted_opponent.py`, spanning Hog, Giant, Prince pressure and defensive control, plus procedural substitutions. This is a bounded control scope, not adequate coverage of air, modern forms or human-level play. Expand next to air defense, splash and spawn mechanics through additional readiness cases. Do not train only Hog and postpone every other deck.

Use human-designed deck structures where they fit the roster, retain their provenance, and call altered rosters derivatives rather than professional demonstrations. Sample 60% structured decks, 30% role-preserving procedural neighbors and 10% arbitrary legal stress decks. Keep parent decks and all their derivatives in one split. `deck_curriculum.py` can generate neighbors, but its current split shuffles individual decks within archetypes and does not enforce parent grouping.

Begin the control at level 11. Then test actual supported levels 10–12, first through a narrow per-card configuration adapter and visible-level propagation. `model.py` consumes level/confidence under public contract v3, but `train_recurrent.py::RolloutBatch` and `_sequence_inputs` omit them. The scripted opponent also requires its own metadata at level 11. These are real missing interfaces, not configuration toggles. Own card levels must be explicitly represented too; visible body level alone cannot tell the actor how strong an undeployed card is.

Randomize modest timing/placement noise and supported dynamics only after measuring plausible ranges on development evidence. Keep episode-level variations fixed within a game, distinguish observation noise from changed mechanics, and hold out combinations. Do not randomize costs, targeting rules or deployment legality to disguise bugs. Test adaptation through observable consequences, with no hidden dynamics identifier supplied to the actor.

`reports/expert_replay_scope_20260913/result.json` reports zero fully compatible two-sided base/level-11 matches in the inspected 5,000, all 365,362 placements with unknown active forms, and 18,913 unattributed abilities. This does not prove the entire corpus unusable. Safe immediate uses are deck/co-occurrence analysis with forms retained, coverage planning, and explicit event-sequence tasks whose labels are actually known. Those logs are not board/action imitation pairs; unknown-form placements cannot be relabeled base cards.

Timebox a compatible observation audit to one working day: inspect existing `katacr_replay.py`, `tv_royale_public_state.py` and saved-video inputs for 20 complete sequences with authoritative actions and aligned observable state. Keep matches and both perspectives together. If unavailable, proceed with the scripted fallback after readiness passes. Fit natural wait/play exposure plus conditional slot/location likelihood, retaining all action failures and teacher identity. Do not oversample play events without correcting the timing prior. Later add verified human examples as a separate ablation; no historical checkpoint becomes an expert by filename.

## Prospective readiness, without repeating v7

The current `calibration_decisions.py::root_metrics` makes any selected candidate's scalar/native winner mismatch a bad decision. `calibration_evaluation.py` also requires complete declared families and explicitly refuses to grant authorization from metrics alone. Preserve both historical behavior and exposure ledgers.

Propose a separately versioned training-readiness protocol, reviewed and frozen before new labels. It grants only the declared scalar/public-policy scope, not search, camera transfer or general simulator acceptance.

1. Freeze source/config hashes, roster, reference build, candidate generation, public checks, family generator, thresholds and roles. Reuse opened evidence only to design the protocol. No fresh collection or training occurs during council.
2. Require strict public serialization, causal masks, legal action transport, complete branches and terminal handling. Test hand, elixir, level/confidence and coordinate round trips. Unsupported fields must remain missing. Public-state calibration cannot be replaced by a simulator win rate.
3. Plan 32 independent fresh families across the roster and tactical situations, balanced across seats. Each has four declared candidates, including wait and a public-script baseline, and two frozen reacting continuation styles: 256 branches per backend. Perturbed positions/timing define family variation; correlated configurations do not increase the independent sample count.
4. Rank candidates using completed reacting outcomes. A proposed material failure is the scalar-preferred candidate losing at least 0.5 average match-score units relative to the reference-best candidate across the two continuations, or exceeding 5% initial total Crown HP in average margin regret when scores tie. Score win/draw/loss as 1/0.5/0. Treat scalar ties pessimistically. Freeze these provisional engineering thresholds before collection; they are not established human-sensitivity limits.
5. Require zero material-failure families, all public checks passing, and no declared cases missing. Zero failures among 32 independent sampled families gives a one-sided 95% upper bound of approximately 8.9% for this protocol's failure event only. It is a coarse entry gate, not proof that all strategic failures are rare. Report response-style disagreements and candidate coverage, and keep absolute winner/trajectory mismatch diagnostic rather than an automatic veto.

A failure triggers bounded diagnosis or explicit scope reduction and a new prospective attempt. Never drop a failing case from the completed attempt. A suspicious repeatable simulator exploit blocks the implicated mechanic even if the aggregate passes. Passing this gate does not recycle opened cases into policy promotion tests. Learned-policy transfer still needs subsequent reacting reference checks.

## Learning and opponents

Warm-start on public-script decisions from balanced, pressure and defense styles, with complete-game trajectories and split deck families. These three styles share code and are not three independent strategic teachers. Evaluate against at least one separately defined reacting strategy before claiming robust improvement.

Use synchronous recurrent PPO with frozen opponents throughout each rollout segment. Reuse `train_recurrent.py::collect_rollout_stationary_opponents`, `compute_gae` and `ppo_update` after contract checks. Start with terminal match reward; if exploration stalls, add a small fixed potential term with matching gamma and zero terminal potential through `reward_model.py`. Disable legacy defense-event rewards for the primary comparison. At 250 ms cadence, the default gamma 0.995 has a short effective horizon relative to a full match; choose discounting explicitly in seconds, with gamma 1 as the episodic control.

Initial opponent proportions are 50% scripted styles, 25% frozen warm-start policy and 25% retained earlier candidates once available. Before history exists, allocate that share to scripts. Pin every policy version and sampling schedule. Add current self-play and exploiters only after improvement against the fixed pool. Keep supervised regularization modest and annealable; the learner must be allowed to beat its teachers.

Required checks include behavior/update log-prob equality before optimization, full action-factor masking, terminal versus collection-truncation bootstrap, episode resets, critic isolation and replayed recurrent state. `dones` alone in the existing rollout structure deserves review before time-limit handling is trusted. `recurrent_state_contract.py` describes structured-hazard snapshots, not a generic LSTM serialization contract.

## First bounded milestone and decisions

First implementation milestone, after council agreement: one end-to-end public-v3 sequence through collection, supervised input, PPO input and inference, with levels/confidence, masks and recurrence intact. Add parent-group splits and a minimal public-script collector adapter. Reuse scalar `selfplay_env.py`; do not rewrite the runtime. Installed verifiers v1 `Taskset`/`Harness` offer typed orchestration, but no wrapper migration is needed for this numerical policy experiment. I did not run setup/sync because this round permits only the proposal write.

Before fitting, complete the prospective gate and benchmark 20 full scalar games plus actual actor forward/update shapes on CPU and MPS. `benchmark.py` uses random legal actions and imports a legacy network; its approximate games/minute is insufficient. Measure retained transitions/sec, full games/hour, p95 inference, update time and peak memory. No throughput was measured in this read-only round.

Then cap the pilot at 128 demonstration games, one warm-start fit and 100,000 learner decisions, with a 24-hour local wall limit including fitting and evaluation. Stop at the cap even if the sample target is unmet. Use 64 paired-seat development games for diagnostics. Freeze one candidate before a separate 128-game comparison against the warm start and fixed opponent pool, grouped by scenario/opponent for uncertainty.

Continue if games complete without contract failures, accepted legal commands exceed 99%, the candidate responds to board/hand interventions, and paired match-score gain is at least 0.10 with its 95% interval above zero. Otherwise call strength evidence inconclusive or negative. Require no greater than 0.10 point-estimate regression in declared archetype slices; report their wider intervals. This is pilot competence, not human-level certification.

If imitation cannot reproduce basic active behavior, fix alignment/timing before RL. If correct PPO fails two bounded seeds, compare candidate-value distillation on the same states and budget. If tile sensitivity dominates failures, refine placements. If clean-state strength survives but recorded-frame decisions fail, prioritize perception rather than more simulator experience.

Hardware checked this round: M4 Pro Mac mini, 12 CPU cores, 24 GB RAM, 8.9 GiB available disk. Reserve at least 4 GiB and cap new pilot artifacts at 2 GiB, with rolling shards and atomic retained checkpoints; no bulk collection until measured output fits. No paid allocation exists. Compute the next budget from measured collection/update time and storage per retained transition. Seek a single bounded accelerator allocation only after local gains and backend validation justify it; CPU movement tests do not certify resident tensor/CUDA execution. Final human-strength evidence requires a frozen cohort, comparable conditions, complete recordings and measured observation-to-action latency.

My principal uncertainty is whether these public scripted teachers provide enough exploration for terminal-outcome PPO to escape their strategic limits. Round 2 should resolve the teacher fallback and prospective regret criterion before debating larger networks.
