# Simple Gym asymmetric stationary-opponent collector

## Outcome

The dense PyTorch Gym can now train exactly one learner seat per battle row
against resident no-op, random, frozen-checkpoint, single-strategy, or mixed
PFSP strategy opponents. Mirror self-play remains available but is no longer
the only production route.

This is an implementation/compatibility milestone, not a policy promotion.
No long CUDA league has run on this source yet.

## Training contract

- one fixed learner deck by exact supported-deck name;
- opponent deck cycles through every other supported deck;
- adjacent rows use the same learner/opponent deck pair with learner seats
  `[0, 1]`;
- both seats remain resident in the tensor simulator;
- PPO arrays contain only the learner seat, so `B x T` battles yield `B*T`
  transitions rather than `2*B*T` self-play transitions;
- opponent actions, recurrence, and rewards never enter learner PPO loss;
- frozen checkpoint recurrence is independent and stays device-resident;
- public-action-mask-v2 remains the action authority for both seats;
- checkpoint metadata persists learner seats, learner deck, paired opponent
  decks, opponent mode, strategy schedule, and frozen checkpoint SHA-256;
- the set-attention policy may rebind `max_entities` because it is not a learned
  tensor dimension. A direct narrow/wide model test proved identical action-type
  logits, location logits, and values with identical weights and inputs.

## Tensor StrategyBot port

All six existing public, data-driven StrategyBots are vectorized from current
actor tensors and official card descriptors:

- bridge-pressure
- slow-push
- balanced
- reactive-defense
- spell-control
- split-lane

The port does not inspect critic tensors, hidden hands/cycles/elixir, simulator
target IDs, or card-name branches. Exact selected-action parity against the
Python StrategyBot passed for:

- 24 initial-state seat/row/strategy comparisons;
- 12 pressured combat seat/strategy comparisons containing visible allied and
  enemy troops, scaled HP, lane strength, defensive fit, cluster fit, and tank
  support.

The mixed league shards rows by strategy and evaluates only each shard, rather
than scoring all six policies over the entire batch.

## PFSP schedule

`reports/hog26_simple_strategy_pfsp_seed1163701.json` records the first schedule
from the corrected paired champion matrix. At 64 rows it allocates:

- bridge-pressure: 13
- slow-push: 12
- balanced: 12
- reactive-defense: 10
- spell-control: 9
- split-lane: 8

Every adjacent row pair retains the same opponent deck and opposite learner
seat. The 33-deck supported artifact covers Hog, bait, X-Bow, Giant/Golem,
P.E.K.K.A bridge-spam, Balloon/LavaLoon, Graveyard, Miner, and Wall Breakers.

## Evidence

- focused collector/backend/mask gate: 52 passed, 10 skipped;
- broad Simple Gym gate: 449 passed, 261 skipped;
- Ruff: clean;
- `simple_pytorch_backend.py` isolated mypy: clean;
- existing whole-trainer mypy still reports only its pre-existing annotation
  debt;
- diff check: clean;
- exact three-step mixed-league replay: all arrays, learner boundaries,
  recurrent states, actions, rewards, dones, and outcomes identical across two
  independent collectors;
- real one-update CPU PPO smoke passed for random, frozen checkpoint, single
  strategy, explicit mixed strategy league, and PFSP-driven league;
- real MPS learner+actor strategy smoke passed with a 494-token recurrent
  checkpoint and learner-only rollout shape;
- retained champion (`max_entities=128`) initialized at audited runtime capacity
  56 and completed a real strategy PPO update with strict state-dict loading.
- the same capacity-rebound contract passed a real anchored PPO update against
  the PFSP league with `anchor_policy_kl_coef=0.1`;
- `scripts/run_hog26_simple_asymmetric_pfsp_seed1163701.sh` refuses fewer than
  94 updates and encodes the exact 120-update CUDA acceptance candidate.

The three-update 64-row MPS warm profile reached 31.8 learner transitions/s on
update 3 (512 transitions, 15.66 s collection, 0.44 s learning). This is
functional but not an efficient production route; CUDA remains required for the
terminal-complete pilot.

## Remaining acceptance gates

Before training evidence is accepted:

1. rerun current-source CUDA Graph certification;
2. run at least 95 uninterrupted updates so every row can cross the 6,000-tick
   terminal boundary;
3. require native/committed rows, zero fallback, nonzero terminal episodes, and
   exact replay hashes;
4. evaluate paired random, every strategy, Hog mirror, and the retained champion;
5. reject the challenger on any broad safety regression even if internal league
   reward improves.

Mixed frozen checkpoints plus strategies in the same row schedule are not yet
implemented; frozen checkpoint mode is currently a separate stationary run.
