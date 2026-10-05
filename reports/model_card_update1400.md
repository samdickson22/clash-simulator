# Clasher V2 champion model card: update 1400

## Model

- Checkpoint: `checkpoints/mixed_league_champion50_lr1e4/policy_v2_update_001400.pt`
- SHA-256: `6acbf7b4bd1f0dc3de221cb5d69caa5d79389a6171113e9c403cc10bc8f44b60`
- Architecture: entity-spatial recurrent actor-critic, 1,266,468 parameters
- Actor: public visible entity tokens, own hand/cycle, public arena state,
  previous action/reward, entity Transformer, 192-wide LSTM, hierarchical
  card-and-tile action distribution
- Critic: separate privileged full-state entity encoder used only during training
- Action space: four hand slots across 18 x 32 tiles, no-op, and champion ability,
  masked by simulator legality

## Data and simulator scope

- Official-client data snapshot: StatsRoyale `gamedata-v5.json`
- Public-data fingerprint: `ef863332281e7c47d628d23a80881ed300d47ede`
- Matching decoded official client: `15.546.41`
- Enabled scope: 57 direct or transitively reachable unit specifications plus
  the enabled spells and buildings
- Training source: simulator experience only; no real-match or human data

The simulator has extensive deterministic, scalar/fast-path, interaction, and
invariant tests. These are strong internal checks, but they do not prove exact
commercial-client parity. Use the read-only replay validator to record external
mismatches rather than treating this checkpoint as live-game validated.

## Objective and training

The champion used the legacy `objective-v1` potential:

```text
0.55 * crown_difference
+ 0.25 * princess_tower_pressure
+ 0.10 * gated_king_pressure
+ 0.10 * absolute_HP_tiebreak_edge
- 0.20 * early_king_chip_penalty
```

Rewards are differences of this public-state potential, with terminal outcomes
remaining dominant. The champion was trained for 5,591,040 learner decisions:

1. pure self-play through update 300;
2. stationary uniform-legal random curriculum through update 800;
3. frozen update-300/update-800 curriculum through update 1300;
4. a weighted league of random, update 800, and update 1300 through update 1400.

The later update-1500 and update-1440 challengers were rejected after matched
evaluation regressions. They are not recommended models.

## Frozen paired evaluation

Every matchup was replayed with the candidate on both seats.

| Opponent | Games | W-L-D | Score | Approx. 95% interval | Crown diff/game |
|---|---:|---:|---:|---:|---:|
| Uniform-legal random | 72 | 62-10-0 | 0.861 | [0.781, 0.941] | +1.583 |
| Update 300 | 72 | 60-12-0 | 0.833 | [0.747, 0.919] | +1.514 |
| Update 800 | 72 | 58-14-0 | 0.806 | [0.714, 0.897] | +1.403 |
| Update 1300 | 72 | 39-33-0 | 0.542 | [0.427, 0.657] | +0.278 |

These measurements establish relative simulator performance on the evaluated
seeds. They do not establish optimal play, human-level strategy, or real-game
performance.

## Intended use

- reproducible RL-gym baseline and curriculum anchor;
- simulator regression and paired opponent evaluation;
- policy viewer demonstrations;
- starting point for controlled reward, strategy-opponent, and imitation studies.

Not intended for automated commercial matchmaking or claims of exact live-game
behavior.

## Known limitations

- The champion's tower-centric objective can prefer racing for three crowns and
  delay defense. The opt-in `defense-v2` profile was added after training and has
  not yet been used to promote a checkpoint.
- The frozen training league contains one learned lineage plus random play. The
  deterministic strategy roster is new and has not yet been included in this
  checkpoint's curriculum.
- Playable no-op is high because the learned policy often waits for elixir. This
  was useful through update 1400 but became an over-specialization failure later.
- No perception, real-client controller, or visual-domain robustness is included.
- The score intervals are normal approximations and the direct update-1300
  interval includes an even match.

## Run it

Watch update 1400 play update 800:

```bash
uv run python scripts/run_clasher.py watch -- \
  --checkpoint checkpoints/mixed_league_champion50_lr1e4/policy_v2_update_001400.pt \
  --opponent-checkpoint checkpoints/random_curriculum/policy_v2_update_000800.pt \
  --device cpu
```

Run a paired random evaluation and save JSON:

```bash
uv run python scripts/run_clasher.py eval -- \
  --checkpoint checkpoints/mixed_league_champion50_lr1e4/policy_v2_update_001400.pt \
  --opponent random --games 72 --seed 4101 --stochastic --device cpu \
  --json-out reports/eval_update1400_random.json
```

Run the public-information strategy benchmark:

```bash
uv run python scripts/run_clasher.py strategy-benchmark -- \
  --checkpoint checkpoints/mixed_league_champion50_lr1e4/policy_v2_update_001400.pt \
  --games-per-opponent 24 --device cpu \
  --json-out reports/strategy_update1400.json \
  --markdown-out reports/strategy_update1400.md
```
