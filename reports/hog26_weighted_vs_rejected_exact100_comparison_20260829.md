# Weighted versus rejected exact-ID 0–99 comparison

The clean weighted run and rejected uniform-sampled predecessor use the same
policy, game IDs, seeds, strategy/seat schedule, query schedule, and terminal
ordering. Their sampled opponent decks differ because the corrected asymmetric
sampler now respects the pool weights.

| Metric | Rejected uniform | Clean weighted |
|---|---:|---:|
| Games | 100 | 100 |
| Decision roots | 924 | 871 |
| Mean roots/game | 9.24 | 8.71 |
| Parent terminal win rate | 37.0% | 27.0% |
| Parent no-op rate | 96.320% | 92.308% |
| Terminal-label no-op rate | 34.091% | 33.410% |
| Hog-optimal rate | 6.061% | 5.052% |
| Explicit corrections into Hog | 52 | 41 |

The ten-point parent win-rate change and four-point no-op change show that the
sampling correction materially changes matchup difficulty and policy behavior;
it is not only a metadata fix. The rejected corpus therefore cannot substitute
for the weighted authority even though its labels were internally consistent.
These first-100 differences are descriptive and do not predict the fitted
ranker's eventual performance.
