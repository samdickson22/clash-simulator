# X4S2 tables (generated 2026-10-11T08:22:36Z from results.json; exploration, NEVER ADOPTABLE)

## Arms: X population (X4S five decks, X4S seeds; `x4s:` = X4S games)

| Arm | Seeds | Loss % [95% CI] | Cutoff % | Student-default % | Coarse complete at cutoff % | Play % | Poll ms | Scale sleep ms | Prep ms | Wall p50/p95 ms |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|

## Arms: G population (L2-v4 own decks vs held-out guard decks, fresh seeds)

| Arm | Seeds | Loss % [95% CI] | Cutoff % | Student-default % | Coarse complete at cutoff % | Play % | Poll ms | Scale sleep ms | Prep ms | Wall p50/p95 ms |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| K4-140 | 540 | 58.7 [54.4, 62.8] | 44.2 | 0.0 | 66.8 | 26.1 | 10.8 | 0.0 | 43.1 | 127.8/132.9 |
| K4-200 | 540 | 23.7 [20.2, 27.4] | 2.0 | 0.0 | 63.0 | 34.1 | 10.3 | 0.0 | 40.3 | 119.3/172.5 |
| K4S-140 | 540 | 27.2 [23.5, 31.1] | 34.4 | 8.9 | 73.8 | 33.8 | 10.5 | 0.0 | 40.6 | 120.8/133.0 |
| K4S-200 | 540 | 24.1 [20.6, 27.8] | 2.0 | 0.3 | 62.9 | 34.2 | 10.4 | 0.0 | 40.2 | 118.9/173.3 |
| K4Sh-140 | 540 | 24.3 [20.7, 28.1] | 49.6 | 14.7 | 64.6 | 33.9 | 10.6 | 4.6 | 50.3 | 132.1/133.0 |

## Paired contrasts (loss pp, paired-seed bootstrap 95% CI, unadjusted)

| Contrast | Seeds | pp | 95% CI |
|---|---:|---:|---|
| G: K4S-200 minus K4-200 | 540 | +0.4 | [-2.4, 3.1] |
| G: K4S-140 minus K4-140 | 540 | -31.5 | [-36.7, -26.3] |
| G: K4Sh-140 minus K4-140 | 540 | -34.4 | [-39.4, -29.3] |
| G: K4Sh-140 minus K4S-140 | 540 | -3.0 | [-7.4, 1.5] |
| G: K4-140 minus K4-200 | 540 | +35.0 | [30.2, 39.6] |
| G: K4S-140 minus K4-200 | 540 | +3.5 | [-1.3, 8.1] |
| G: K4Sh-140 minus K4-200 | 540 | +0.6 | [-4.1, 5.4] |
| G: K4S-140 minus K4S-200 | 540 | +3.1 | [-1.5, 7.8] |

Blocks per phase: {'rep03': 270, 'rep08': 270}; blocks per host: {'127x03': 270, '127x08': 270}; excluded interrupted blocks: 0.
