# Scaled Hog 2.6 strategy-proposal repair decision

Decision: reject the complete short-horizon conditional-action repair lineage.
Retain the original Hog parent. Do not tune the optimizer, coefficient, head
set, or corpus size again under the 24-decision label contract.

## Final corpora

- train: 129 probes, 61 accepted, 61 unique accepted state hashes;
  corpus SHA-256 `50bb395ded3e61ec02c03575eec9bb6f19e1b0e2d83624cbf50cbfef05530ffe`;
- replay-disjoint validation: 21 unique-seed probes, 12 accepted, 12 unique
  accepted state hashes; corpus SHA-256
  `770fff0aaaa6cd539dc57b12f169b1a3bcfea33a6851c2892ef6826512b57a07`.

Warmups 13, 27, and 41 produced useful roots. Warmup 55 produced 0/21
accepted roots and the first warmup-69 continuation was 0/3, so later
collection was stopped and replaced with fresh productive-phase seeds. A
separate validation launch that accidentally reused one seed was caught,
stopped, and quarantined before compilation; only the corrected unique-seed
validation corpus above was used.

## Offline result

The original recurrent hazard play/wait gate was frozen. Only same-mode card
and tile preferences trained conditional action heads using the exact pilot
hyperparameters.

- selected epoch: 3;
- non-root exact retention: 99.826%;
- play/wait mode retention: 100%;
- corrective preference accuracy: 1.852% -> 16.667%;
- safety preference accuracy: 94.595% -> 100%;
- candidate SHA-256:
  `81f88aea052bf4abb3d2bbd91b188b11b6b07d828838df36f81a8ba710556ac4`.

## Gameplay rejection

The unchanged seven-opponent, 28-game-per-arm paired screen rejected the
candidate:

- parent: 17-11, +0.429 crowns/game;
- candidate: 12-16, -0.071 crowns/game;
- candidate minus parent: -5 wins, -0.500 crowns/game;
- regressions included balanced, random, slow-push, and split-lane;
- placement cadence remained approximately 7%, confirming that the frozen
  timing gate worked and the regression came from card/tile choices.

Raw gameplay summary:
`reports/hog26_strategy_proposal_scaled_conditional_seed1204501_development/summary.json`.

## Interpretation

The strategy proposals improve candidate coverage and the learned head can
fit some held-out pairwise preferences without changing cadence. Nevertheless,
both the six-root pilot and the 61-root scaled fit regress full games. More
roots or coefficient tuning under the same 24-decision objective is therefore
not justified. The short reward horizon is the remaining shared mismatch:
it rewards locally favorable damage/board changes that need not improve the
terminal match outcome.

Before another policy fit, rerun identical root/candidate sets at materially
longer horizons and measure best-action and margin stability. If the teacher
labels are unstable, replace the label objective with long-horizon or terminal
outcomes rather than patching the policy again.
