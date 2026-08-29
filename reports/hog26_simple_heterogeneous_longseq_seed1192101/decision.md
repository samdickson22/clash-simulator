# Seed 1192101 MPS capacity decision

Date: 2026-08-29

## Decision

Reject this execution before update one and preserve its update-zero checkpoint
and exact traceback.  No learned checkpoint exists.

The 64-decision collection completed, but PPO forwarded all 64 recurrent
sequences in one minibatch.  MPS held 27.32 GiB plus 2.43 GiB of other
allocations and failed a further 1.12 GiB tile-decoder allocation at its 30.19
GiB safety ceiling.  Do not disable the MPS high-watermark guard.

The replacement keeps 64-step temporal credit but uses eight sequences per
minibatch.  Eight sequences x 64 decisions = 512 transitions per optimizer
step, exactly matching the rejected short-sequence run's 64 x 8 = 512.  With
two epochs this also preserves the total optimizer-step count per transition.
The change is therefore a memory-safe reshape of the same learning budget, not
a hidden batch-size or update-frequency change.
