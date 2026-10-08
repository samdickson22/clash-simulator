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

## Implementation and validation

S6-owned flag-controlled native planner wrapper and simulator command channel. Engine, gamedata, native binary and frozen S4 tracker v3 are unchanged. Single pending command, optimistic own spend/slot reservation at submission, one engine execution at the due tick, and unchanged 160-tick horizon.

25 unit tests passed. The initial failed unit fixture used duplicate synthetic cards; its log is retained and the legal eight-card fixture passes. Three terminal development seeds reproduce identical action hashes/counts/ticks for d=0 aware, unaware and original Player B. Five outcome-suppressed pilots passed. All 1,280 confirmation games completed; independent receipt and bootstrap recomputation matched exactly. Final frozen-file audits passed on 01/04/08.

## Seed audit and limits

- 127x01: 170,611 text files and 18,357 NPZ archives; 0 errors, 0 collisions, 726 unavailable historical paths.
- 127x04: 152,956 text files and 10,209 NPZ archives; 0 errors, 0 collisions, 726 unavailable historical paths.

Freshness is established against retained readable evidence; unavailable historical paths prevent an absolute all-history disjointness claim.

## Resource accounting

- Game CPU: 21.125 core-hours.
- Confirmation supervisors plus reaped workers: 22.303 core-hours.
- Preflight and metered operations: 0.459 core-hours.
- Total metered CPU: 22.762 core-hours.
- Game CPU overlaps supervisor/worker CPU and is not added again. Small transfers and final report rendering are unmetered.

## Pending-command diagnostics

| Cell | Submissions | Executions | Pending at terminal | Blocked polls | Rejections |
| --- | ---: | ---: | ---: | ---: | ---: |
| clean-d0 | 14025 | 14025 | 0 | 0 | 3 |
| clean-d22-unaware | 14282 | 14182 | 100 | 156483 | 4 |
| clean-d22-aware | 14497 | 14380 | 117 | 158765 | 13 |
| T3-N97-d22-unaware | 15944 | 15812 | 132 | 174524 | 542 |
| T3-N97-d22-aware | 17420 | 17303 | 117 | 190807 | 591 |

Blocked polls measure enforced command occupancy, not counterfactual demand for a second play. The harness does not search while a command is pending. Scores validate this fixed simulator model; they do not establish a renderer or production-actuator qualification. Raw receipts remain on 01/04/08. Code, preregistration, hashes, small receipts and results are mirrored to 05. No commits.

## Operational interruptions and accounting attribution

04 made 126 capacity-triggered partition interruptions/resumes; 08 made none.
Identical incomplete inputs were resumed, terminal receipts remained immutable,
and outcomes stayed unread until the complete barrier. See OPERATIONS.md for the
host-wide thread spike and retained process/launch evidence. Confirmation took
15.38 minutes from first game start to final game end. The interrupted CPU is
included in the 22.303 confirmation supervisor/worker core-hours.

Seven mirrored logs were removed from CPU attribution using exact-byte/prefix
proofs; the original aggregate remains retained. See CPU-ACCOUNTING-NOTE.md.
This post-analysis reporting correction changes no score, CI, frozen source or
raw receipt. Final report rendering and small copies are unmetered.
