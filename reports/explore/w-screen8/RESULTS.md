# W-screen8 fresh paired outcome check

600 fresh paired seeds; symmetric d=27; 5 decks/25 matchups; alternating seats; 1,800 terminal games.

| Arm | W/L/D | Loss %, paired 95% CI |
|---|---:|---:|
| Baseline | 295/305/0 | 50.83 [46.83, 54.83] |
| Full W | 483/117/0 | 19.50 [16.50, 22.67] |
| Screen8 | 484/116/0 | 19.33 [16.33, 22.50] |

Loss changes, pp (paired 95% CI): screen8−baseline **-31.50 [-35.83, -27.50]**; full W−baseline **-31.33 [-35.67, -27.33]**; screen8−full W **-0.17 [-1.00, +0.67]**.

**PASS:** screen8−full W upper CI ≤ +3 pp; 5,000 paired-bootstrap resamples.

| Full-decision wall latency, ms | p50 | p95 | p99 |
|---|---:|---:|---:|
| Baseline | 5.2 | 343.7 | 482.4 |
| Full W | 258.5 | 491.4 | 696.1 |
| Screen8 | 176.8 | 330.2 | 460.0 |

Full-decision timings include observation through submission under fleet load; no live qualification.

[Metrics/CPU latency](METRICS.md); [counts/CIs](results.json).

Default OFF. Parity: OFF 250/250 score/action/trace; ON 125/125 choices/retained scores; 54 tests. Runtime patch: none.

Commits: freeze `d0e9dc2f`; baseline `f9d3b454`; implementation `59454e1a`/`62044189`; report SHA in PROGRESS.
