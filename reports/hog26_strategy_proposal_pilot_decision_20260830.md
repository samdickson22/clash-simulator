# Hog 2.6 strategy-proposal conditional repair pilot

Decision: reject the six-root trained checkpoint, retain the proposal generator,
and scale replay-disjoint exact roots before one new conditional-action fit.

## Proposal evidence

Every root reserves the parent, wait, six tensor StrategyBot proposals, and
additional policy/spatial candidates. A 24-decision exact Simple-Gym rollout
with direct discounted reward selects the label.

| Split | Probes | Accepted roots | Corpus SHA-256 |
|---|---:|---:|---|
| train seed 1201101 | 14 | 6 | `681c3b610a1d39e883613773cf1c85d2331d94e0623fe669a7db6a1ec7dc96f3` |
| validation seed 1201201 | 7 | 5 | `8555c0b4aaa2cf322fc6fd7ac8a14a89199be4e1e44774a4227cdb78479d7db9` |

Strategy proposals supplied three accepted improvements in each split; the
remaining accepted improvements came from policy/spatial candidates. The
combined 11/21 acceptance rate materially exceeds the earlier generic probe
yield and proves that the proposal sources are complementary.

## Conditional repair

The source hazard play/wait gate was frozen. Only same-mode complete-action
preferences trained card and tile heads. The selected epoch retained 99.65%
non-root exact actions, preserved play/wait mode exactly, improved held-out
corrective preference accuracy from 0% to 30.77%, and preserved safety
preference accuracy at 94.44%.

- checkpoint SHA-256: `442a98050d63d668132e9dd50663ace2a29175265c214fe707f08a297555a9a5`
- offline report: `reports/hog26_strategy_proposal_conditional_seed1201301.json`

## Gameplay rejection

The exact seven-opponent paired development screen rejected the checkpoint:

- parent: 12-16, +0.179 crowns/game;
- candidate: 8-20, -0.643 crowns/game;
- candidate minus parent: -4 wins and -0.821 crowns/game;
- placement cadence remained approximately 7.0% for both arms.

Raw summary:
`reports/hog26_strategy_proposal_conditional_seed1201301_development/summary.json`.

The checkpoint is audit-only and must not initialize another lineage. Because
cadence stayed fixed, this is direct evidence of card/tile overfitting from six
training roots. No learning-rate or coefficient sweep is authorized on this
pilot. The next conditional fit requires at least an order of magnitude more
accepted train roots, replay-disjoint validation, the same frozen timing gate,
and the unchanged paired gameplay rejection rules.
