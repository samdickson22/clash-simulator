# PyTorch training and oracle integration — 2026-08-14

## Scope and lineage

- Worktree: `/Users/sam/.codex/worktrees/4725b4d4-84cb-41d8-8ac7-7b11a58246b5/clasher`
- Branch: `codex/pytorch-training-oracle-4725`
- Base: `ae5c08e2` (`Expand PyTorch batch and deployment coverage`)
- Python-only integration; no Rust path was changed.

## Milestones

1. `e288de2e` — route the opt-in `python`, `pytorch-shadow`, and `pytorch`
   simulator backends through synchronous self-play, async actors, actor-count
   probes, and RL benchmark workers. The default remains `python`.
2. `6d5c193d` — add the paired production-shaped recurrent rollout and oracle
   benchmark. It uses 12 persistent workers, 64 environments, alternating
   variant order, a concurrent oracle process on the same paired backend,
   exact rollout/oracle digests, latency and throughput metrics, and a
   deterministic paired bootstrap interval.
3. `2ade99e9` — add independently writable tensor batch forks, exact scalar
   snapshot guards, executor priming/invalidation, and opt-in oracle search
   routing. `BattleState.clone()` remains scalar-authoritative for every search
   simulation, and unsupported branches fail closed to Python.

## Exact validation

Environment recovery preserved the incomplete Python 3.14 environment as
`.venv-py314-incomplete-20260814T1815` and created the locked Python 3.12.13
environment at `.venv`.

- Routing and recurrent/self-play coverage:

  ```text
  56 passed in 11.22s
  ```

- Tensor-fork, simulator, and oracle coverage:

  ```text
  27 passed in 1.51s
  ```

- Benchmark protocol unit coverage:

  ```text
  4 passed in 0.55s
  ```

- Strict type check of `state.py`, `executor.py`, and `oracle_planner.py`:

  ```text
  Success: no issues found in 3 source files
  ```

- `git diff --check ae5c08e2..HEAD`: clean.

The covered no-op oracle differential produced identical chosen actions,
planner RNG state, and input snapshots with 4 tensor forks, 16 tensor ticks,
0 Python ticks, and 0 fallbacks. The sampled-search differential produced the
same actions (`{0: 51, 1: 52}`), planner RNG, and unchanged root snapshot; its
candidate metrics were 4 tensor ticks, 12 Python ticks, 6 exact unsupported
fallbacks, and 4 tensor forks.

## Benchmark guard and clean-window command

The live guard-only probe exited before creating workers because an unrelated
MPS-configured Clasher workload was present. The only reported process evidence
was PID/PPID/CPU/reason plus command SHA-256; command text was not emitted by the
guard. No contaminated throughput result was collected.

Run the full protocol only in a clean compute window:

```sh
nice -n 10 .venv/bin/python scripts/perf/benchmark_recurrent_torch_oracle.py \
  --seed 2301 --oracle-seed 901 \
  --num-workers 12 --num-envs 64 \
  --rollout-steps 64 --warmup-steps 8 --repetitions 7 \
  --actor-threads 1 --decision-interval 8 --max-ticks 2048 \
  --engine-fast-path on \
  --oracle-queries 3 --oracle-depth 6 \
  --oracle-simulations 32 --oracle-action-samples 64 \
  --timeout 600 \
  > reports/pytorch_recurrent_oracle_12worker.json
```

The harness exits with status 2 if any paired rollout field differs byte for
byte or if the fixed-seed oracle action/RNG digests differ.

## Inherited broad-suite state

The repository-wide test command cannot collect seven inherited modules at
this base because later-lineage tests refer to missing reward-profile APIs and
`clasher.rl.strategy_bots`. With those seven uncollectable modules excluded,
the broad run produced `1279 passed, 135 failed`; the failures are likewise
dominated by the inherited `compute_rollout_digest(..., reward_profile=...)`
API mismatch, with a small existing imitation-objective group. These unrelated
lineage repairs were intentionally not folded into this Python simulator
integration.
