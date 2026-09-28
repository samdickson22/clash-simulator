# Hog 2.6 heterogeneous long-run contract (seed 1192001)

Date: 2026-08-29

## Purpose

Test whether the retained Hog 2.6 policy can learn from terminal outcomes when
the accepted Simple PyTorch Gym is allowed to run for materially longer than
the rejected 10k--61k-transition pilots.  This is not another StrategyBot
distillation or external ranker experiment.

## Frozen parent

- Path:
  `/Users/sam/Desktop/code/clasher/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt`
- SHA-256:
  `28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`
- Learner deck: `Hog 2.6 Cycle`

The parent initializes model weights only.  Simulator state, optimizer state,
update counter, transition counter, and RNG state start fresh under the
persisted Simple-Gym backend contract.

## Training contract

- backend: `simple-pytorch`, MPS eager
- environments: 64 physical rows / 32 logical paired matchups
- learner seats: paired 0/1 for every matchup
- rollout: 8 decisions, 512 learner transitions/update
- target: 512 updates / 262,144 learner transitions
- match horizon: 6,000 ticks
- terminal exposure: at least five complete match horizons per physical row
- learning rate: `1e-5`, no annealing
- PPO: 2 epochs, sequence batch 64, gamma `0.995`, GAE `0.95`
- anchor: frozen parent, policy KL coefficient `0.1`
- reward: Simple-Gym `objective-v1-gamma-v1`; legacy elixir-leak penalty off
- checkpoints: every 5 updates (the existing runner's stricter cadence)

The logical opponent schedule is the already certified heterogeneous mix:

- random: 4/32 matchups
- frozen-parent Hog mirror: 4/32
- balanced: 8/32
- bridge-pressure: 4/32
- slow-push, spell-control, reactive-defense, split-lane: 3/32 each

The opponent deck pool remains diverse and paired across learner seats.

## Fail-closed training gates

Reject the run if any of the following occurs:

- simulator fallback or non-native/non-committed rows;
- checkpoint/backend/mask/reward/vocabulary metadata drift;
- no terminal episodes after the first terminal boundary;
- non-finite loss, reward, KL, entropy, or value statistic;
- anchor-policy KL exceeds `0.10` for three consecutive saved boundaries;
- MPS construction/runtime failure or capacity overflow;
- process exits without the exact update-512 checkpoint and `COMPLETE` marker.

## Gameplay evaluation gates

Training completion is not promotion.  Evaluate parent plus updates 65, 130,
255, 385, and 512 using identical seeds and both seats.  These are the nearest
persisted boundaries to the originally intended 64/128/256/384/512 cadence:
the already launched trainer saves every five updates plus its final endpoint.
This correction was made before the first screen result existed and changes no
metric threshold or acceptance rule.

1. Development screen: the frozen 48-game gameplay screen.
2. Quarantine: the frozen 96-game gameplay quarantine.
3. Strategy matrix: balanced, reactive-defense, spell-control,
   bridge-pressure, slow-push, and split-lane.
4. Random and frozen-parent Hog mirror controls.
5. Hog utilization: Hog played in every game, with no regression in legal,
   affordable Hog-window conversion or dominant-tile collapse.
6. Safety: no strategy bucket may lose more wins than the candidate gains
   overall; no parent win may become a challenger loss in the strict promotion
   comparison unless the matched aggregate bootstrap lower bound is positive.

The best saved boundary is selected by the full paired evidence, not by
training reward.  If no boundary clears every gate, retain the parent and
reject the entire lineage.
