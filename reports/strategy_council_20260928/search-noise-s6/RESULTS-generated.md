# S6 results

Complete: 1280 games. Paired-matchup bootstrap (10,000 draws; both seats retained).

| Cell | Score | 95% CI |
| --- | ---: | --- |
| clean-d0 | 89.5% | [84.8, 93.8] |
| clean-d22-unaware | 72.3% | [65.2, 78.9] |
| clean-d22-aware | 86.7% | [81.6, 91.4] |
| T3-N97-d22-unaware | 50.8% | [43.4, 58.2] |
| T3-N97-d22-aware | 60.2% | [52.7, 67.6] |

## Registered contrasts

- primary: +14.5 pp [+8.6, +20.3]; PASS
- secondary: +9.4 pp [+3.9, +15.2]; PASS
- latency_cost: +2.7 pp [-2.0, +7.4]

## Tracker diagnostics

| Cell | Coverage | Post-error coverage | Width | MAE | Hand mass ≥90% | Hand accuracy | Unanimity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| clean-d0 | 1.000 | n/a | 0.000 | 0.000 | 0.1820 | 1.0000 | 0.1820 |
| clean-d22-unaware | 1.000 | n/a | 0.000 | 0.000 | 0.1987 | 1.0000 | 0.1987 |
| clean-d22-aware | 1.000 | n/a | 0.000 | 0.000 | 0.1652 | 1.0000 | 0.1652 |
| T3-N97-d22-unaware | 0.917 | 0.888 | 2.385 | 0.495 | 0.1422 | 0.9217 | 0.0000 |
| T3-N97-d22-aware | 0.918 | 0.893 | 2.443 | 0.510 | 0.1432 | 0.9168 | 0.0000 |

Game CPU: 21.13 core-hours. Supervisor/worker, development and preflight accounting are reported separately in compute-audit.json.

Manifest: `198d3855e37280d463dbac3b7b30abc5fe04386665fcca2cd942ee7f6d576e60`. Receipt aggregate: `9a1b680277a4e0003fe5453526014f9e702ba4487a127dce6778fb68f9c72f6d`.

Truth is scoring-only. Noisy cells use unchanged S4 tracker v3 and frozen S3 interval radii. Clean cells use exact public deduction. No outcome-based exclusions. Unanimity retains the S3 definition and is distinct from the >=90%-mass rate. Raw receipts stay on the fleet.
