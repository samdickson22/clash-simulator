# X4S2 tables (generated 2026-10-11T10:35:26Z from results.json; exploration, NEVER ADOPTABLE)

## Arms: X population (X4S five decks, X4S seeds; `x4s:` = X4S games)

| Arm | Seeds | Loss % [95% CI] | Cutoff % | Student-default % | Coarse complete at cutoff % | Play % | Poll ms | Scale sleep ms | Prep ms | Wall p50/p95 ms |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|

## Arms: G population (L2-v4 own decks vs held-out guard decks, fresh seeds)

| Arm | Seeds | Loss % [95% CI] | Cutoff % | Student-default % | Coarse complete at cutoff % | Play % | Poll ms | Scale sleep ms | Prep ms | Wall p50/p95 ms |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| K4-140 | 1068 | 58.6 [55.6, 61.7] | 45.1 | 0.0 | 66.9 | 25.8 | 10.8 | 0.0 | 43.1 | 128.5/132.9 |
| K4-200 | 1068 | 26.7 [24.0, 29.3] | 2.1 | 0.0 | 62.0 | 34.2 | 10.3 | 0.0 | 40.3 | 119.7/173.0 |
| K4S-140 | 1068 | 27.2 [24.6, 30.0] | 35.1 | 9.0 | 74.5 | 33.8 | 10.5 | 0.0 | 40.6 | 121.3/133.0 |
| K4S-200 | 1068 | 26.4 [23.8, 29.1] | 2.0 | 0.3 | 60.7 | 34.2 | 10.4 | 0.0 | 40.2 | 119.1/172.5 |
| K4Sh-140 | 1068 | 23.5 [21.0, 26.0] | 49.7 | 14.7 | 64.4 | 33.7 | 10.5 | 4.6 | 50.3 | 132.1/133.0 |

## Paired contrasts (loss pp, paired-seed bootstrap 95% CI, unadjusted)

| Contrast | Seeds | pp | 95% CI |
|---|---:|---:|---|
| G: K4S-200 minus K4-200 | 1068 | -0.3 | [-2.2, 1.7] |
| G: K4S-140 minus K4-140 | 1068 | -31.4 | [-34.9, -27.6] |
| G: K4Sh-140 minus K4-140 | 1068 | -35.1 | [-38.8, -31.5] |
| G: K4Sh-140 minus K4S-140 | 1068 | -3.7 | [-6.9, -0.6] |
| G: K4-140 minus K4-200 | 1068 | +31.9 | [28.3, 35.4] |
| G: K4S-140 minus K4-200 | 1068 | +0.6 | [-2.8, 3.9] |
| G: K4Sh-140 minus K4-200 | 1068 | -3.2 | [-6.6, 0.2] |
| G: K4S-140 minus K4S-200 | 1068 | +0.8 | [-2.4, 4.0] |

Blocks per phase: {'rep03': 270, 'rep08': 472, 'rep08L': 56, 'rep03C': 270}; blocks per host: {'127x03': 540, '127x08': 528}; excluded interrupted blocks: 12.
