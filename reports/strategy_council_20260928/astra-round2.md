# Astra, Round 2

The compute grant changes the scale of the experiment, but it does not make the existing privileged oracle a trustworthy teacher. I recommend that we build a clean public-information recurrent actor and train it through a staged, diverse PPO league, with a short scripted warm start and a serious from-scratch control. Use CPU simulation workers and a GPU learner immediately. Develop perception and compatible human supervision alongside training. Add search/distillation only after the teacher demonstrably improves decisions.

I withdraw my Mac-limited 100,000-decision pilot as the main strategic test. That budget could expose broken plumbing; failure at that scale would tell us little about the approach's potential. We should spend the grant on replicated learning curves, diverse opponents and independent evaluation. We should not spend it expanding an unvalidated teacher-label factory.

This is my preferred strategy, not consensus with Fable. No implementation, training or collection occurred in this round.

## Where I agree with Fable

We agree on the central diagnosis: basic adaptive competence has not been demonstrated, and neither modern replay reconstruction nor exact trajectory matching should indefinitely prevent us from trying to learn it. We also agree on entity attention, recurrent memory, a privileged training critic, public-only actor inputs, fresh weights without accumulated repair adapters, synchronous PPO first, and later opponent history/exploiters.

Fable's proposed policy-conditioned reference checks are a useful addition to my first proposal. A simulator can pass scripted controls and still teach a learned player an exploit. We need checks both before learning and after the policy changes its state distribution.

I also accept small potential-based shaping from the beginning, with a terminal-only control later. It is a practical exploration aid if discounting and terminal potential are correct. I would not retain an illegal-action penalty in the principal objective: illegal submissions are contract or transport failures to diagnose, and the actor already has legal masks.

## Differences that matter

### 1. A privileged oracle is a hypothesis, not the default expert

I inspected `rl/oracle_planner.py`. `FixedDepthThompsonOracle` clones full `BattleState`, selects both sides' actions through decoupled bandits, and uses `reward_win_prob_p0` at the leaf. Its defaults are 48 simulations, depth 10 and eight ticks per step: about four seconds of simulated lookahead. This is not evidence of strong completed-game play. More simulations do not automatically fix a short-horizon heuristic or decisions conditioned on information unavailable to the student.

Privileged demonstrations are legitimate training data. The concern is learnability and strategic quality, not that privileged labels are categorically forbidden. Two identical public histories can receive contradictory labels because the teacher sees different hidden hands. Distillation can then learn an unhelpful average; a student also reaches states unlike the teacher's.

Therefore the oracle should earn its role. After the applicable search/ranking gate, compare it with scripts and the current actor on completed reacting games, then compare students at equal training compute. Preserve uncertainty and alternate good actions rather than forcing every noisy search winner into a hard label. Until that evidence exists, scripts provide a cheap bootstrap and PPO supplies improvement.

`train_dagger_oracle.py` imports `MaskedPolicyValueNet` and buffers raster boards/HUDs. It cannot directly run the proposed structured recurrent actor. `dagger_behavior.py` offers reusable actor helpers, but its inspected input builder also omits newer history/confidence/level fields. These modules need adaptation, not “reuse as-is.”

### 2. The proposed event/tracker preset does not instantiate

Current `model.py::PolicyConfig` rejects:

- `memory_kind="lstm"` with `structured_deterministic_resource_enabled=True`.
- The deterministic tracker with nonzero `public_history_slots`.
- `deterministic_hierarchy="event"` without structured memory and an enabled hierarchical mode gate.
- Event accumulation combined with the deterministic resource tracker.

Fable's preset combines these incompatible choices. Separately, `event_policy.py` contains a useful continuous-time distribution, but the inspected model/imitation/PPO files do not call `continuous_time_action_distribution`. Selecting the existing deterministic event decoder does not integrate its likelihood into PPO.

Use an LSTM with existing public history inputs, deterministic resource tracking disabled, and a stochastic mode/card/tile distribution at five ticks. An external causal tracker can later improve event memory without replacing the LSTM. Track confirmed observations exactly where possible; opponent hand/cycle beliefs must remain uncertain when observations or rules are ambiguous.

Continuous-time timing remains a good later experiment. It must share one distribution across collection, supervised likelihood, PPO and inference. It is unnecessary to solve it before learning useful play. Ten ticks is 500 ms; I prefer 250 ms as the starting control, now that local compute is not binding.

### 3. Activity is not competence

I reject hard success thresholds on waiting frequency or defensive action frequency. Waiting while a card is playable is often correct, and many threats need no new card. Track these quantities by tactical situation to diagnose collapse. Promote on completed-game strength, execution reliability, adaptation and absence of repeatable exploits.

Likewise, held-out archetypes outside the admitted card scope cannot be a mandatory acceptance slice for a 16-card pilot. Admit their mechanics first, or report them as out-of-scope stress tests. The procedural deck split needs parent-family grouping; its current within-archetype shuffle does not provide that.

### 4. Broader compute should broaden learning, not hide the observation boundary

Start with noiseless values for fields deployment can actually observe. Mask simulator-only fields from the beginning. That separates a difficult perception problem from a different information game. Later add measured correlated observation errors and latency. Fable's full simulator-exact actor is useful as an explicitly optimistic ablation, but I would not make it the sole lineage we hope to deploy.

## The strategy to implement

### Actor and objective

Use `ClasherPolicy`, initially its 128-wide four-layer entity encoder, 256-wide LSTM and card-conditioned spatial decoder. Keep semantic card descriptors and current-hand identity. Use public-v3 visible levels/confidence and add own undeployed-card/tower levels to the contract. Carry observed public events and prior own actions, but zero previous reward inputs. A separate privileged critic and opponent-state prediction losses are allowed; their targets never feed the actor.

Fix the full public sequence path through rollout storage, imitation, PPO, worker IPC and inference. `RolloutBatch` and `_sequence_inputs` currently omit level arrays. Add recurrent burn-in, terminal/truncation separation, behavior-log-prob replay checks, and hidden-state isolation tests. Version the checkpoint/observation contract. These are narrow prerequisites to using existing modules, not a runtime rewrite.

Use full-game terminal score with a small fixed potential-based shaping coefficient. Start at gamma 1 for the finite match objective, zero terminal potential, and GAE lambda 0.95. Inspect credit assignment before changing those values; the historical per-decision gamma 0.995 implies a much shorter preference horizon. Normalize advantages without changing the underlying competitive score. No elixir-spending, forced-play or hand-authored defensive-style reward.

Keep tile-center actions initially, but audit building pulls and spell edges before scaling. Preserve submitted coordinates in demonstrations. If projection reverses useful choices, add a constrained sub-tile residual; do not compensate with card-specific rules.

### Initialization and learning

The main lineage gets up to 500,000 public-script-labeled decision opportunities from complete multi-deck games, including natural waits, then recurrent PPO. Use several scripted styles and keep teacher provenance. This is basic motor/tactical initialization, not expert imitation. Train a from-scratch PPO control with the same architecture, opponents and update budget. The grant makes this comparison affordable and avoids assuming either demonstrations or pure RL must win.

Run three seeds per initialization for five million learner decisions each, counting learner actions rather than both players' actions. Freeze evaluation checkpoints at one and five million decisions. Thirty million total decisions is the first learning experiment. Examine whole learning curves and retain failures; do not stop an otherwise healthy method after a few dozen PPO updates.

Use synchronous collection with policy-versioned actor batches. Start with 64 environments, 128-step chunks, 32-step burn-in and two PPO epochs; adjust batching to measured memory/throughput without changing effective sample counts. Initial learning rate 1e-4, clip 0.2, and entropy regularization with separately logged mode/card/location entropy. Tune only on development runs. Refresh recurrent state consistently when actor weights change.

For the first million decisions, use a frozen mixture of scripted opponents and the initial policy pool. After that, introduce retained checkpoints and current self-play while preserving fixed opponents. A reasonable established-league allocation is 25% scripts, 50% historical/checkpoint opponents, 25% current self-play. Opponent identity stays fixed for each match. Add PFSP after stable improvement, with a floor for historical opponents. Add targeted exploiters after the pool has meaningful strategic diversity.

No-op/random opponents are controls, not a large source of rewarded training wins. Report a fixed opponent matrix throughout; a changing league win rate is not progress evidence.

### Scope and adaptation

Use the existing 16-card roster for the first learning experiment, across Hog, Giant, pressure/control decks and procedural neighbors. This isolates learning-system failures. Do not require human-level performance in this artificial subgame before expansion.

Prepare a broader base-card scope during that experiment: preserve recognizable professional-style deck structures, include air, splash, swarm, building, spell and spawn interactions, and target the roughly 66-card scope described by the existing support artifacts only after checking actual scalar behavior. An artifact listing supported cards is not admission evidence. Run the next learning stage across that broader scope, retaining Hog as a specialization slice rather than the whole training distribution.

Fix level plumbing early. Start the first million decisions at level 11, then introduce per-card levels 10–12 in half the games, keeping half at the reference setting. Randomize tower levels explicitly and expose visible level information consistently. Own-level support is needed by the teachers too. Hold out particular level/deck combinations to distinguish adaptation from memorization.

I would not begin with hidden independent ±5% HP/damage noise. First learn real level variation and observation/action latency. Then add coherent, episode-fixed balance perturbations within declared ranges, with a nominal arm retained. Preserve strict costs, targeting and legality. Measure whether robustness helps; randomization is not automatically beneficial.

### Human data and search

Audit the existing camera corpora now; Fable's inventory makes them more promising than my first proposal's acquisition emphasis suggested. Require action alignment, confidence/missingness, ruleset/form identity and independent match splits before using a placement/timing prior. Low weight does not make mislabeled data harmless. Keep raw modern replay forms intact and use action-only logs for distribution analysis until public states are defensible.

A small clean human corpus can improve strategic diversity without reconstructing all modern mechanics. Add it as a measured supervised regularizer, never as an excuse to delay PPO. Modern forms should enter by explicit mechanic bundles later.

Privileged-oracle search remains a bounded teacher-quality experiment, followed by public-belief search only if rankings and student improvement justify it. Fast actor-only deployment is the default. A learned world model is not part of this strategy.

## Readiness and evaluation

Keep v7, its source pins and exposure ledger unchanged. Write a new prospective training-readiness protocol that distinguishes correct public serialization, useful action rankings and later policy transfer. I do not support concurrent development fitting before the existing required gate is satisfied merely by labeling checkpoints non-promotable. Contract tests and synthetic optimizer checks can proceed without fitting a gameplay policy.

For the scoped entry gate, use 32 fresh independent families with four fixed candidates and four reacting continuations per family. Freeze response styles/seeds, candidate generation, source hashes and missing-case rules. Exact public serialization and legal transport remain mandatory. Every branch must complete.

Revise my Round 1 material score-regret threshold from 0.5 to 0.25 across the four continuations. A bad family also includes more than 5% initial total Crown HP in mean margin regret when scores tie. Score wins/draws/losses as 1/0.5/0, and handle scalar ties pessimistically. These are proposed engineering tolerances, not scientifically established human limits. Require zero bad families and publish the approximately 8.9% one-sided upper bound for this narrowly defined event. Absolute scalar/native winner mismatch alone remains diagnostic. This gate must be frozen before outcomes and cannot be implemented by silently editing v7's evaluator.

Before broader training, extend coverage to new mechanic bundles and levels. Before promotion, run a separate policy-conditioned reference block from frozen candidate games, including common decisions, losses and suspected exploit patterns. Distinguish representative random roots from targeted exploit probes; targeted probes do not support a population failure-rate estimate. No missing cases disappear from denominators. Search needs its own admitted scope and teacher-quality check.

Use at least 512 paired-seat games per finalist versus the frozen opponent pool, grouped by independent matchup/seed for uncertainty, plus held-out deck-family and level slices. Advance when PPO beats initialization by at least 0.05 mean match score with a 95% interval above zero, beats the fixed scripted pool overall, and shows no material subgroup collapse. Require evidence across seeds before calling the recipe reliable. Report interventions, illegal/rejected actions, latency and disconnects. Validate tactical reactions with controlled board/hand changes and outcome-based scenario grading, not mandatory play frequency.

Final human-level claims require an identified human cohort, comparable decks/levels, frozen weights and complete real-game recordings. Native reference transfer and simulator strength are intermediate evidence.

## Grant use and stop rules

Start on one GPU learner with roughly 64 CPU cores for scalar actors and sufficient remote scratch storage. The Mac coordinates and hosts reference tooling; its disk is not the experiment's storage budget. Benchmark complete games, observation construction, inference and updates for two hours on the actual machine. Choose the bottleneck from measurements. Do not require CUDA tensor parity before using a GPU learner with scalar actors, or claim old simple-gym microbenchmarks predict this workload.

Propose a first envelope of 72 GPU-hours and 4,608 CPU core-hours for the 30-million-decision comparison, including evaluation. This is a ceiling, not a promise of throughput. If it cannot finish, report achieved decisions and profile before spending more. Grant availability does not mean an unlimited launch is authorized during council.

After positive learning and transfer evidence, allocate up to two GPU learners and 128 CPU cores for seven days to a broader-deck league stage, targeting three 30-million-decision replicas. That adds at most 336 GPU-hours and 21,504 CPU core-hours. Prefer fewer resources if the small actor underutilizes the GPU. Keep restartable jobs, rolling trajectories, selected checkpoints and object-storage evidence. These envelopes replace my Mac-only budget; they do not require a large accelerator cluster.

If both initialization arms fail after five million decisions with correct updates, first inspect exploration, credit assignment, opponent difficulty and representation. Give the strongest diagnosed revision one replicated follow-up. If scripts win early but plateau, reduce imitation anchoring and improve league diversity. If failures cluster around placement precision or missing history, fix that interface before making the network larger. If the native checks expose repeatable exploits, repair or isolate the mechanic before rewarding more of it.

The remaining substantive disagreement is teacher priority. I favor scripted initialization plus replicated PPO now, with oracle teaching earned by evidence. Fable favors making oracle DAgger the initial dependency. The grant lets us evaluate that challenger without making its correctness an assumption or blocking the main learning path. I can agree to this strategy if we also settle the valid timing/memory preset, observable actor boundary and prospective gate explicitly.
