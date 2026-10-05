# M0 scalar learner and inference receipt

The public-v4 scalar path now carries actual entity levels, entity level confidence, own hand/next-card levels, hand level confidence and accepted own-play history through collection, rollout serialization, minibatch indexing, recurrent PPO, checkpoint evaluation and public inference. Missing level pairs fail rather than becoming invented observations. The level-11 legacy defaults remain in place.

`SelfPlayBattleEnv(public_contract_version=4)` uses the clean real-play-v2 feature projection and public legality builder. It disables illegal-action and elixir-leak rewards and rejects defense scenarios. Its default potential coefficient is 0.05, with shaping gamma one and zero terminal potential. The actor receives zero previous rewards. Submitted actions and acceptance results are retained separately in `RolloutBatch.actions` and `action_success`; `StepInfo` retains execution failures. These acceptance flags do not claim the later deployment took effect at submission time.

Per-seat card mappings and tower levels enter before battle construction. `reset(card_levels=(mapping0, mapping1), tower_levels=(level0, level1))` supports explicit episode setup. Worker configuration carries those fields. Nominal/mixed scheduling after the first million decisions belongs to the admitted experiment runner.

Collection and PPO reconstruct recurrent state from the complete public episode prefix under current weights. Prefixes exclude privileged critic fields. The scalar multiprocessing queue carries the ragged prefix payload, and rollout audits hash it. A fixed-weight 128+3-decision test matches uninterrupted 131-decision inference. Changed-weight reconstruction is tested separately.

The proposed 32-step suffix restart changes the policy at collection boundaries. Production therefore uses exact prefix reconstruction in both collection and PPO. The recurrence helper retains a bounded suffix option solely for diagnostic comparisons. No production collection flag selects this approximation. This reference can cost more memory and replay time than a future optimized implementation; the benchmark must measure it.

Time-limit truncations bootstrap the final observation before reset and cut the GAE chain between episodes. True terminal transitions receive no bootstrap. Public-v4 playing-strength evaluation rejects unfinished matches. Evaluation CLI decoding now defaults to stochastic; deterministic decoding requires its explicit flag.

Fresh entry flags are `--public-contract-version 4`, `--public-history-slots 4`, and `--public-seen-card-slots 8`, with scalar backend `--simulation-backend python`. Existing architecture, optimizer and rollout-size flags remain available. The council recipe must also specify its agreed card semantics and learning hyperparameters.

Validation: 109 focused tests passed in 9.28 seconds, including two real scalar worker processes, mixed-level transport, public checkpoint inference, policy likelihood replay, 128-step boundary continuity, pre-reset truncation bootstrap, critic isolation and legacy paths. The exact command and results are in `pytest.log`; Ruff and `git diff --check` passed. `shared_rollout_ipc.py` remains unchanged because it handles the raster path; the actual structured path uses the tested scalar queue.

No gameplay training job, native collection, paid compute, commit or historical-evidence modification occurred in this workstream. Tests use untrained policies and bounded software-contract optimizer checks. This receipt does not establish playing strength or Tier A admission.


The full-match deadline repair maps the council's nominal 6,000-tick horizon to 6,001 ticks. The simulator deliberately resolves the last playable interval strictly after 300 seconds. Training and evaluation record the effective cap. Legacy 6,000-tick runs and deliberately shorter caps keep their prior behavior. New tests start at tick 5,999 and verify true termination at 6,001 for equal HP and either unequal-HP winner, including the terminal reward. A standalone evaluation test records the actual winner rather than an incomplete draw. The focused follow-up passed 26 tests in 5.33 seconds; see `horizon-pytest.log`.
