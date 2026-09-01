# Hog 2.6 legacy-simulator bridge pilot

Date: 2026-09-01

## Decision

Adopt the parallel Python simulator as a local development training bridge for
the fresh 494-token factorized policy.  Reject the joint action-value treatment
at update 20.  Continue only the plain control in staged outcome-RL runs, with
Simple Gym transfer checks before any promotion.

## Bridge evidence

The exact fresh initializer resumed through eight CPU rollout workers with MPS
learning, one Hog 2.6 deck, and the random plus six-strategy league.

- bounded update-1 bridge: `181.3` transitions/s;
- matched 20-update control mean: `210.435` transitions/s;
- prior eager Simple/MPS update: `8.9` transitions/s;
- observed local bridge ratio versus that prior route: about `23.6x` at the
  matched-control mean;
- control and joint-Q first-rollout SHA-256 were exactly equal:
  `0d3cae7f0e1808ccf1156b0a7531fe231db2ca952b36078b3bf1a9d935824b99`.

The update-1 learned checkpoint loaded directly into the Simple Gym with the
same 1,628,884-parameter/494-token contract.  A 128-decision Simple/MPS trace was
100% legal and retained the initializer's exact 12.5% play cadence and eight
unique actions.  This proves checkpoint compatibility, not simulator parity.

## Matched update-20 result

Both arms consumed 35,840 transitions from identical initial rollout evidence.

| arm | mean tps | sampled training W-L | final play rate | final KL |
|---|---:|---:|---:|---:|
| control | 210.435 | 16-20 | 15.5% | 0.00017 |
| joint-Q | 196.555 | 12-24 | 14.7% | 0.00026 |

Joint-Q retained 93.40% of control throughput and its selected-action loss fell
from 0.2706 to 0.0050, but its learned gate stayed tiny and negative (-0.0005).
It did not improve gameplay.

## Deterministic two-game development screen

| checkpoint | balanced | random | placement balanced/random |
|---|---:|---:|---:|
| initializer | 0-2 | 2-0 | 11.2% / 10.6% |
| control update 20 | 0-2 | 2-0 | 11.2% / 10.6% |
| joint-Q update 20 | 0-2 | 1-1 | 11.1% / 14.7% |

The screen is intentionally small but sufficient to reject the treatment: it
introduced a regression and no compensating win.  It is not sufficient to claim
the control improved.

## Guardrails for continuation

- keep Hog 2.6 as the learner deck until competent play is demonstrated;
- retain the diversified stationary opponent league;
- save intermediate checkpoints rather than assuming the final update is best;
- screen intermediates in Python for development, then recheck selected
  candidates in Simple Gym;
- never promote from training reward, loss, cadence, or this bridge alone.
