# Hog 2.6 long-sequence heterogeneous PPO contract (seed 1192101)

Date: 2026-08-29

## Frozen design

- parent SHA-256:
  `28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`
- backend: accepted Simple PyTorch Gym, MPS eager
- learner: fixed Hog 2.6, paired seats
- opponents: the exact 32-matchup heterogeneous random/strategy/frozen-parent
  schedule used by seed 1192001
- environments: 64
- rollout/recurrent sequence: 64 decisions = 25.6 seconds
- updates: 64
- learner transitions: 64 x 64 x 64 = 262,144
- full terminal boundary: approximately every 12 updates
- optimizer: AdamW, learning rate `1e-5`, two PPO epochs
- gamma/lambda: `0.995` / `0.95`
- anchor: original parent, policy-KL coefficient `0.1`
- reward: `objective-v1-gamma-v1`
- public action mask: v2 tensor actor projection
- saved checkpoints: every 5 updates plus update 64

The only intended learning-design change from rejected seed 1192001 is the
eightfold longer rollout/BPTT/GAE window.  Total transitions and all policy,
opponent, reward, mask, and anchor contracts remain fixed.

## Fail-closed gates

Reject on OOM/capacity failure, non-finite statistics, backend or semantics
drift, fallback/noncommitted rows, missing terminal outcomes after update 15,
or anchor-policy KL above 0.10 for three saved checkpoints.

Run matched paired development screens at updates 15, 30, 45, 60, and 64.
Promotion still requires the full 48-game screen, 96-game quarantine, complete
strategy matrix, Hog-use audit, and no-regression checks.  Training reward or
teacher agreement alone cannot promote a checkpoint.
