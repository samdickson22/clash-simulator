# Clasher

Fast Clash Royale-style battle simulator with self-play training loops.

## What changed in this refactor

- Centralized path resolution in `src/clasher/paths.py`.
- No more brittle `cwd` assumptions for `gamedata.json`, `decks.json`, `hitboxes.json`, or checkpoints.
- Unified CLI in `src/clasher/cli.py` with a local launcher: `run_clasher.py`.
- RL train/watch/eval now resolve and print absolute paths they actually use.

## Quick start

### 1) Environment

```bash
uv sync
```

### 2) Inspect resolved paths

```bash
uv run python run_clasher.py paths
```

### 3) Train the entity-recurrent policy

```bash
uv run python run_clasher.py train -- \
  --resume-from checkpoints/entity_selfplay/policy_v2_update_000300.pt \
  --updates 300 \
  --num-envs 24 \
  --actor-workers 8 \
  --actor-threads 1 \
  --rollout-steps 64 \
  --device mps \
  --actor-device cpu \
  --sequence-batch-size 4 \
  --epochs 3 \
  --save-every 10 \
  --checkpoint-dir checkpoints/entity_selfplay
```

This is the primary trainer. It uses public entity tokens, an entity Transformer,
recurrent memory, a card-conditioned spatial decoder, and a separate privileged
critic. On Apple Silicon, the CPU actor processes run the Python simulator and
low-latency inference while MPS handles full recurrent PPO minibatches.

For a stationary curriculum phase, train one balanced seat per environment
against a uniform-legal random opponent. Only learner-controlled decisions enter
PPO, so opponent actions never contaminate the policy loss:

```bash
uv run python run_clasher.py train -- \
  --resume-latest \
  --updates 800 \
  --num-envs 64 \
  --actor-workers 12 \
  --actor-threads 1 \
  --rollout-steps 64 \
  --opponent-mode random \
  --device mps \
  --actor-device cpu \
  --sequence-batch-size 4 \
  --epochs 2 \
  --save-every 10 \
  --checkpoint-dir checkpoints/random_curriculum
```

After the stationary anchor establishes measurable progress, mix frozen V2
opponents by repeating `--opponent-checkpoint`. Workers distribute the snapshots
round-robin and preserve each opponent's recurrent state independently:

```bash
uv run python run_clasher.py train -- \
  --resume-from checkpoints/random_curriculum/policy_v2_update_000800.pt \
  --updates 1300 \
  --num-envs 64 \
  --actor-workers 12 \
  --actor-threads 1 \
  --rollout-steps 64 \
  --opponent-mode checkpoint \
  --opponent-checkpoint checkpoints/entity_selfplay/policy_v2_update_000300.pt \
  --opponent-checkpoint checkpoints/random_curriculum/policy_v2_update_000800.pt \
  --engine-fast-path on \
  --device mps \
  --actor-device cpu \
  --sequence-batch-size 4 \
  --epochs 2 \
  --save-every 10 \
  --checkpoint-dir checkpoints/historical_curriculum
```

### 4) Evaluate a V2 checkpoint

```bash
uv run python run_clasher.py eval -- \
  --checkpoint-dir checkpoints/entity_selfplay \
  --games 40 \
  --opponent random \
  --stochastic \
  --device cpu
```

Evaluation replays each seeded deck matchup with the candidate on both seats and
reports a score interval, crown differential, and no-op rate when another action
was actually legal.

### 5) Watch the V2 checkpoint play itself

```bash
uv run python run_clasher.py watch -- \
  --checkpoint checkpoints/entity_selfplay/policy_v2_update_000140.pt \
  --device cpu
```

The viewer runs the same recurrent policy on both seats unless
`--opponent-checkpoint` or `--opponent-random` is supplied. Controls are
Space to pause, R to reset, 1-5 for simulation speed, and Escape to quit.
Stochastic action sampling is the default; add `--deterministic` for argmax play.

### 6) Print the latest V2 checkpoint

```bash
uv run python run_clasher.py latest-checkpoint \
  --checkpoint-dir checkpoints/entity_selfplay
```

### 7) Smoke-run Gymnasium env

```bash
uv run python run_clasher.py gym-smoke -- \
  --episodes 2 \
  --max-steps 128 \
  --decks-path decks.json \
  --action-mode flat
```

With structured episode debug dump (for exploit triage):

```bash
uv run python run_clasher.py gym-smoke -- \
  --episodes 1 \
  --max-steps 256 \
  --action-mode flat \
  --debug-dump reports/rollout_debug.jsonl
```

Gym ids:
- `clasher-selfplay-v0` (`dict` obs + flat discrete actions)
- `clasher-selfplay-xyz-v0` (`dict` obs + `MultiDiscrete([18, 32, 6])` actions for `(x, y, card-slot/no-op/champion-ability)`)

### 8) Determinism Check

```bash
uv run python run_clasher.py determinism-check -- \
  --seed 123 \
  --decisions 512 \
  --trials 2 \
  --quiet-engine
```

### 9) Benchmark Suite

Single-process env throughput:

```bash
uv run python run_clasher.py benchmark -- env \
  --decisions 4096 \
  --quiet-engine
```

Async actor queue throughput + lag:

```bash
uv run python run_clasher.py benchmark -- async-queue \
  --num-actors 6 \
  --transitions 8192 \
  --actor-rollout-steps 128 \
  --quiet-engine
```

## Legacy trainers still supported

The old raster baseline remains available during checkpoint migration:

- `run_clasher.py train-legacy`
- `run_clasher.py train-async`
- `python -m clasher.rl.train_selfplay`
- `python -m clasher.rl.train_selfplay_async`

These training commands use the legacy checkpoint format and model, not the V2
entity-recurrent checkpoints produced by `run_clasher.py train`. The viewer now
loads V2 checkpoints.

## Path behavior

Resolution order for relative paths:

1. Current working directory
2. Project root (auto-detected by `pyproject.toml` + `gamedata.json`)

You can force a root with:

```bash
export CLASHER_ROOT=/absolute/path/to/clasher
```

## Notes

- Python `>=3.10` required.
- For Apple Silicon training, use `--device mps --actor-device cpu`; tiny actor
  inference batches are faster on CPU, while full PPO sequences are faster on MPS.
- Evaluation defaults to CPU because it performs latency-sensitive batch-one inference.
- If a checkpoint/decks/data file is missing, commands now fail with the resolved absolute path in the error.
