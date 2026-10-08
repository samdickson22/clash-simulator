# S4 results and decision

**Only the joint public-derived repair and ELT meet the registered materiality rule.** R-hand does not: +5.859 pp [−0.391, +12.109]. R-elixir is +6.250 pp [0.000, +12.500]; its lower bound is exactly zero, so it also fails the strictly-positive rule. These intervals do not establish that either component has no effect. The interaction is +5.859 pp [−2.344, +14.062], with no resolved evidence of nonadditivity.

**Tracker v3 meets the N97 development target**, but no tracker-v3 strength confirmation was run: 20.63% resolved-hand rate, 91.52% correct among ≥90%-mass hands on dev validation. Same-trace ELT: 8.46% / 76.99%; T2: 2.06% / 49.40%; public-derived reference: 21.36% / 100%. N90/N64 remain uninformative at the ≥90% threshold. See TRACKER-V3.md for per-level resource metrics and full reliability curves.

**S5 PREREG was not drafted:** the user's required condition, material R-hand repair, was not met. No S5 games or tracker-v3 confirmation games were launched.

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

## Validation and integrity

All five pilots and three-seed terminal endpoint action-hash/count/tick equivalence passed. Both switches off reproduce S2 Full; both on reproduce S2 R-derived. Twenty-two final unit tests pass. The exact tracker path passed all 24 original P16 games (23,058 observations, zero errors). Tracker development uses only fresh public traces, never S4 confirmation outcomes.

All 1,280 terminal receipts, 152 successful partitions and both supervisor successes existed before outcome analysis. No confirmation exclusions, reruns or post-freeze changes. Independent receipt aggregation and score recomputation match. Final audits verify 468 S1, 473 S2, 518 S3 and 477 S4 frozen files without mismatch on 01/04/08.

Both seed audits passed: 04 scanned 974,508 seed fields / 10,209 NPZ archives; 01 scanned 990,204 / 14,803. Both retain 726 unavailable historical paths, limiting absolute historical-disjointness claims. PREREG was hashed before any S4 game; confirmation waited for both audits and all preflight evidence.

## Compute and operations

Game CPU: **29.62 core-hours**. Confirmation supervisor/worker CPU: **29.74**. Total attributable metered CPU: **at least 41.93 core-hours**, including development, preflight, failed tests and interrupted dev work. These totals overlap; do not add game CPU to the total. Confirmation game wall span: 20.53 minutes.

Three top-level 04 logs duplicated hub log bytes (snapshot, seed audit, final integrity); they are omitted from the total rather than double-counted. The 04 seed log explicitly declared the hub host. The responsible copying process is unidentified. See CPU-ACCOUNTING-NOTE.md and compute-audit.json for hashes and missing attribution. Game CPU and all outcome receipts are unaffected. Small copy/final-summary operations are unmetered.

All games and heavy replays ran on 04/08 at nice 10, one native/BLAS thread. Supervisors reserved host-wide headroom; observed Python counts stayed below 96, no console users were observed, and the launchers enforce a 16 cap when who is nonempty. Hub 01 performed light collection/registration. No engine/gamedata edits, sealed-study mutations, prohibited-host work, deleted data, service changes or commits. Only S4-owned source/docs/small evidence/results are mirrored to 05; raw receipts/traces and binaries remain on the fleet.

Development incidents and corrections are preserved in DEV-LOG.md. Original generated analysis is retained in RESULTS-generated.md; result.json is unchanged.
