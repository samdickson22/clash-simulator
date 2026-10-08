# S5 results

Complete: 1536 games. Paired-matchup bootstrap (10,000 draws; both seats retained).

| Cell | Score | 95% CI |
| --- | ---: | --- |
| T3-N97 | 70.3% | [63.3, 77.0] |
| ELT-N97 | 69.9% | [62.9, 76.6] |
| Full-N97 | 62.1% | [54.7, 69.5] |
| R-derived | 77.3% | [71.5, 83.2] |
| T3-N90 | 68.0% | [60.9, 75.0] |
| Full-N90 | 59.4% | [52.0, 66.8] |

## Registered contrasts

- primary: +8.2 pp [+2.3, +14.5]; PASS
- secondary_elt: +0.4 pp [-5.5, +6.2]; FAIL
- secondary_n90: +8.6 pp [+3.1, +14.5]; PASS
- ceiling_gap: +7.0 pp [+2.0, +12.1]

## Tracker diagnostics

| Cell | Coverage | Post-error coverage | Width | MAE | Hand mass ≥90% | Hand accuracy | Unanimity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| T3-N97 | 0.890 | 0.845 | 2.824 | 0.729 | 0.2409 | 0.9084 | 0.0000 |
| ELT-N97 | 0.707 | 0.606 | 3.624 | 1.687 | 0.1031 | 0.7375 | 0.0000 |
| Full-N97 | 0.999 | 0.998 | 6.215 | 0.748 | 0.0113 | 0.7671 | 0.0113 |
| R-derived | 1.000 | 1.000 | 0.000 | 0.000 | 0.1770 | 1.0000 | 0.1770 |
| T3-N90 | 0.892 | 0.884 | 2.791 | 0.769 | 0.0002 | 1.0000 | 0.0000 |
| Full-N90 | 0.991 | 0.990 | 6.787 | 0.787 | 0.0013 | 0.1266 | 0.0013 |

Game CPU: 36.95 core-hours. Supervisor/worker, development and preflight accounting are reported separately in compute-audit.json.

Manifest: `692e774a4a914e79b530a64730ff946c6e0dadacd7a2bf6a55803903bd187af9`. Receipt aggregate: `4230dc824f132e798dbfdfd88017cf2e25888956903e49db30f9bde01aabccc6`.

Truth is scoring-only. T3 uses unchanged S4 tracker v3 and frozen S3 interval radii. Full/ELT anchors retain their original intervals. No outcome-based exclusions. Unanimity retains the S3 definition and is distinct from the >=90%-mass rate. Raw receipts stay on the fleet.

## Integrity and operations

Independent recomputation matched all 1,536 receipts, six scores, all score CIs, and all four paired contrasts/CIs. Receipt aggregate 4230dc824f132e798dbfdfd88017cf2e25888956903e49db30f9bde01aabccc6.

All S1–S5 frozen manifests and the separately frozen S4 tracker dependencies pass final audits on 01/04/08. No confirmation reruns, exclusions, tracker changes or engine/gamedata edits. Both seed audits passed; 726 unavailable historical paths limit absolute historical-disjointness claims. The only preflight failure was a new test comparing rounded decimal radii with exact float equality; test-only correction passed and original failed log is retained.

Game CPU: 36.954 core-hours. Confirmation supervisor/worker CPU: 37.099. Total metered CPU: at least 38.079. These overlap; do not add them. Small finalization/copy operations are unmetered. Confirmation wall span: 17.75 minutes.

Games used 04/08 only, nice 10, one native/BLAS thread; console-user capacity reserved headroom. Hub 01 performed collection/analysis; 05 received only code/docs/small receipts/results. Raw terminal receipts stay on the fleet. No commits or data deletion.
