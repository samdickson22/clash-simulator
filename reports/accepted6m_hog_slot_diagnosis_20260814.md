# Accepted-6M Hog slot diagnosis (2026-08-14)

## Scope

This audit explains the three Hog zero-use games in the predeclared 12-game
Hog matrix for the accepted zero-mechanics parent. It does not change the
checkpoint, reinterpret a loss as a pass, or authorize promotion.

Bound inputs:

- decision records SHA-256:
  `9e3e541d41381250b4f45bdfe298a1579b76e23a288a0f65fd9b27eebe309ea7`
- game records SHA-256:
  `9f75adf6efb2991fadf117a31ce708e98748158790a14a7dd42c700efe524135`
- utilization report SHA-256:
  `f8a1eef0d9dd3efcd182fd696659a7dd1a7b44f01b45513a13a0a6e615bc84ef`

## Finding

The failure is observable card choice, not missing Hog access. In games 1, 5,
and 10, Hog was in hand, legal, and affordable on 8, 2, and 2 recorded
decisions. The deterministic policy chose a different slot on all 12.

| Game | Candidate seat | Legal-affordable Hog decisions | Hog plays | Outcome |
| ---: | ---: | ---: | ---: | --- |
| 1 | 1 | 8 | 0 | win, 1--0 crowns |
| 5 | 1 | 2 | 0 | loss, 0--1 crowns |
| 10 | 0 | 2 | 0 | loss, 0--1 crowns |

The selected slots at those missed opportunities were:

- game 1: Hog occupied slot 0; the policy selected slot 3 on all eight;
- game 5: Hog occupied slot 1; the policy selected slots 2 and 0;
- game 10: Hog occupied slot 0; the policy selected slot 1 twice.

Across all 12 games, the utilization report records:

| Hog slot | Legal-affordable decisions | Plays | Conversion |
| ---: | ---: | ---: | ---: |
| 0 | 23 | 0 | 0.00% |
| 1 | 20 | 18 | 90.00% |
| 2 | 4 | 4 | 100.00% |
| 3 | 32 | 32 | 100.00% |

This large slot asymmetry is exactly within the causal reach of the shared
mechanics card-choice query: it can change the relative score of legal hand
cards while timing/action-type and placement geometry remain frozen. It also
means aggregate Hog use is insufficient evidence. A candidate must have at
least two legal-affordable observations, at least one play, and at least 25%
conversion in every slot, in addition to the existing per-game, per-seat,
aggregate, outcome, and no-regression gates.

## Decision

Keep the four-update mechanics-query experiment. Do not broaden it to timing or
placement before seeing this causal result. If it cannot repair the slot-0
defect without passing every preservation gate, reject the branch instead of
adding a Hog-specific rule or relaxing the threshold.
