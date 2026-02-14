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

### 3) Train (sync PPO)

```bash
uv run python run_clasher.py train -- \
  --num-workers 6 \
  --device mps \
  --quiet-engine \
  --rollout-steps 768 \
  --save-every 5 \
  --checkpoint-dir checkpoints/selfplay_run \
  --resume-latest
```

### 4) Train (async actors + learner)

```bash
uv run python run_clasher.py train-async -- \
  --num-actors 10 \
  --device mps \
  --quiet-engine \
  --actor-rollout-steps 128 \
  --transitions-per-update 4096 \
  --epochs 2 \
  --batch-size 1536 \
  --compress-obs-fp16 \
  --policy-sync-every 2 \
  --save-every 5 \
  --checkpoint-dir checkpoints/selfplay_async \
  --resume-latest
```

### 5) Watch latest checkpoint

```bash
uv run python run_clasher.py watch -- \
  --checkpoint-dir checkpoints/selfplay_run \
  --device mps
```

`watch` can also take `--checkpoint /absolute/or/relative/path.pt`.

### 6) Evaluate latest checkpoint

```bash
uv run python run_clasher.py eval -- \
  --checkpoint-dir checkpoints/selfplay_run \
  --games 100 \
  --device mps \
  --quiet-engine
```

### 7) Print latest checkpoint path only

```bash
uv run python run_clasher.py latest-checkpoint --checkpoint-dir checkpoints/selfplay_async
```

### 8) Smoke-run Gymnasium env

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
- `clasher-selfplay-xyz-v0` (`dict` obs + `MultiDiscrete([18, 32, 5])` actions for `(x, y, slot/no-op)`)

### 9) Determinism Check

```bash
uv run python run_clasher.py determinism-check -- \
  --seed 123 \
  --decisions 512 \
  --trials 2 \
  --quiet-engine
```

### 10) Benchmark Suite

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

## Legacy modules still supported

You can still run module entrypoints directly:

- `python -m clasher.rl.train_selfplay`
- `python -m clasher.rl.train_selfplay_async`
- `python -m clasher.rl.watch_policy_battle`
- `python -m clasher.rl.eval`

If running direct modules without an editable install, use `run_clasher.py` instead.

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
- For Apple Silicon, `--device mps` is supported in both trainers and watch/eval.
- If a checkpoint/decks/data file is missing, commands now fail with the resolved absolute path in the error.
