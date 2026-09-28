# Hog 2.6 terminal action reranker development gate

Date: 2026-08-31

## Decision

Freeze the rank-8 epoch-1 action reranker as a **development candidate only**.
Do not integrate it into free-running play until it passes a newly generated,
untouched terminal holdout.  Reject the rank-16 and rank-32 arms.

The retained policy is never edited.  The reranker receives its frozen state
features plus a complete legal-action descriptor built from canonical tile
geometry, the checkpoint's mechanics/semantic card features, and the parent's
action prior.  It predicts terminal outcome first and dense return only as a
bounded tie-break.  An action may override the parent only when its predicted
win-probability advantage reaches the frozen margin.

## Development evidence

All arms used 24 terminal training roots and 21 exact-policy-input-disjoint,
play-aligned development roots, with 12 terminal candidates per root.  Seven
development roots had an action with a better terminal outcome than the parent.

| rank | selected epoch | margin | overrides | outcome improvements | outcome regressions | decision |
|---:|---:|---:|---:|---:|---:|---|
| 8 | 1 | 0.10 | 6/21 | 2/7 correctable | 0 | freeze for fresh holdout |
| 16 | none | none | - | at most 1 | gate not met | reject |
| 32 | none | none | - | at most 1 | gate not met | reject |

The rank-8 epoch-1 development BCE was 0.47613 and its guarded action attained
best-outcome accuracy 0.76190 versus the parent's 0.66667.  Continued training
degraded transfer, so the frozen candidate is exactly epoch 1; no later epoch,
larger rank, threshold change, or seed is eligible based on this development
set.

Candidate checkpoint:

- `checkpoints/hog26_terminal_reranker_rank8_seed1236001/candidate.pt`
- SHA-256 `a28c41547467d65607ac0befdc0954a381b207fe5076614c97c6615c9c707a4e`
- parent SHA-256 `28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`
- frozen override probability margin `0.10`

## Next hard gate

Generate a new root-fingerprint-disjoint terminal holdout after the architecture,
rank, epoch, seed, and margin are frozen.  The candidate is rejected if it
chooses even one worse terminal outcome than the parent, captures fewer than two
correctable roots, or depends on a duplicated root.  Only a passing untouched
holdout earns an inference wrapper and paired seven-opponent gameplay screen.
