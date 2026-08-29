# Heterogeneous update-60 retrospective screen

Date: 2026-08-29

## Decision

Reject update 60 from `hog26_simple_heterogeneous_seed1164301`.  Retain the
original Hog 2.6 parent.

This retrospective closes the missing free-running evidence for the earlier
61,440-transition mixed-league pilot.  It also supplies a concrete baseline
for the new 262,144-transition run: merely reproducing update-60 behavior is a
failure.

## Matched screen

Both arms used the same fixed Hog 2.6 learner deck, held-out opponent deck pool,
seeds, and paired physical seats.  Each bucket contains four games.

| Bucket | Parent | Update 60 | Win delta | Crown diff/game delta |
|---|---:|---:|---:|---:|
| balanced | 2-2 | 1-3 | -1 | -0.25 |
| bridge-pressure | 1-3 | 0-4 | -1 | -0.75 |
| random | 3-1 | 3-1 | 0 | -0.75 |
| **total** | **6-6** | **4-8** | **-2** | **-0.58** |

Placement rate was effectively unchanged at roughly 7.0% in every bucket, so
the regression is not explained by a trivial play/no-op collapse.  Defensive
event success also failed to improve: balanced was flat, bridge-pressure fell
from 0.406 to 0.360, and random was flat.

## Consequence

The old short heterogeneous PPO run moved policy weights without producing a
free-running advantage.  The current seed-1192001 run is allowed to continue
because it is predeclared to cross substantially more complete terminal
cycles, but it must beat this result at updates 64/128/256/384/512 and still
pass the larger frozen screen and quarantine before promotion.
