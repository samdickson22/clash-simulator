# S3 results

Complete: 1792 games. Paired-matchup bootstrap (10,000 draws; both seats retained).

| Cell | Score | 95% CI |
| --- | ---: | --- |
| T2-N97 | 65.0% | [57.8, 72.1] |
| T2-N90 | 64.5% | [57.0, 71.5] |
| Full-N97 | 64.8% | [57.4, 71.9] |
| Full-N90 | 62.9% | [55.5, 69.9] |
| ELT-N97 | 70.7% | [63.7, 77.3] |
| R-derived | 80.1% | [74.2, 85.5] |
| T2-N64 | 56.6% | [48.8, 64.1] |

## Registered contrasts

- primary: +1.6 pp [-4.7, +7.8]; FAIL
- secondary: +0.2 pp [-6.4, +6.8]; FAIL
- ceiling_gap: +15.0 pp [+8.8, +21.5]

## Tracker diagnostics

| Cell | Coverage | Post-error coverage | Width | MAE | Hand mass ≥90% | Unanimity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| T2-N97 | 0.891 | 0.854 | 2.780 | 0.701 | 0.0132 | 0.0000 |
| T2-N90 | 0.902 | 0.895 | 2.757 | 0.741 | 0.0004 | 0.0000 |
| Full-N97 | 0.999 | 0.998 | 6.128 | 0.727 | 0.0052 | 0.0052 |
| Full-N90 | 0.993 | 0.992 | 6.675 | 0.759 | 0.0007 | 0.0007 |
| ELT-N97 | 0.711 | 0.612 | 3.417 | 1.641 | 0.0962 | 0.0000 |
| R-derived | 1.000 | 1.000 | 0.000 | 0.000 | 0.1619 | 0.1619 |
| T2-N64 | 0.933 | 0.933 | 4.230 | 0.827 | 0.0000 | 0.0000 |

Game CPU: 41.97 core-hours. Supervisor/worker, development and preflight accounting are reported separately in compute-audit.json.

Manifest: `7f2a2f72c573828433808fc1b2153eb0fc74b30c6193319dfb897e0ad4d658d9`. Receipt aggregate: `9a9b38ae9543770206b7d6c7d170d958ced5aa01d70c5912698d74d6ab26bdc3`.

Truth is scoring-only. T2 intervals use the calibration-split radius frozen before confirmation. Full/ELT anchors retain their original intervals. No outcome-based exclusions. T2-N64 is descriptive. Raw receipts stay on the fleet.
