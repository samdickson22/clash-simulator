# Mac mini local configuration

Use the CPU with **8 scalar environments, 2 Torch threads, 128-step rollouts and exact episode-prefix reconstruction** for the next local correctness work. Keep the approved model unchanged. For future synthetic update checks, retain the already measured two-sequence minibatch instead of making the update batch eight sequences at once. Gameplay fitting still follows readiness admission.

Two bounded runs took 260.16 seconds combined. They produced 11,264 learner decisions and 13 true completed games, with no truncations or rejected commands. No optimizer steps, labels or fitted weights were produced.

| Setting | 4 environments | 8 environments |
| --- | ---: | ---: |
| Timed duration | 122.49 s | 137.68 s |
| Learner decisions | 5,120 | 6,144 |
| Learner decisions/s | 41.80 | 44.63 |
| True completed games | 5 | 8 |
| Observed completed games/hour | 146.95 | 209.19 |
| Process peak RSS, decimal GB | 1.32 | 1.53 |
| Whole action-call p95 | 53.28 ms | 77.55 ms |
| Exact-prefix reconstruction | 28.61 s, 23.4% | 36.90 s, 26.8% |
| Per-chunk decisions/s range | 34.23–53.43 | 32.54–60.06 |

Eight environments provide more simultaneous games for about 0.21 GB extra peak RSS. Its observed decision rate was only 6.8% higher; this does not establish a statistically reliable speedup. The runs have different trajectories and phase mixes and are not replicated timing experiments. Their game/hour rates use few completions, include unfinished games, and should not be used as sustained training rates.

For local planning, use roughly **40–45 retained decisions/s for collection under the present load**, with individual chunks around 33–60/s. At 40–45/s, 100,000 decisions require about 37–42 minutes of collection alone. PPO updates, evaluation, native checks and changing policy behavior add time. This is a planning range, not a confidence interval or a complete training-budget estimate.

The 24 GiB, 12-logical-CPU machine was already running four unrelated Java processes at roughly 800–850% aggregate CPU. Those jobs were left alone. System memory-pressure output reported 47–54% free across the checks. Reported swap use declined from 6,741.12 MiB to 6,725.12 MiB; the benchmarks did not coincide with an increase. A 3 GiB native-emulator allowance fits the observed headroom, but concurrent emulator/learner throughput was not measured. The coordinator waited until both benchmarks stopped before starting its reference emulator.

Both runs used the full approved actor, public-v4 levels/confidence, role-v2 training decks, five-tick actions, the frozen reacting public balanced opponent, nominal level 11, and a 6001-tick horizon. Exact prefix replay consumed about a quarter of rollout time. This measurement supports preserving correctness while budgeting for its cost; no recurrence or architecture shortcut was introduced.

Evidence is in `macmini-env4.json` and `macmini-env8.json`. Both preserve before/after weight and source hashes. Weights and the imported runtime closure stayed unchanged. Whole-tree source changed independently: the four-environment run saw edits to native-observation/readiness code; the eight-environment run saw the addition of `readiness_native_config.py`, outside its imported closure. The raw eight-environment artifact records the added file in its before/after maps, although its original changed-file list did not list additions. The script now includes additions and deletions in that list.

The selected machine for current work is the Mac mini. Remote benchmarking is optional, not a blocker for this local path. Full PPO-update throughput and longer runs alongside the native tooling remain unmeasured. No further parameter sweep was run.
