# Long-sequence heterogeneous horizon-only rejection

Date: 2026-08-29

## Decision

Reject the lineage at update 9 and retain the original Hog parent.  Do not wait
for update 15 after the added matched diagnostic made the failure decisive.

## Evidence

- 46 terminal training episodes completed through update 9: 0 wins, 46 losses.
- The paired update-8 diagnostic used identical decks, seeds, and both seats:
  parent 9-3; challenger 7-5.
- Balanced regressed from 4-0 to 2-2.
- Bridge-pressure stayed 1-3; random stayed 4-0.
- Aggregate crown differential regressed by 0.583/game.
- Placement rate did not collapse, and PPO/MPS metrics remained finite.  This
  is a gameplay/curriculum failure, not a numerical failure.

The originally planned update-15 screen was superseded only after this extra
update-8 diagnostic and the 0-46 terminal distribution existed.  Continuing
would test more samples from a demonstrably overmatched opponent distribution,
not the isolated temporal-horizon hypothesis.

## Consequence

The 64-decision recurrent horizon is retained.  Replace the 24/32 hard-strategy
league with the predeclared competence stage: 14 diverse random, 10
frozen-parent Hog mirrors, and 8 hard-strategy matchups.  All other model,
reward, mask, optimizer, anchor, transition-budget, and temporal contracts stay
fixed.
