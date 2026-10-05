# Council M0 actual-path benchmark

Sam subsequently selected the Mac mini for current work. The [local configuration follow-up](macmini-tuning.md) measures four and eight environments across 13 completed games and recommends the next local setup.

The final local CPU run completed two real games, with no truncations or rejected commands. It retained 1,536 learner decisions in 33.56 seconds, or 45.77 decisions/second. The p95 learner action forward pass was 32.92 ms. Both policy-weight digests match. No optimizer step, fitted checkpoint, demonstration label or paid job was produced.

Reproduce with:

```sh
.venv/bin/python scripts/perf/benchmark_council_rollout.py \
  --device cpu --num-envs 2 --rollout-steps 128 --chunks 6 \
  --max-ticks 6001 --synthetic-backward --output /tmp/council-benchmark-new.json
```

The script refuses to overwrite an existing output. It supports CPU, MPS and CUDA and fails if the requested device is unavailable. It verifies the jointly approved strategy hash and immutable training-role manifest before running.

The measured model has 2,604,979 parameters. It uses the approved width 128, four attention heads, four actor layers, two separate critic layers, LSTM width 256, card semantics 4, public contract 4, four history slots and eight seen-card slots. Observations carry entity and undeployed hand/next-card levels and confidence. It uses canonical coordinates and lane globals, five-tick decisions and nominal level 11. The model starts with fresh weights and reacts against the frozen public balanced controller. Only the learner seat contributes to retained decision counts; learner seats alternate across the two environments.

Collection uses exact current-weight episode-prefix reconstruction. Finite suffix replay is not used. The six chunk rates ranged from 28.53 to 73.18 retained decisions/second. Prefix replay, simulator state and machine contention make this short local run unsuitable for extrapolating a remote training budget.

The nominal match deadline is followed through tick 6001 so the final tiebreaker resolves. The final run's two games ended naturally before that deadline. Its observed completed-game rate is 214.56/hour, based on just two completions during a 33.56-second timed window after two warmup decisions per environment. This is a small-sample observation, not a steady-state throughput estimate or a playing-strength result.

The optional synthetic diagnostic took 3.24 seconds for one two-sequence, 128-step forward/backward pass. It uses the real observation shapes, independently sampled legal actions, alternating artificial advantages and zero value targets. Gradients were finite, and weights stayed unchanged. This excludes prefix reconstruction, optimizer updates and multiple PPO epochs, so it does not measure full PPO update throughput. Peak process RSS was 3.14 GB, including that synthetic backward pass, model setup and the retained replay history.

The final evidence is `cpu-final-6001.json`. Before/after hashes cover source, configuration, training decks and game data. Its imported runtime closure did not change. Two unrelated source modules, `readiness_execution.py` and `readiness_root_bank.py`, changed concurrently and are listed in the whole-tree receipt. The report therefore records whole-tree stability as false and runtime stability as true. It does not claim the entire workspace was frozen.

Earlier diagnostic artifacts are preserved:

| Artifact | Workload | Result |
| --- | --- | --- |
| `cpu-short-smoke.json` | 2 envs, 8-step chunks, 2 chunks | 36.02 learner decisions/s; no completed games |
| `cpu-128x2.json` | 2 envs, 128-step chunks, 2 chunks | 69.66 learner decisions/s; 21.32 ms forward p95; no completed games |
| `mps-128x2.json` | Same short workload on MPS | 22.68 learner decisions/s; 46.49 ms forward p95; no completed games |
| `cpu-fullgame-bounded.json` | 2 envs, 128-step chunks, 10 chunks | 2 true completions, 0 truncations; earlier nominal horizon and whole-tree drift retained as diagnostics |
| `synthetic-short-smoke.json` | 8-step synthetic backward sanity check | Finite gradients; unchanged weights |

The MPS run's whole-tree drift was confined to two live-inference modules not imported by this benchmark. The device timings are local low-batch observations. They do not predict CUDA learner performance.

A remote CPU/GPU run was the next benchmark contemplated by this initial report. The later Mac mini decision and local follow-up above supersede that as an immediate dependency. Actual PPO update and multi-epoch cost, accelerator memory at the intended batch size, worker transport and sustained throughput remain unmeasured. No grant resources were launched by this task, and this benchmark does not admit gameplay training or establish Tier A readiness.
