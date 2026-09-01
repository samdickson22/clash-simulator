# Hog 2.6 batched Simple-Gym gate and bridge rejection

Date: 2026-09-01

## Decision

Reject the Python-trained spatial-teacher lineage as a route to verified Simple-
Gym competence.  Preserve its checkpoint only as diagnostic evidence.  Further
outcome training must run directly in the Simple Gym on CUDA Graph; do not spend
more local time training against the Python backend and assuming transfer.

## Evaluator improvement

The Simple evaluator previously constructed one tiny resident collector per
opponent.  It now supports one mixed-league collector containing every opponent
bucket while preserving:

- paired learner seats;
- exact requested games per opponent;
- deterministic policy execution and seeded random actions;
- first natural terminal outcome per row;
- per-opponent placement and outcome records;
- backend execution metadata;
- fail-closed 760-decision termination bounds.

For two games against each of six strategy bots plus random, each arm evaluated
14 games total:

| arm | wall | seconds/game | peak observed RSS |
|---|---:|---:|---:|
| initializer | 1,488.55 s | 106.33 | under 5 GiB |
| spatial update 20 | 1,429.84 s | 102.13 | under 5 GiB |

The earlier sequential balanced/random evaluation took about 22 minutes for
four games, roughly 330 seconds/game.  Batching therefore improved practical
per-game throughput by approximately 3.1-3.2x.  This is useful for occasional
local gates but remains too slow for high-confidence campaigns.

## Matched breadth result

Seed: `1249401`.  Both arms used MPS eager execution, identical 14-row opponent
schedule, two paired seats per bucket, and natural terminal outcomes.

| opponent | initializer | spatial update 20 |
|---|---:|---:|
| bridge-pressure | 0-2 | 0-2 |
| slow-push | 0-2 | 0-2 |
| spell-control | 0-2 | 0-2 |
| reactive-defense | 0-2 | 0-2 |
| split-lane | 0-2 | 0-2 |
| balanced | 0-2 | 0-2 |
| random | 0-2 | 0-2 |
| **total** | **0-14** | **0-14** |

All candidate placement rates remained noncollapsed (`10.43%` to `14.80%`),
and every game was legal and naturally terminal.  The candidate changed its
behavior but delivered zero Simple outcome improvement.

## Consequence

The spatial candidate's Python-backend gains—especially against slow-push—do
not establish target-backend skill.  The broader Simple gate confirms the
earlier 0-4 transfer tie was not merely too narrow.  The retained best verified
model remains novice/low-ladder and no fresh checkpoint is promoted.

The next admissible experiment is the already-packaged direct Simple CUDA Graph
gate/training path.  Prime Intellect currently has no live pod and the wallet is
negative, so that external compute boundary—not another local objective tweak—
is the immediate blocker.
