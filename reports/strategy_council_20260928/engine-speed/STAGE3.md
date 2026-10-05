# Stage 3: GO for native P16 SRP

2026-10-03. Python remains the default and the authoritative reference. The native backend passes the requested gates. Recommend that srp-dagger opt in for its qualified P16/public-v4 srp_xm workload; the kit itself was not modified.

## Final gates

| Gate | Result |
|---|---|
| Public masks and consumed features | 256 distinct real pilot roots, both seats; 512 exact 2,306-bit masks and body/hand/elixir/Crown feature projections |
| Script root actions | 256 roots x 2 seats x 4 controllers = 2048 identical choices |
| Native-driven full games | 32 terminal games, 140,475 tick boundaries, 55,080 decisions; zero action/state-digest/full-RNG differences |
| Native rollout parity | 200 distinct searchable recorded roots, 3,999 candidates, 617,820 ticks, 115,770 continuation actions; zero differences |
| Production flag replay | All 200 qualified Python traces reproduced through backend="native" on the final build |
| Default path | 12 complete calls match the saved pre-integration planner, default constructor and native backend, including exact float scores, traces, leaf digests, choices and counters |
| Regression checks | 46 tests: 13 Stage 1, 24 Stage 2, 4 reduced Stage 3 cases and 5 backend boundary cases |
| Whole-call CPU | Python 2.306219s/call; native 0.030481s/call; 75.660x aggregate |

The 32 games cover all three public styles and include 8 default balanced StrategyBot seats. Both engines choose actions independently before deployment; every tick compares the unchanged es_common.battle_digest format and all 624 MT words plus index. The digest is not a serialization of every private clock. The 200-call differential additionally checks every candidate leaf score via float.hex(), every continuation action with its pre-action state digest, final leaf digests, root choices, rollout ticks, script calls, observation skips and override counters.

An earlier 200-call gate, including unaffordable roots, also passed 1,387 candidates / 212,718 ticks / 39,838 continuation actions. The stronger final gate requires a legal card play at each of 200 distinct roots. The corpus contains all 27 original Stage 0 snapshots plus 512 reproducibly replayed roots from accepted Stage 2 games. Corpus hashes/provenance are in stage3_corpus.json and stage3_search_corpus.json; the latter pickle is 13,723,611 bytes in ~/.cache/clasher-engine-speed. The actual OQ checkpoint builder separately passed 283 roots x 2 seats x 4 controllers.

## What runs natively

Public masks and the observation fields consumed by PublicScriptedOpponent, all balanced/pressure/defense scoring, the default balanced StrategyBot, cloning, deployment, stepping, continuation scheduling, and defense-v2 evaluation with the elixir term and terminal scores ±2/0. Float32 public boundaries, body ordering, stable action ties and CPython 3.12 compensated leaf sums are preserved. Candidate generation, its NumPy RNG, the root script/opponent choices, and final candidate comparison remain Python. No Python callbacks occur inside the native rollout loop.

The wrapper initializes immutable card/arena metadata once per planner, imports one live root per select_action, and clones it natively per candidate. Current public movement speed modes are imported separately from base movement stats because the leaf reads charge/slow-adjusted entity.speed. The existing Python live importer and all Python engine/opponent behavior remain unchanged.

## Measurements

The final 12-call benchmark times uninstrumented complete select_action calls on identical recorded roots, candidates, seeds and srp_xm settings. It includes native live-root export/import and Python candidate generation. Constructor, checkpoint loading and immutable configuration setup are excluded. Python is the current .venv CPython 3.12.13 source implementation with fast_script=True, not the older external Cython snapshot. An earlier identical 12-call run measured 2.488400s versus 0.035917s, 69.281x. Shared-host P/E-core scheduling varies; this is aggregate process-CPU evidence, not a per-call guarantee. One near-terminal call in the first run achieved only 2.18x.

## Enable

Build with `bash engine-rs/build.sh`. Make engine-rs and src importable, for example `PYTHONPATH=engine-rs:src`, then add `backend="native"` to the existing `ScriptRolloutPlanner(env, bot, opponent_model=StrategyBot("balanced"), ...)` constructor. Its defaults retain samples 16, script_top 4, horizon 160, rollout_interval 10, defense-v2 and elixir_weight 1. Keep the caller's existing plan_every 2 schedule and engine-legal/public root mask. Omitting backend, or specifying backend="python", selects the original Python rollout.

Admission covers level 11 P16, standard tournament towers/elixir, canonical public-v4, the qualified untyped vocabulary, all three PublicScriptedOpponent styles, and either the same public script or the default balanced StrategyBot opponent. Unsupported profiles, custom balanced weights, typed vocabularies and incompatible rules fail explicitly. C56, other StrategyBot styles and other observation contracts are outside this port. No srp-dagger, training, frozen runtime, pilot, C56 or oracle-qualification file was edited.

## Differential reductions

1. Exclude launched Ice Spirit carriers from public bodies; their reference representation is a projectile.
2. Exact character target ties use fixed spatial bucket encounter order. Building ties within 1e-6 use owner-relative coordinates. Unseen episode 102 first exposed Cannon 289 selecting Skeleton 323 instead of 324 at 3426. Match entities.py:2674-2727; phase3426.json and a small regression retain the proof.
3. Crown lookup requires Building class. A projectile retained its destroyed Princess's name and incorrectly closed 39 Log pocket tiles at episode 115 tick 3250. A saved-root regression verifies masks and all four actions.
4. A shot launched after its target died earlier in combat has no primary target. Python queries bodies at its zero-radius endpoint; Rust now does too. Existing homing shots whose target dies later keep their distinct behavior. The reduced test failed before the correction; phase3564.json records the full-game discovery.
5. Defense-v2 reads current entity.speed. Preserve the public unslowed movement mode through charge transitions, resets and live import, then apply the current slow factor. The saved DarkPrince leaf verifies exact potential components.

## Receipts and reproduction

Final receipts are stage3_roots_final.json, stage3_games_final.json, stage3_search_rollouts_a.json, stage3_qualified_backend.json and stage3_backend_final.json under results/. Both final driver exit receipts are 0. Final logs are logs/stage3_final_build_games2.log and logs/stage3_final_checks.log. stage3_manifest.json binds the final sources, extension, reports and receipts; stage3_python_preservation.json verifies all 90 Stage 2-loaded Python oracle hashes unchanged.

Launch long jobs with the authorized pilot/detach.sh wrapper. `engine-rs/evidence-stage3/final_games.sh` builds and runs 32 games. `final_checks.sh` replays qualified traces, verifies roots, repeats default/benchmark checks and runs 46 tests. To rerun the original differential use `PYTHONPATH=engine-rs:src nice -n 10 .venv/bin/python -B engine-rs/test_stage3_rollouts.py --searchable --output <new-receipt.json>`. Root-producing and qualification helpers are tests under engine-rs; atomic per-case receipts make the long comparisons resumable. Use new output names to preserve accepted receipts after source changes.

No known mismatch remains within the qualified scope. The native module remains an optional local extension rather than a packaged wheel. Only the authorized planner source, Rust core, Stage 3 tests/evidence and engine-speed documentation/results changed. Cargo intermediates are cleaned at final handoff; the tested extension is retained.
