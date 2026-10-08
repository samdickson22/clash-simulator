# S4 results

Complete: 1280 games. Paired-matchup bootstrap (10,000 draws; both seats retained).

| Cell | Score | 95% CI |
| --- | ---: | --- |
| Full | 66.4% | [59.8, 73.0] |
| R-elixir | 72.7% | [66.0, 78.9] |
| R-hand | 72.3% | [65.6, 78.5] |
| R-derived | 84.4% | [78.9, 89.5] |
| ELT | 72.9% | [66.4, 78.9] |

## Registered contrasts

- R-elixir - Full: +6.2 pp [+0.0, +12.5]; material=False
- R-hand - Full: +5.9 pp [-0.4, +12.1]; material=False
- R-derived - Full: +18.0 pp [+11.7, +24.2]; material=True
- ELT - Full: +6.4 pp [+0.4, +12.5]; material=True
- interaction: +5.9 pp [-2.3, +14.1]

## Tracker diagnostics

| Cell | Coverage | Post-error coverage | Width | MAE | Hand mass ≥90% | Unanimity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 0.998 | 0.997 | 6.174 | 0.738 | 0.0034 | 0.0034 |
| R-elixir | 1.000 | 1.000 | 0.000 | 0.000 | 0.0028 | 0.0028 |
| R-hand | 0.999 | 0.998 | 6.185 | 0.733 | 0.1830 | 0.1830 |
| R-derived | 1.000 | 1.000 | 0.000 | 0.000 | 0.1938 | 0.1938 |
| ELT | 0.715 | 0.620 | 3.494 | 1.614 | 0.1154 | 0.0000 |

Game CPU: 29.62 core-hours. Supervisor/worker, development and preflight accounting are reported separately in compute-audit.json.

Manifest: `cc70d857ac3a3a3a1068eb730e701e78bdac9277c828a50355b2af260cb520e8`. Receipt aggregate: `95628321ee96c8d2d25486b40545c4cab36e77a0f60b6f49ffbd928f04114ed0`.

Truth is scoring-only except the registered public-derived repair inputs. Full/ELT anchors retain their original intervals. No outcome-based exclusions. Raw receipts stay on the fleet.
