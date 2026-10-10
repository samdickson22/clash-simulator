# S1 one-core cached student search

Completed 2026-10-10T12:47:23Z. **1-core student tier viable.**

S-200 lost 28.17%, versus cached-v1 K0c-200 44.17% and K2-200 29.00%. Its paired advantage over cached v1 was −16.00 pp [−21.00, −11.17]; against K2 it was −0.83 pp [−5.33, +3.50]. Both frozen upper-CI margins pass. At 160 ms, student loss rose to 32.17%: +4.00 pp [−0.17, +8.33], while cached-v1 loss rose to 79.00%: +34.83 pp [30.17, 39.67]. The student’s slowdown estimate remains uncertain within that interval.

Exploration only: 3,000 terminal games, 600 fresh paired seeds per arm; symmetric d=27/capacity1, five decks/25 matchups/alternating seats, the exact K2 plain v1 policy opponent. All five arms run in rotated order on the same physical slot. No Mac, live or heldout access.

| Arm | W/L/D | Loss %, paired-seed 95% CI | Cutoff %, 95% CI | Fallback %, 95% CI | Latency p50/p95/p99/max, ms |
|---|---:|---:|---:|---:|---:|
| K0c-200 | 335/265/0 | 44.17 [40.17, 48.17] | 82.33 [81.35, 83.27] | 53.00 [50.81, 55.16] | 192.522/192.717/193.015/226.405 |
| S-200 | 431/169/0 | 28.17 [24.67, 31.67] | 61.78 [60.78, 62.81] | 19.33 [18.15, 20.58] | 192.523/192.688/192.844/215.626 |
| K0c-160 | 126/474/0 | 79.00 [75.67, 82.33] | 97.92 [97.70, 98.14] | 93.19 [92.61, 93.77] | 152.499/152.681/152.863/186.235 |
| S-160 | 407/193/0 | 32.17 [28.50, 36.00] | 75.43 [74.45, 76.36] | 50.86 [49.68, 52.06] | 152.542/152.687/152.846/183.937 |
| K2-200 | 426/174/0 | 29.00 [25.33, 32.67] | 27.19 [25.48, 28.90] | 0.73 [0.71, 0.76] | 160.944/192.896/193.008/218.055 |

| Paired loss contrast | pp, 95% CI |
|---|---:|
| S-200 minus K0c-200 | -16.00 [-21.00, -11.17] |
| S-160 minus K0c-160 | -46.83 [-51.33, -42.33] |
| S-200 minus K2-200 | -0.83 [-5.33, 3.50] |
| S-160 minus S-200 | 4.00 [-0.17, 8.33] |
| K0c-160 minus K0c-200 | 34.83 [30.17, 39.67] |

Frozen rule: S-200−K0c-200 upper CI≤−10 pp and S-200−K2-200 upper CI≤+5 pp. Observed upper bounds -11.17 pp and 3.50 pp; component passes [True, True].

| Arm | Decisions | Positive overrun count / % | Overrun p50/p95/p99/max, ms | Extra-delay ticks | Cut returns >deadline+8 ms |
|---|---:|---:|---:|---|---:|
| K0c-200 | 129378 | 72 / 0.056% | 6.633/15.531/21.718/26.405 | {"1": 72} | 22 |
| S-200 | 90303 | 48 / 0.053% | 3.584/8.847/14.666/15.626 | {"1": 48} | 5 |
| K0c-160 | 188565 | 139 / 0.074% | 9.052/16.663/19.724/26.235 | {"1": 139} | 80 |
| S-160 | 110001 | 106 / 0.096% | 6.340/11.768/14.595/23.937 | {"1": 106} | 32 |
| K2-200 | 73687 | 79 / 0.107% | 4.809/12.140/15.335/18.055 | {"1": 79} | 19 |

The timer starts before public observation and charges the single cached model inference, belief preparation, top-8 candidate proposals, public root, scoring and submission. Scoring cutoffs are 192/152 ms with an 8 ms reserve. Every positive overrun is retained and charged as ceil(overrun×20) additional ticks to command due time, own availability and timed waits. Partial and late roots never count. The frozen K2 anchor uses its byte-exact WAIT-first two-worker collector; the one-core arms use coarse-first scoring. K0c differs from K2’s policy-only K0 and the earlier R3 mirror.

| Arm | GC count / generation counts | Pause p50/p95/p99/max, ms | >50/250/500 ms counts | GC ms per simulated game minute | During decision |
|---|---:|---:|---:|---:|---:|
| K0c-200 | 13618 / {"0": 12398, "1": 1133, "2": 87} | 0.304/3.141/7.807/145.013 | 87/0/0 | 10.246 | 0 |
| S-200 | 14873 / {"0": 13564, "1": 1225, "2": 84} | 0.294/3.232/8.053/128.917 | 84/0/0 | 10.833 | 0 |
| K0c-160 | 12645 / {"0": 11508, "1": 1055, "2": 82} | 0.283/2.904/6.902/146.542 | 82/0/0 | 9.412 | 0 |
| S-160 | 14654 / {"0": 13331, "1": 1218, "2": 105} | 0.297/3.126/8.140/148.165 | 105/0/0 | 11.898 | 0 |
| K2-200 | 15966 / {"0": 14550, "1": 1308, "2": 108} | 0.495/3.780/8.836/151.507 | 108/0/0 | 14.706 | 0 |

GC is deferred only during decisions and remains in whole-game wall/CPU. Maintenance does not advance simulated ticks or incur decision lateness. The inherited instrumentation has no pause timestamps or live poll/opportunity state; maintenance overlap and resulting live loss remain unknown. Zero collections during a decision does not prove zero delayed live polls.

Qualifications: 125/125 frozen coarse-first and K2 no-deadline actions/candidates/scores/root checks; exact proposal-augmented frozen scoring; cached-v1 versus double-inference actions/proposals/RNG; cached student versus canonical R3 TimedPolicy; charged student inference assertions; injected-clock, non-drain/pool-reuse, belief and GC tests. Excluded 40-game smoke passed. [Qualification](receipts/qualification.json), [tests](receipts/qualification.log), [belief qualification](receipts/belief-qualification.json).

Statistics: 5000 shared paired-seed percentile bootstrap resamples, RNG 2026101026; unadjusted pointwise 95% CIs. Draws remain separate. Cutoff/fallback/overrun intervals resample per-game numerator and denominator totals. No early reporting-outcome reduction, optional stopping or outcome-dependent retuning.

Source freeze dfefec9f74b8e9af6709051c218680a527f573bb; native SHA 44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2; R3a EMA SHA 37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85; threshold 0.5005528330802917. Reporting 4503602707370496+[0,600), excluded smoke 4503602617370496+[0,8). [Plan](PLAN.md), [seed audit](seed-audit.json), [raw hashes/statistics](results.json), [R2 runtime pin](receipts/runtime-pin-r2.json), [execution audit](receipts/execution.json), [GC supplement](gc-maintenance.json).

Fleet: 127x01 only, physical 0–39, nice10/SCHED_OTHER; K2 uses two workers plus main (3 cores), others one core. R3 priority and final release were independently checked before S1. All reporting PGIDs exited and [final vacancy](receipts/host-audit-final.json) passed. Metered whole-tree study CPU 45.767 hours; nested per-game diagnostic CPU is not added again. Small repository authoring, transfer sender, scanner and independent metadata audit overhead is disclosed separately.

R3a remains killed and NEVER-ADOPTABLE under its original Stage 1 gates. This study reports a compute-tier comparison and does not override those gates. Fleet strength does not qualify loaded Mac timing or live admission; see [S1 Mac tier](MAC-TIER.md).

Operational provenance: the original [freeze](FROZEN.json), plan and seed audit remain preserved in [R1 history](history/r1/PLAN.md). Reporting attempt 1 stopped at 09:07:53Z when the exclusive-host guard detected an obsolete T11 checkpoint poller. Its one terminal game and zero complete blocks were never opened for outcome analysis and are entirely excluded; its 18.317127 CPU seconds remain in the cost audit. The owner retired the poller at 09:14:04Z. Coordinator-authorized [R2 amendment](FROZEN-R2.json), commit `dfefec9f`, was scanned/pushed before the 09:16:58Z restart on the new seed bank. Excluded smoke remains the original 40 games. No timing algorithm, model, threshold, arm, reducer or statistical settings changed.

The complete reporting barrier opened only after 3,000 fresh terminal games/600 blocks, clean exit and unchanged source pins. The [independent integer-count paired-bootstrap check](receipts/statistics-verification.json), authored/committed before outcomes opened, verified all raw game hashes and matched every loss/contrast interval within 1.43e−14 pp; both decision components agree. [Physical topology](receipts/physical-topology.json) confirms 40 distinct selected physical cores without SMT siblings. Repeated independent host audits and the supervisor guard found no further foreign compute after the R2 restart. All 444 positive overruns were charged one extra tick each; no event exceeded 50 ms of positive overrun.

Protocol notes: the original corpus transfer used a 20,000 KiB/s cap (20.48 decimal MB/s), 2.4% above a strict decimal 20 MB/s limit. Source and receiver ran at nice 19, the synchronous transfer finished before qualification/reporting, both frozen file hashes verified, and no detached transfer process remained on 03. Actual peak rate was not measured; see the unchanged [transfer receipt](receipts/corpus-transfer.json) and additive [cap discrepancy](receipts/corpus-transfer-cap-note.json). A post-launch [filename coverage supplement](receipts/seed-filename-coverage.json) checked 12 older FROZEN/prereg JSON variants outside the original freeze glob, including 7,367 numeric seed declarations and helper mappings: zero overlaps. The original frozen audit remains unchanged.

Analysis cost includes the clean 12.057292 CPU-second reduction/GC/verification tree. An initial analysis launcher failed on `taskset -c39` syntax before Python or reduction started; its group exited and its log/receipt are preserved. The corrected launch used `taskset -c 39`; failed launcher CPU was unmetered and is explicitly not counted as zero. Other small authoring, transfer, scanner, publication and independent metadata-audit overhead is unmetered. [Failure receipt](receipts/postprocess-launch1-failure.json), [analysis barrier](receipts/analysis-barrier.json), [analysis meter](receipts/auxiliary-meters/postprocess.json).
