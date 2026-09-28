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

For a mixed league, repeat `--league-opponent` with `random`, a
`strategy:NAME`, and frozen checkpoints. Repetition controls worker weights;
the following assigns four of the twelve workers to each opponent:

```bash
uv run python run_clasher.py train -- \
  --resume-from checkpoints/historical_curriculum/policy_v2_update_001300.pt \
  --updates 1500 \
  --num-envs 64 \
  --actor-workers 12 \
  --actor-threads 1 \
  --rollout-steps 64 \
  --opponent-mode league \
  --league-opponent strategy:reactive-defense \
  --league-opponent checkpoints/random_curriculum/policy_v2_update_000800.pt \
  --league-opponent checkpoints/historical_curriculum/policy_v2_update_001300.pt \
  --engine-fast-path on \
  --device mps \
  --actor-device cpu \
  --learning-rate 1e-4 \
  --sequence-batch-size 4 \
  --epochs 2 \
  --save-every 10 \
  --checkpoint-dir checkpoints/mixed_league
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
was actually legal. Add `--json-out reports/eval.json` for a machine-readable
scorecard. Defense diagnostics report incoming tower danger, board-value edge,
and action rate while threatened.

The opt-in `defense-v2` reward keeps the original tower objective dominant while
adding telescoping public board-value and tower-danger potentials:

```bash
uv run python run_clasher.py train -- \
  --resume-from checkpoints/mixed_league_champion50_lr1e4/policy_v2_update_001400.pt \
  --updates 1420 --reward-profile defense-v2 \
  --opponent-mode checkpoint \
  --opponent-checkpoint checkpoints/mixed_league_champion50_lr1e4/policy_v2_update_001400.pt \
  --num-envs 64 --actor-workers 12 --actor-threads 1 \
  --rollout-steps 64 --device mps --actor-device cpu
```

`objective-v1` remains the default so old checkpoints and experiments do not
silently change objective.

### Strategy benchmark and PFSP inputs

Clasher includes six deterministic, card-agnostic public-information opponents:
bridge pressure, slow push, spell control, reactive defense, split lane, and
balanced play. Evaluate the entire roster and emit both JSON and Markdown:

```bash
uv run python run_clasher.py strategy-benchmark -- \
  --checkpoint checkpoints/mixed_league_champion50_lr1e4/policy_v2_update_001400.pt \
  --games-per-opponent 24 --device cpu \
  --json-out reports/strategy_update1400.json \
  --markdown-out reports/strategy_update1400.md
```

The JSON includes PFSP weights computed from measured score rates. Feed it back
into league training with `--pfsp-report reports/strategy_update1400.json` and
`--pfsp-strategy-workers N`; the largest-remainder allocator deterministically
maps the weights onto exactly `N` actor workers. Keep at least one frozen
checkpoint in that league. Strategy bots can also be used directly with
`--opponent-mode strategy --opponent-strategy reactive-defense` or as an
explicit `--league-opponent strategy:reactive-defense`.

### Fixed oracle imitation baseline

Generate a deterministic V2 public-observation corpus from the existing
fixed-depth oracle, then fit an imitation warm start and an untouched control
checkpoint from exactly the same initialization:

```bash
uv run python run_clasher.py imitation -- collect \
  --output datasets/oracle_v2_seed4401.npz \
  --decisions 5000 --seed 4401 --workers 12 --reward-profile defense-v2

uv run python run_clasher.py imitation -- fit \
  --corpus datasets/oracle_v2_seed4401.npz \
  --output-checkpoint checkpoints/imitation/oracle_warmstart.pt \
  --control-checkpoint checkpoints/imitation/matched_control.pt \
  --manifest-out reports/imitation_seed4401.json \
  --device mps --epochs 10 --seed 5501
```

Both outputs use the normal V2 checkpoint format and can receive identical PPO
decision budgets. The corpus is fixed and versioned, so oracle drift cannot
confound the comparison.

The oracle and corpus default to `defense-v2`; selecting `objective-v1` remains
available for a deliberate legacy ablation.

### Read-only real-replay validation

`replay-validate` compares two normalized public-frame JSONL traces and records
spawn, damage, tower-damage, and death/visibility mismatches. It never automates
or mutates a commercial client:

```bash
uv run python run_clasher.py replay-validate -- \
  --observed reports/replays/real_match.jsonl \
  --simulated reports/replays/clasher_trace.jsonl \
  --report-out reports/replays/parity_report.json \
  --events-out reports/replays/derived_events.json
```

Each JSONL row contains `timestamp_ms`, public `towers`, and visible `entities`
with `track_id`, `player_id`, `card`, `x`, `y`, and optional `hp`. This is an
adapter boundary for manual labels or a future video detector, not a claim that
pixel extraction is already solved.

### 5) Watch the V2 checkpoint play itself

```bash
uv run python run_clasher.py watch -- \
  --checkpoint checkpoints/entity_selfplay/policy_v2_update_000140.pt \
  --device cpu
```

The viewer runs the same recurrent policy on both seats unless
`--opponent-checkpoint` or `--opponent-random` is supplied. Controls are
Space to pause, R/Enter to reset, 1-5 for simulation speed, D for sight/lock
overlays, S for a screenshot, and Escape to quit. Stochastic action sampling is
the default; add `--deterministic` for argmax play.

To play a recorded human evaluation match against a checkpoint:

```bash
uv run python run_clasher.py watch -- \
  --checkpoint checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt \
  --human-player 0 \
  --human-label evaluator-1 \
  --human-ladder-label mid-ladder \
  --deterministic \
  --device cpu \
  --record-out reports/human_vs_policy_matches.jsonl
```

Player 0 is shown at the bottom. Click one of the four current hand cards or use
Q/W/E/R, then click an exactly legal highlighted arena tile; A activates a legal
champion ability. Enter starts a new match. Each completed game appends one JSONL
record containing the checkpoint SHA-256, seats, decks, crowns, candidate-perspective
outcome, human actions, and invalid input count. Run a second block with
`--human-player 1` with the same `--seed` to replay the sampled matchups with
human/candidate deck roles held fixed and physical arena seats swapped. Human
mode cannot be combined with a second policy or random opponent.

Human matches are locked to the simulator's native 20 Hz wall-clock pace; the
1-5 speed controls are disabled. Recorded rows include pacing metadata, and the
summary gate rejects legacy or accelerated sessions.

After balancing the candidate across both seats, summarize the evidence with:

```bash
uv run python scripts/summarize_human_policy_matches.py \
  --records reports/human_vs_policy_matches.jsonl \
  --output reports/human_vs_policy_summary.json \
  --required-games 40 \
  --required-distinct-decks 8 \
  --required-score-rate 0.5 \
  --required-human-ladder-label mid-ladder \
  --fail-on-gate
```

The strict gate requires one checkpoint hash, recorded evaluator labels, only
the exact required ladder cohort, globally balanced seats, every matchup paired
equally across both candidate seats, enough distinct decks and matchups, at
least the requested score, and a 95% score-interval lower bound at or above that
score. Passing simulator or bot gates alone is not reported as human-level
evidence.

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
- The accepted update-1400 model is documented in
  [`reports/model_card_update1400.md`](reports/model_card_update1400.md), and
  canonical video metadata lives in
  [`reports/canonical_replays.json`](reports/canonical_replays.json).
- The project is available under the [MIT License](LICENSE).
