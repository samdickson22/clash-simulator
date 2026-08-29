# Hog 2.6 long-sequence mb8 PPO contract (seed 1192101)

Date: 2026-08-29

This replaces the OOM seed-1192101 execution while preserving its simulation
seed and all semantic/training inputs.

- 64 environments x 64 decisions x 64 updates = 262,144 transitions
- recurrent/GAE horizon: 64 decisions / 25.6 seconds
- PPO sequence minibatch: 8 sequences / 512 transitions
- PPO epochs: 2, therefore 16 optimizer steps/update and 1,024 total
- old short-window control: 64 sequences x 8 decisions = the same 512
  transitions/optimizer step and 1,024 total optimizer steps
- exact parent, league, reward, mask, anchor, LR, gamma, lambda, entropy, and
  capacity contracts unchanged
- MPS high-watermark remains enabled
- checkpoints/screens: updates 15, 30, 45, 60, 64

Reject on OOM, capacity/fallback/semantics drift, non-finite metrics, missing
terminal outcomes after update 15, sustained anchor KL above 0.10, or any final
promotion-gate regression.  No checkpoint is promoted from training metrics.
