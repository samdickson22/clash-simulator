# S2 results

Complete: 3,584 games. A−Full: +27.7 pp [+21.5, +34.0].

95% percentile intervals use 10,000 paired-matchup bootstrap resamples, both seats retained, RNG 9711100003. No outcome-based exclusions.

| Cell | Games | Score (95% CI) |
| --- | ---: | --- |
| Full | 256 | 66.4% [59.4, 73.0] |
| R-derived | 256 | 81.6% [75.8, 87.1] |
| R-board | 256 | 71.5% [64.5, 78.1] |
| R-hp | 256 | 69.5% [62.1, 76.6] |
| R-own | 256 | 62.5% [55.1, 69.5] |
| R-events | 256 | 81.6% [75.8, 87.1] |
| R-latency | 256 | 72.7% [65.6, 79.3] |
| R-taps | 256 | 66.4% [59.4, 73.0] |
| A+derived | 256 | 79.7% [73.8, 85.2] |
| A+board | 256 | 87.9% [82.8, 92.2] |
| A+hp | 256 | 90.2% [85.5, 94.1] |
| A+own | 256 | 95.7% [92.6, 98.4] |
| A+latency | 256 | 92.6% [87.9, 96.5] |
| A | 256 | 94.1% [90.6, 97.3] |

## Repair gains (Repair−Full)

| Channel | Gain (95% CI) | Material by either test |
| --- | --- | --- |
| derived | +15.2 pp [+9.8, +21.1] | True |
| events | +15.2 pp [+9.8, +21.1] | True |
| latency | +6.2 pp [+0.0, +12.1] | False |
| board | +5.1 pp [-0.8, +10.9] | True |
| hp | +3.1 pp [-2.0, +8.2] | False |
| taps | +0.0 pp [+0.0, +0.0] | False |
| own | -3.9 pp [-9.8, +2.0] | False |

## Add costs

| Channel | A−Add (95% CI) | Add−A (95% CI) |
| --- | --- | --- |
| derived | +14.5 pp [+9.8, +19.5] | -14.5 pp [-19.5, -9.8] |
| board | +6.2 pp [+2.0, +10.9] | -6.2 pp [-10.9, -2.0] |
| hp | +3.9 pp [-0.4, +8.6] | -3.9 pp [-8.6, +0.4] |
| latency | +1.6 pp [-2.0, +5.5] | -1.6 pp [-5.5, +2.0] |
| own | -1.6 pp [-5.1, +1.6] | +1.6 pp [-1.6, +5.1] |

Materiality is repair LB>0 or Add−A UB<0; no multiplicity adjustment.

Sum of repair gains: +41.0 pp [+15.2, +67.2]. A−Full gap: +27.7 pp [+21.5, +34.0]. Sum minus gap: +13.3 pp [-9.0, +36.3].

R-events changes legacy posterior to ELT as explicitly requested, so its contrast mixes tracker and event effects. A+derived uses ELT, not the legacy posterior. Full already has zero injected tap failures, making R-taps a duplicate control. These qualifications also limit the interaction check.

## Derived-state diagnostics

| Cell | Elixir MAE | Coverage | Width | Hand concentrated |
| --- | ---: | ---: | ---: | ---: |
| Full | 0.745 | 0.998 | 6.226 | 0.0018 |
| R-derived | 0.000 | 1.000 | 0.000 | 0.1591 |
| R-board | 0.745 | 0.999 | 6.218 | 0.0023 |
| R-hp | 0.749 | 0.998 | 6.217 | 0.0037 |
| R-own | 0.743 | 0.999 | 6.218 | 0.0018 |
| R-events | 0.000 | 1.000 | 0.000 | 0.1591 |
| R-latency | 0.755 | 0.998 | 6.232 | 0.0044 |
| R-taps | 0.745 | 0.998 | 6.226 | 0.0018 |
| A+derived | 1.694 | 0.684 | 3.362 | 0.0000 |
| A+board | 0.000 | 1.000 | 0.000 | 0.1656 |
| A+hp | 0.000 | 1.000 | 0.000 | 0.1584 |
| A+own | 0.000 | 1.000 | 0.000 | 0.1535 |
| A+latency | 0.000 | 1.000 | 0.000 | 0.1673 |
| A | 0.000 | 1.000 | 0.000 | 0.1544 |

## Hog 2.6 (descriptive)

| Cell | Score (95% CI) |
| --- | --- |
| Full | 45.0% [27.5, 62.5] |
| R-derived | 55.0% [35.0, 75.0] |
| R-board | 50.0% [32.5, 67.5] |
| R-hp | 45.0% [27.5, 65.0] |
| R-own | 32.5% [15.0, 52.5] |
| R-events | 55.0% [35.0, 75.0] |
| R-latency | 42.5% [25.0, 60.0] |
| R-taps | 45.0% [27.5, 62.5] |
| A+derived | 55.0% [37.5, 72.5] |
| A+board | 70.0% [52.5, 85.0] |
| A+hp | 85.0% [75.0, 95.0] |
| A+own | 95.0% [87.5, 100.0] |
| A+latency | 87.5% [72.5, 100.0] |
| A | 85.0% [72.5, 95.0] |

Game CPU: 77.31 core-hours; successful workers including initialization: 77.53; supervisors plus workers: 77.57; preflight: 0.56. These are overlapping totals, not additive. Confirmation elapsed: 0.69 hours.

Manifest: b2d65cb5eaadc081871d100f8f9127f4da10bc7ef7d0fcf0986f08733a5d301b. Receipt aggregate: 99d0477ca5fe9a1e825fae8b699a6822e3ed05b15e2ecfd517564e182c2f2077.

See ELT-DIAGNOSIS.md for event-aligned evidence; result.json contains all family contrasts, noise counts, decision timings and diagnostics. Raw receipts remain on the fleet.
