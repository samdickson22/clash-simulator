# PTR1 results

Generated 2026-10-18T10:23:35.439529+00:00. Preregistration: [PTR1-PREREG.md](PTR1-PREREG.md). Reference `res-lb-RF-wintp`; primary `res-lb-RF-pt5-wintp` (λ=.005); secondary `res-lb-RF-pt2-wintp` (λ=.002). `acc` is the account row; `all` is the equal-count pool of the three opponents. Source tree `45ed20a7ae7f`.

| Arm | Role | PASS/FAIL | K4 lower CI ≥0 | Both K4 rows ≥−.02 | HPv2 pooled ≥0 | Metrics within 2 SE | Adverse metrics beyond 2 SE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pt5 | primary | FAIL | True | True | True | False | barrel_answer_share, Zap_enemy_in_radius_share |
| pt2 | secondary exploratory | FAIL | True | True | True | False | Zap_enemy_in_radius_share |

PASS requires all four preregistered conditions. A secondary pt2 PASS is exploratory and does not authorize shipping. No live change, sealing, commit or repository code edit was performed. The metric tolerance is adverse change >2 paired-case SE; the main metric gate pools both level rows and all three opponents, following the LP2/KV1 comparison convention. All stratified contrasts and their adverse flags are also disclosed below. CPU, reaction, plays/game and Cannon location are descriptive; the preregistered gate names idle share, wincon spend, crossing elixir, Barrel answers, wrong lane and spell proximity. Both the standing and reproduced PT1 idle/spend definitions are shown and conservatively checked. Hog crossing mean, median, share ≥6 and Cannon+3 are checked.

## Integrity and run receipt

Raw rows 3600; unique valid 3600; identical command/outcome duplicates counted once 0; error rows retained in audit 0. Rows by level `{'l16': 1800, 'acc': 1800}`; hosts `{'127x04': 1800, '127x08': 1800}`. Expected and checked: 200 paired cases per opponent per level row, 600 cases per arm per level row, 3600 valid games total. Every accepted pair matches seed, seat, ordered own/opponent deck and truth levels. Own deck is the live Hog deck, RF enabled in every arm. L16 truth levels are all 16; account own levels are Skeletons7/Archers8/Valkyrie7/Cannon9/Fireball7/Zap9/ElectroSpirit8/HogRider8, King7; enemy logged levels and King9. No Goblin Hut; 53 registered source rows; clean noise.

Bank BASE 1962852923111632; opponent offsets 0/201/402, indexes 0–199, seats index%2. The three opponent seed ranges are disjoint and disjoint from PT1 BASE 68725711644388 and its case ranges. Each row bank SHA256 is matched against its raw row, and expected complete bank contents and case metadata are checked. Every valid result is terminal and has no row errors/issues/failures/live_errors. Original errors, if any, remain in the audit; authorized one-time reruns and identical-duplicate handling are disclosed. No early stopping or outcome-dependent exclusion.

| Host | Shard | Launched UTC | Receipt PID/PGID | Logged end UTC / rc | Rows by attempt |
| --- | --- | --- | --- | --- | --- |
| 127x04 | l16-s0 | 2026-10-18T08:52:50Z | 2637284/2637284 | ['2026-10-18T09:57:27Z', '0'] | {'l16-s0': 180} |
| 127x04 | l16-s1 | 2026-10-18T08:52:50Z | 2637312/2637312 | ['2026-10-18T09:54:08Z', '0'] | {'l16-s1': 180} |
| 127x04 | l16-s2 | 2026-10-18T08:52:51Z | 2637351/2637351 | ['2026-10-18T09:53:33Z', '0'] | {'l16-s2': 180} |
| 127x04 | l16-s3 | 2026-10-18T08:52:51Z | 2637369/2637369 | ['2026-10-18T10:01:29Z', '0'] | {'l16-s3': 180} |
| 127x04 | l16-s4 | 2026-10-18T08:52:51Z | 2637393/2637393 | ['2026-10-18T09:54:07Z', '0'] | {'l16-s4': 180} |
| 127x04 | acc-s0 | 2026-10-18T08:52:51Z | 2637454/2637454 | ['2026-10-18T09:56:19Z', '0'] | {'acc-s0': 180} |
| 127x04 | acc-s1 | 2026-10-18T08:52:51Z | 2637508/2637508 | ['2026-10-18T09:55:38Z', '0'] | {'acc-s1': 180} |
| 127x04 | acc-s2 | 2026-10-18T08:52:51Z | 2637564/2637564 | ['2026-10-18T09:56:41Z', '0'] | {'acc-s2': 180} |
| 127x04 | acc-s3 | 2026-10-18T08:52:51Z | 2637600/2637600 | ['2026-10-18T09:58:08Z', '0'] | {'acc-s3': 180} |
| 127x04 | acc-s4 | 2026-10-18T08:52:51Z | 2637626/2637626 | ['2026-10-18T09:55:06Z', '0'] | {'acc-s4': 180} |
| 127x08 | l16-s5 | 2026-10-18T08:52:52Z | 4154402/4154402 | ['2026-10-18T10:13:25Z', '0'] | {'l16-s5': 180} |
| 127x08 | l16-s6 | 2026-10-18T08:52:52Z | 4154432/4154432 | ['2026-10-18T10:13:15Z', '0'] | {'l16-s6': 180} |
| 127x08 | l16-s7 | 2026-10-18T08:52:52Z | 4154460/4154460 | ['2026-10-18T10:13:03Z', '0'] | {'l16-s7': 180} |
| 127x08 | l16-s8 | 2026-10-18T08:52:52Z | 4154486/4154486 | ['2026-10-18T10:13:30Z', '0'] | {'l16-s8': 180} |
| 127x08 | l16-s9 | 2026-10-18T08:52:52Z | 4154528/4154528 | ['2026-10-18T10:13:12Z', '0'] | {'l16-s9': 180} |
| 127x08 | acc-s5 | 2026-10-18T08:52:52Z | 4154566/4154566 | ['2026-10-18T10:18:14Z', '0'] | {'acc-s5': 180} |
| 127x08 | acc-s6 | 2026-10-18T08:52:52Z | 4154635/4154635 | ['2026-10-18T10:15:16Z', '0'] | {'acc-s6': 180} |
| 127x08 | acc-s7 | 2026-10-18T08:52:53Z | 4154700/4154700 | ['2026-10-18T10:14:38Z', '0'] | {'acc-s7': 180} |
| 127x08 | acc-s8 | 2026-10-18T08:52:53Z | 4154736/4154736 | ['2026-10-18T10:13:48Z', '0'] | {'acc-s8': 180} |
| 127x08 | acc-s9 | 2026-10-18T08:52:53Z | 4154759/4154759 | ['2026-10-18T10:15:04Z', '0'] | {'acc-s9': 180} |

| Arm | Early/final paired command hashes compared | Differing command hashes |
| --- | --- | --- |
| pt5 | 1200 | 1200 |
| pt2 | 1200 | 1200 |

First paired hash check 2026-10-18T09:05:14.240206+00:00: pt5 differed in 41/41 available pairs. Full hashes are in the watch history.

First paired hash check 2026-10-18T09:05:14.240206+00:00: pt2 differed in 38/38 available pairs. Full hashes are in the watch history.

Reruns: none. The watcher checked shard liveness, terminal rc, row errors and early command hashes every ten minutes on 127x04/08. An initial self-SSH attempt to 127x05 returned rc255; `hostname` established the watcher already ran on 127x05, so local scorer access was used. This did not affect jobs or data.

## Paired score contrasts

Win=1, draw=.5. The unchanged RF1/scale_report bootstrap uses 4000 matched-case draws with Python `random.Random(0)`, sorted draws [100,3900], independently for each arm/stratum. Pooled observations are separate (level row, index, opponent) pairs, matching RF1; repeated seeds across level rows are not clustered together. Scores below use unrounded means. CIs are pointwise and not adjusted for multiplicity. pt5 is the sole primary arm.

| Row | Opponent | Arm−RF | Pairs | RF score | Arm score | Δ [95% CI] |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | LIVE-K4CW-r16-fp | pt5 | 200 | 0.7350 | 0.8450 | +0.1100 [+0.0400, +0.1800] |
| l16 | LIVE-K4CW-r16-fp | pt2 | 200 | 0.7350 | 0.8150 | +0.0800 [+0.0100, +0.1500] |
| l16 | R3a | pt5 | 200 | 0.8300 | 0.9050 | +0.0750 [+0.0100, +0.1400] |
| l16 | R3a | pt2 | 200 | 0.8300 | 0.8500 | +0.0200 [-0.0450, +0.0850] |
| l16 | HPv2 | pt5 | 200 | 0.4500 | 0.5350 | +0.0850 [+0.0000, +0.1700] |
| l16 | HPv2 | pt2 | 200 | 0.4500 | 0.5200 | +0.0700 [-0.0150, +0.1500] |
| l16 | all | pt5 | 600 | 0.6717 | 0.7617 | +0.0900 [+0.0467, +0.1333] |
| l16 | all | pt2 | 600 | 0.6717 | 0.7283 | +0.0567 [+0.0133, +0.1000] |
| acc | LIVE-K4CW-r16-fp | pt5 | 200 | 0.5100 | 0.5600 | +0.0500 [-0.0300, +0.1350] |
| acc | LIVE-K4CW-r16-fp | pt2 | 200 | 0.5100 | 0.5950 | +0.0850 [+0.0000, +0.1700] |
| acc | R3a | pt5 | 200 | 0.6450 | 0.6800 | +0.0350 [-0.0400, +0.1150] |
| acc | R3a | pt2 | 200 | 0.6450 | 0.6800 | +0.0350 [-0.0450, +0.1100] |
| acc | HPv2 | pt5 | 200 | 0.2650 | 0.3075 | +0.0425 [-0.0250, +0.1125] |
| acc | HPv2 | pt2 | 200 | 0.2650 | 0.3300 | +0.0650 [-0.0150, +0.1450] |
| acc | all | pt5 | 600 | 0.4733 | 0.5158 | +0.0425 [-0.0017, +0.0867] |
| acc | all | pt2 | 600 | 0.4733 | 0.5350 | +0.0617 [+0.0167, +0.1083] |
| pooled | LIVE-K4CW-r16-fp | pt5 | 400 | 0.6225 | 0.7025 | +0.0800 [+0.0250, +0.1325] |
| pooled | LIVE-K4CW-r16-fp | pt2 | 400 | 0.6225 | 0.7050 | +0.0825 [+0.0275, +0.1400] |
| pooled | R3a | pt5 | 400 | 0.7375 | 0.7925 | +0.0550 [+0.0025, +0.1050] |
| pooled | R3a | pt2 | 400 | 0.7375 | 0.7650 | +0.0275 [-0.0250, +0.0775] |
| pooled | HPv2 | pt5 | 400 | 0.3575 | 0.4213 | +0.0638 [+0.0075, +0.1175] |
| pooled | HPv2 | pt2 | 400 | 0.3575 | 0.4250 | +0.0675 [+0.0100, +0.1225] |
| pooled | all | pt5 | 1200 | 0.5725 | 0.6388 | +0.0663 [+0.0350, +0.0975] |
| pooled | all | pt2 | 1200 | 0.5725 | 0.6317 | +0.0592 [+0.0283, +0.0908] |

## Standing play-quality metrics

| Row | Opponent | Arm | CPU ms/decision | Idle troop share | Wrong lane share | Wincon spend share | Cross elixir mean / median | Reaction p50 / p90 s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | LIVE-K4CW-r16-fp | RF | 642.6 | 0.5286 | 0.2655 | 0.0661 | 3.1777 / 3.0530 | 1.500 / 5.500 |
| l16 | LIVE-K4CW-r16-fp | pt5 | 826.8 | 0.4440 | 0.1921 | 0.0303 | 4.4715 / 4.2850 | 1.500 / 8.000 |
| l16 | LIVE-K4CW-r16-fp | pt2 | 780.1 | 0.4642 | 0.2233 | 0.0461 | 3.7547 / 3.5890 | 1.500 / 7.000 |
| l16 | R3a | RF | 591.5 | 0.5744 | 0.2689 | 0.0685 | 3.2288 / 3.1070 | 1.500 / 5.750 |
| l16 | R3a | pt5 | 743.5 | 0.5025 | 0.1833 | 0.0289 | 4.4902 / 4.2850 | 2.000 / 8.500 |
| l16 | R3a | pt2 | 700.8 | 0.5291 | 0.2262 | 0.0306 | 3.8892 / 3.7140 | 1.750 / 7.500 |
| l16 | HPv2 | RF | 536.8 | 0.5637 | 0.2111 | 0.0557 | 3.3712 / 3.2500 | 1.750 / 5.750 |
| l16 | HPv2 | pt5 | 657.4 | 0.4989 | 0.1282 | 0.0211 | 4.6407 / 4.4640 | 2.250 / 8.500 |
| l16 | HPv2 | pt2 | 613.1 | 0.5234 | 0.1506 | 0.0339 | 3.9201 / 3.7500 | 1.750 / 7.500 |
| l16 | all | RF | 590.5 | 0.5554 | 0.2495 | 0.0636 | 3.2481 / 3.1070 | 1.500 / 5.750 |
| l16 | all | pt5 | 741.6 | 0.4817 | 0.1687 | 0.0267 | 4.5248 / 4.3300 | 2.000 / 8.500 |
| l16 | all | pt2 | 698.5 | 0.5052 | 0.2013 | 0.0371 | 3.8457 / 3.6780 | 1.750 / 7.250 |
| acc | LIVE-K4CW-r16-fp | RF | 655.6 | 0.5178 | 0.2654 | 0.0597 | 3.2258 / 3.1250 | 1.500 / 5.500 |
| acc | LIVE-K4CW-r16-fp | pt5 | 834.1 | 0.4347 | 0.1962 | 0.0371 | 4.5063 / 4.3030 | 2.000 / 8.000 |
| acc | LIVE-K4CW-r16-fp | pt2 | 787.9 | 0.4638 | 0.2271 | 0.0483 | 3.6867 / 3.5000 | 1.500 / 7.000 |
| acc | R3a | RF | 594.1 | 0.5650 | 0.2796 | 0.0601 | 3.2587 / 3.1070 | 1.500 / 5.500 |
| acc | R3a | pt5 | 736.8 | 0.4852 | 0.1997 | 0.0279 | 4.5464 / 4.3570 | 2.000 / 8.250 |
| acc | R3a | pt2 | 717.0 | 0.5057 | 0.2252 | 0.0399 | 3.8982 / 3.7320 | 1.750 / 7.000 |
| acc | HPv2 | RF | 497.9 | 0.5713 | 0.2172 | 0.0579 | 3.3491 / 3.2500 | 1.750 / 6.000 |
| acc | HPv2 | pt5 | 628.6 | 0.4883 | 0.1202 | 0.0313 | 4.6868 / 4.4640 | 2.250 / 8.250 |
| acc | HPv2 | pt2 | 584.1 | 0.5161 | 0.1616 | 0.0317 | 3.8939 / 3.7140 | 1.750 / 7.000 |
| acc | all | RF | 583.4 | 0.5510 | 0.2556 | 0.0593 | 3.2701 / 3.1600 | 1.500 / 5.750 |
| acc | all | pt5 | 734.1 | 0.4688 | 0.1742 | 0.0321 | 4.5682 / 4.3570 | 2.000 / 8.000 |
| acc | all | pt2 | 697.3 | 0.4949 | 0.2067 | 0.0402 | 3.8175 / 3.6420 | 1.750 / 7.000 |
| pooled | LIVE-K4CW-r16-fp | RF | 649.2 | 0.5231 | 0.2655 | 0.0629 | 3.2021 / 3.0890 | 1.500 / 5.500 |
| pooled | LIVE-K4CW-r16-fp | pt5 | 830.5 | 0.4392 | 0.1942 | 0.0337 | 4.4892 / 4.3030 | 1.500 / 8.000 |
| pooled | LIVE-K4CW-r16-fp | pt2 | 784.1 | 0.4640 | 0.2253 | 0.0472 | 3.7208 / 3.5530 | 1.500 / 7.000 |
| pooled | R3a | RF | 592.8 | 0.5696 | 0.2745 | 0.0642 | 3.2440 / 3.1070 | 1.500 / 5.750 |
| pooled | R3a | pt5 | 740.1 | 0.4936 | 0.1917 | 0.0284 | 4.5187 / 4.3210 | 2.000 / 8.250 |
| pooled | R3a | pt2 | 709.1 | 0.5171 | 0.2257 | 0.0355 | 3.8939 / 3.7140 | 1.750 / 7.000 |
| pooled | HPv2 | RF | 517.3 | 0.5675 | 0.2141 | 0.0568 | 3.3602 / 3.2500 | 1.750 / 5.750 |
| pooled | HPv2 | pt5 | 643.1 | 0.4937 | 0.1242 | 0.0260 | 4.6635 / 4.4640 | 2.250 / 8.500 |
| pooled | HPv2 | pt2 | 598.5 | 0.5197 | 0.1562 | 0.0328 | 3.9070 / 3.7320 | 1.750 / 7.250 |
| pooled | all | RF | 586.9 | 0.5532 | 0.2526 | 0.0614 | 3.2592 / 3.1420 | 1.500 / 5.750 |
| pooled | all | pt5 | 737.8 | 0.4752 | 0.1715 | 0.0295 | 4.5467 / 4.3570 | 2.000 / 8.250 |
| pooled | all | pt2 | 697.9 | 0.5000 | 0.2041 | 0.0387 | 3.8314 / 3.6420 | 1.750 / 7.000 |

CPU is total own-seat decision CPU / own-seat decisions on the allowed hosts, not wall time. Reaction is accepted enemy play → next accepted own play, 20 ticks/s; no subsequent play means omitted. Standing hz_report definitions: idle uses accepted troop plays with no enemy within6tiles of aim on the preceding own frame; wrong lane uses accepted defensive nonspell plays and closest incursion within±3s; wincon spend uses revealed enemy wincon plays preceded within3s by an accepted own play and an elixir observation≤1; a crossing is the transition from no enemy body at y<15 to at least one. These definitions are unchanged from RF1.

| Row | Opponent | Arm | Cross events | Cross ≥8 | Undefended 5s | Incursions/game | Decision reaction p50/p90 s | Median game CPU ms/decision | Giant undefended / pushes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | LIVE-K4CW-r16-fp | RF | 3001 | 0.0030 | 0.1593 | 15.01 | 0.150 / 1.150 | 633.0 | 0.0000 / 8 |
| l16 | LIVE-K4CW-r16-fp | pt5 | 2806 | 0.0581 | 0.2609 | 14.03 | 0.150 / 0.650 | 830.5 | 0.0000 / 10 |
| l16 | LIVE-K4CW-r16-fp | pt2 | 2882 | 0.0180 | 0.2047 | 14.41 | 0.150 / 0.650 | 764.9 | 0.0000 / 7 |
| l16 | R3a | RF | 2644 | 0.0023 | 0.1483 | 13.22 | 0.400 / 0.900 | 577.8 | 0.0476 / 84 |
| l16 | R3a | pt5 | 2548 | 0.0628 | 0.2524 | 12.74 | 0.400 / 0.900 | 738.5 | 0.0482 / 83 |
| l16 | R3a | pt2 | 2513 | 0.0215 | 0.2025 | 12.56 | 0.400 / 0.900 | 695.5 | 0.0488 / 82 |
| l16 | HPv2 | RF | 2129 | 0.0023 | 0.1301 | 10.64 | 0.400 / 1.150 | 540.3 | 0.0538 / 93 |
| l16 | HPv2 | pt5 | 2048 | 0.0664 | 0.2305 | 10.24 | 0.400 / 0.900 | 660.8 | 0.0467 / 107 |
| l16 | HPv2 | pt2 | 2052 | 0.0244 | 0.1842 | 10.26 | 0.400 / 0.900 | 611.5 | 0.0412 / 97 |
| l16 | all | RF | 7774 | 0.0026 | 0.1475 | 12.96 | 0.150 / 1.150 | 577.6 | 0.0486 / 185 |
| l16 | all | pt5 | 7402 | 0.0620 | 0.2495 | 12.34 | 0.150 / 0.900 | 727.1 | 0.0450 / 200 |
| l16 | all | pt2 | 7447 | 0.0209 | 0.1983 | 12.41 | 0.150 / 0.900 | 682.0 | 0.0430 / 186 |
| acc | LIVE-K4CW-r16-fp | RF | 3071 | 0.0029 | 0.1433 | 15.36 | 0.150 / 1.150 | 645.5 | 0.0000 / 11 |
| acc | LIVE-K4CW-r16-fp | pt5 | 2894 | 0.0691 | 0.2543 | 14.47 | 0.150 / 0.650 | 817.1 | 0.1250 / 16 |
| acc | LIVE-K4CW-r16-fp | pt2 | 2859 | 0.0168 | 0.2141 | 14.29 | 0.150 / 0.650 | 764.3 | 0.0000 / 13 |
| acc | R3a | RF | 2742 | 0.0033 | 0.1404 | 13.71 | 0.400 / 1.150 | 572.0 | 0.0319 / 94 |
| acc | R3a | pt5 | 2623 | 0.0671 | 0.2356 | 13.12 | 0.400 / 0.900 | 731.1 | 0.0889 / 90 |
| acc | R3a | pt2 | 2695 | 0.0267 | 0.2030 | 13.47 | 0.400 / 0.900 | 699.0 | 0.0408 / 98 |
| acc | HPv2 | RF | 2118 | 0.0033 | 0.1270 | 10.59 | 0.400 / 1.150 | 498.8 | 0.0190 / 105 |
| acc | HPv2 | pt5 | 1995 | 0.0767 | 0.2175 | 9.97 | 0.400 / 0.900 | 635.9 | 0.0581 / 86 |
| acc | HPv2 | pt2 | 2046 | 0.0191 | 0.1789 | 10.23 | 0.400 / 0.900 | 596.5 | 0.0250 / 80 |
| acc | all | RF | 7931 | 0.0032 | 0.1379 | 13.22 | 0.150 / 1.150 | 568.6 | 0.0238 / 210 |
| acc | all | pt5 | 7512 | 0.0704 | 0.2380 | 12.52 | 0.150 / 0.900 | 721.9 | 0.0781 / 192 |
| acc | all | pt2 | 7600 | 0.0209 | 0.2007 | 12.67 | 0.150 / 0.900 | 682.2 | 0.0314 / 191 |
| pooled | LIVE-K4CW-r16-fp | RF | 6072 | 0.0030 | 0.1512 | 15.18 | 0.150 / 1.150 | 636.6 | 0.0000 / 19 |
| pooled | LIVE-K4CW-r16-fp | pt5 | 5700 | 0.0637 | 0.2575 | 14.25 | 0.150 / 0.650 | 822.6 | 0.0769 / 26 |
| pooled | LIVE-K4CW-r16-fp | pt2 | 5741 | 0.0174 | 0.2094 | 14.35 | 0.150 / 0.650 | 764.3 | 0.0000 / 20 |
| pooled | R3a | RF | 5386 | 0.0028 | 0.1443 | 13.46 | 0.400 / 1.150 | 576.3 | 0.0393 / 178 |
| pooled | R3a | pt5 | 5171 | 0.0650 | 0.2439 | 12.93 | 0.400 / 0.900 | 735.0 | 0.0694 / 173 |
| pooled | R3a | pt2 | 5208 | 0.0242 | 0.2028 | 13.02 | 0.400 / 0.900 | 696.5 | 0.0444 / 180 |
| pooled | HPv2 | RF | 4247 | 0.0028 | 0.1286 | 10.62 | 0.400 / 1.150 | 521.0 | 0.0354 / 198 |
| pooled | HPv2 | pt5 | 4043 | 0.0715 | 0.2241 | 10.11 | 0.400 / 0.900 | 650.3 | 0.0518 / 193 |
| pooled | HPv2 | pt2 | 4098 | 0.0217 | 0.1816 | 10.24 | 0.400 / 0.900 | 601.8 | 0.0339 / 177 |
| pooled | all | RF | 15705 | 0.0029 | 0.1427 | 13.09 | 0.150 / 1.150 | 574.2 | 0.0354 / 395 |
| pooled | all | pt5 | 14914 | 0.0662 | 0.2437 | 12.43 | 0.150 / 0.900 | 723.2 | 0.0612 / 392 |
| pooled | all | pt2 | 15047 | 0.0209 | 0.1995 | 12.54 | 0.150 / 0.900 | 682.0 | 0.0371 / 377 |

## Enemy Hog crossings

| Row | Opponent | Arm | Hog crossings | Elixir mean | Median | Share ≥6 | Cannon in hand and ≥3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | LIVE-K4CW-r16-fp | RF | 433 | 3.1815 | 3.0350 | 0.0323 | 0.3048 |
| l16 | LIVE-K4CW-r16-fp | pt5 | 408 | 4.1762 | 3.9280 | 0.1838 | 0.3235 |
| l16 | LIVE-K4CW-r16-fp | pt2 | 411 | 3.6151 | 3.2850 | 0.0973 | 0.3333 |
| l16 | R3a | RF | 435 | 3.2759 | 3.0710 | 0.0414 | 0.3724 |
| l16 | R3a | pt5 | 413 | 4.0646 | 3.8920 | 0.1622 | 0.3632 |
| l16 | R3a | pt2 | 426 | 3.7102 | 3.4820 | 0.0962 | 0.3615 |
| l16 | HPv2 | RF | 403 | 3.1141 | 3.0890 | 0.0372 | 0.3548 |
| l16 | HPv2 | pt5 | 407 | 4.3267 | 4.1960 | 0.2039 | 0.3808 |
| l16 | HPv2 | pt2 | 382 | 3.6063 | 3.3120 | 0.1021 | 0.3691 |
| l16 | all | RF | 1271 | 3.1925 | 3.0710 | 0.0370 | 0.3438 |
| l16 | all | pt5 | 1228 | 4.1886 | 3.9640 | 0.1832 | 0.3559 |
| l16 | all | pt2 | 1219 | 3.6456 | 3.3920 | 0.0984 | 0.3544 |
| acc | LIVE-K4CW-r16-fp | RF | 413 | 3.2453 | 3.0350 | 0.0460 | 0.3317 |
| acc | LIVE-K4CW-r16-fp | pt5 | 429 | 4.1829 | 3.9280 | 0.1772 | 0.2937 |
| acc | LIVE-K4CW-r16-fp | pt2 | 408 | 3.5563 | 3.2140 | 0.1005 | 0.3039 |
| acc | R3a | RF | 459 | 3.1679 | 2.9640 | 0.0370 | 0.3203 |
| acc | R3a | pt5 | 446 | 4.3573 | 4.3210 | 0.1906 | 0.3722 |
| acc | R3a | pt2 | 454 | 3.7294 | 3.4640 | 0.1145 | 0.3436 |
| acc | HPv2 | RF | 398 | 3.0185 | 2.8660 | 0.0201 | 0.2839 |
| acc | HPv2 | pt5 | 397 | 4.3822 | 4.1780 | 0.2393 | 0.3728 |
| acc | HPv2 | pt2 | 375 | 3.5960 | 3.3030 | 0.1040 | 0.3280 |
| acc | all | RF | 1270 | 3.1463 | 2.9640 | 0.0346 | 0.3126 |
| acc | all | pt5 | 1272 | 4.3063 | 4.0710 | 0.2013 | 0.3459 |
| acc | all | pt2 | 1237 | 3.6319 | 3.3210 | 0.1067 | 0.3258 |
| pooled | LIVE-K4CW-r16-fp | RF | 846 | 3.2126 | 3.0350 | 0.0390 | 0.3180 |
| pooled | LIVE-K4CW-r16-fp | pt5 | 837 | 4.1797 | 3.9280 | 0.1804 | 0.3082 |
| pooled | LIVE-K4CW-r16-fp | pt2 | 819 | 3.5858 | 3.2850 | 0.0989 | 0.3187 |
| pooled | R3a | RF | 894 | 3.2205 | 3.0000 | 0.0391 | 0.3456 |
| pooled | R3a | pt5 | 859 | 4.2166 | 4.0350 | 0.1769 | 0.3679 |
| pooled | R3a | pt2 | 880 | 3.7201 | 3.4640 | 0.1057 | 0.3523 |
| pooled | HPv2 | RF | 801 | 3.0666 | 3.0020 | 0.0287 | 0.3196 |
| pooled | HPv2 | pt5 | 804 | 4.3541 | 4.1780 | 0.2214 | 0.3769 |
| pooled | HPv2 | pt2 | 757 | 3.6012 | 3.3030 | 0.1030 | 0.3487 |
| pooled | all | RF | 2541 | 3.1694 | 3.0000 | 0.0358 | 0.3282 |
| pooled | all | pt5 | 2500 | 4.2485 | 4.0230 | 0.1924 | 0.3508 |
| pooled | all | pt2 | 2456 | 3.6387 | 3.3570 | 0.1026 | 0.3400 |

RF1 tracking is unchanged: greedily match nearest enemy Hog positions across adjacent frames within max(1tile,0.2×elapsedticks), each track counted at first y<15. Elixir and Cannon hand membership use that frame. Packets have no entity IDs; gaps can split tracks. This is observed tracking, not hidden entity-ID truth.

## Fireball / Zap / ElectroSpirit

| Row | Opponent | Arm | Card | Plays/game | Plays | Frames available | Enemy within2.5 share |
| --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | LIVE-K4CW-r16-fp | RF | Fireball | 0.900 | 180 | 161 | 0.4907 |
| l16 | LIVE-K4CW-r16-fp | RF | Zap | 5.435 | 1087 | 1080 | 0.5667 |
| l16 | LIVE-K4CW-r16-fp | RF | ElectroSpirit | 7.725 | 1545 | 1526 | 0.2235 |
| l16 | LIVE-K4CW-r16-fp | pt5 | Fireball | 1.595 | 319 | 309 | 0.4304 |
| l16 | LIVE-K4CW-r16-fp | pt5 | Zap | 3.085 | 617 | 616 | 0.4984 |
| l16 | LIVE-K4CW-r16-fp | pt5 | ElectroSpirit | 3.665 | 733 | 733 | 0.3561 |
| l16 | LIVE-K4CW-r16-fp | pt2 | Fireball | 1.250 | 250 | 230 | 0.5043 |
| l16 | LIVE-K4CW-r16-fp | pt2 | Zap | 3.785 | 757 | 756 | 0.5251 |
| l16 | LIVE-K4CW-r16-fp | pt2 | ElectroSpirit | 5.035 | 1007 | 1005 | 0.2935 |
| l16 | R3a | RF | Fireball | 1.100 | 220 | 196 | 0.4439 |
| l16 | R3a | RF | Zap | 5.025 | 1005 | 1002 | 0.5868 |
| l16 | R3a | RF | ElectroSpirit | 7.475 | 1495 | 1471 | 0.2080 |
| l16 | R3a | pt5 | Fireball | 1.810 | 362 | 355 | 0.5099 |
| l16 | R3a | pt5 | Zap | 2.920 | 584 | 584 | 0.5428 |
| l16 | R3a | pt5 | ElectroSpirit | 3.420 | 684 | 684 | 0.3173 |
| l16 | R3a | pt2 | Fireball | 1.395 | 279 | 271 | 0.5461 |
| l16 | R3a | pt2 | Zap | 3.575 | 715 | 713 | 0.5806 |
| l16 | R3a | pt2 | ElectroSpirit | 5.035 | 1007 | 1006 | 0.2744 |
| l16 | HPv2 | RF | Fireball | 1.155 | 231 | 220 | 0.5409 |
| l16 | HPv2 | RF | Zap | 5.150 | 1030 | 1029 | 0.6608 |
| l16 | HPv2 | RF | ElectroSpirit | 7.640 | 1528 | 1509 | 0.2412 |
| l16 | HPv2 | pt5 | Fireball | 2.270 | 454 | 448 | 0.4799 |
| l16 | HPv2 | pt5 | Zap | 3.150 | 630 | 629 | 0.6184 |
| l16 | HPv2 | pt5 | ElectroSpirit | 4.025 | 805 | 804 | 0.3856 |
| l16 | HPv2 | pt2 | Fireball | 1.560 | 312 | 306 | 0.5098 |
| l16 | HPv2 | pt2 | Zap | 3.850 | 770 | 768 | 0.6302 |
| l16 | HPv2 | pt2 | ElectroSpirit | 5.260 | 1052 | 1050 | 0.3238 |
| l16 | all | RF | Fireball | 1.052 | 631 | 577 | 0.4939 |
| l16 | all | RF | Zap | 5.203 | 3122 | 3111 | 0.6043 |
| l16 | all | RF | ElectroSpirit | 7.613 | 4568 | 4506 | 0.2244 |
| l16 | all | pt5 | Fireball | 1.892 | 1135 | 1112 | 0.4757 |
| l16 | all | pt5 | Zap | 3.052 | 1831 | 1829 | 0.5539 |
| l16 | all | pt5 | ElectroSpirit | 3.703 | 2222 | 2221 | 0.3548 |
| l16 | all | pt2 | Fireball | 1.402 | 841 | 807 | 0.5204 |
| l16 | all | pt2 | Zap | 3.737 | 2242 | 2237 | 0.5789 |
| l16 | all | pt2 | ElectroSpirit | 5.110 | 3066 | 3061 | 0.2976 |
| acc | LIVE-K4CW-r16-fp | RF | Fireball | 1.055 | 211 | 201 | 0.4925 |
| acc | LIVE-K4CW-r16-fp | RF | Zap | 5.695 | 1139 | 1129 | 0.5190 |
| acc | LIVE-K4CW-r16-fp | RF | ElectroSpirit | 8.035 | 1607 | 1585 | 0.2479 |
| acc | LIVE-K4CW-r16-fp | pt5 | Fireball | 1.695 | 339 | 326 | 0.4693 |
| acc | LIVE-K4CW-r16-fp | pt5 | Zap | 3.295 | 659 | 657 | 0.4612 |
| acc | LIVE-K4CW-r16-fp | pt5 | ElectroSpirit | 3.800 | 760 | 757 | 0.3408 |
| acc | LIVE-K4CW-r16-fp | pt2 | Fireball | 1.340 | 268 | 248 | 0.5161 |
| acc | LIVE-K4CW-r16-fp | pt2 | Zap | 3.895 | 779 | 777 | 0.4813 |
| acc | LIVE-K4CW-r16-fp | pt2 | ElectroSpirit | 5.365 | 1073 | 1072 | 0.3041 |
| acc | R3a | RF | Fireball | 1.215 | 243 | 222 | 0.5315 |
| acc | R3a | RF | Zap | 5.575 | 1115 | 1109 | 0.5419 |
| acc | R3a | RF | ElectroSpirit | 8.030 | 1606 | 1588 | 0.2135 |
| acc | R3a | pt5 | Fireball | 2.035 | 407 | 394 | 0.4949 |
| acc | R3a | pt5 | Zap | 3.195 | 639 | 639 | 0.4930 |
| acc | R3a | pt5 | ElectroSpirit | 3.495 | 699 | 699 | 0.3104 |
| acc | R3a | pt2 | Fireball | 1.670 | 334 | 322 | 0.5466 |
| acc | R3a | pt2 | Zap | 3.885 | 777 | 772 | 0.5104 |
| acc | R3a | pt2 | ElectroSpirit | 5.195 | 1039 | 1039 | 0.2502 |
| acc | HPv2 | RF | Fireball | 1.125 | 225 | 215 | 0.5163 |
| acc | HPv2 | RF | Zap | 5.160 | 1032 | 1028 | 0.5905 |
| acc | HPv2 | RF | ElectroSpirit | 7.685 | 1537 | 1515 | 0.2310 |
| acc | HPv2 | pt5 | Fireball | 2.275 | 455 | 439 | 0.4829 |
| acc | HPv2 | pt5 | Zap | 3.305 | 661 | 660 | 0.5758 |
| acc | HPv2 | pt5 | ElectroSpirit | 3.900 | 780 | 780 | 0.3923 |
| acc | HPv2 | pt2 | Fireball | 1.670 | 334 | 324 | 0.5309 |
| acc | HPv2 | pt2 | Zap | 3.945 | 789 | 788 | 0.5787 |
| acc | HPv2 | pt2 | ElectroSpirit | 5.295 | 1059 | 1059 | 0.3239 |
| acc | all | RF | Fireball | 1.132 | 679 | 638 | 0.5141 |
| acc | all | RF | Zap | 5.477 | 3286 | 3266 | 0.5493 |
| acc | all | RF | ElectroSpirit | 7.917 | 4750 | 4688 | 0.2308 |
| acc | all | pt5 | Fireball | 2.002 | 1201 | 1159 | 0.4832 |
| acc | all | pt5 | Zap | 3.265 | 1959 | 1956 | 0.5102 |
| acc | all | pt5 | ElectroSpirit | 3.732 | 2239 | 2236 | 0.3493 |
| acc | all | pt2 | Fireball | 1.560 | 936 | 894 | 0.5324 |
| acc | all | pt2 | Zap | 3.908 | 2345 | 2337 | 0.5237 |
| acc | all | pt2 | ElectroSpirit | 5.285 | 3171 | 3170 | 0.2931 |
| pooled | LIVE-K4CW-r16-fp | RF | Fireball | 0.978 | 391 | 362 | 0.4917 |
| pooled | LIVE-K4CW-r16-fp | RF | Zap | 5.565 | 2226 | 2209 | 0.5423 |
| pooled | LIVE-K4CW-r16-fp | RF | ElectroSpirit | 7.880 | 3152 | 3111 | 0.2359 |
| pooled | LIVE-K4CW-r16-fp | pt5 | Fireball | 1.645 | 658 | 635 | 0.4504 |
| pooled | LIVE-K4CW-r16-fp | pt5 | Zap | 3.190 | 1276 | 1273 | 0.4792 |
| pooled | LIVE-K4CW-r16-fp | pt5 | ElectroSpirit | 3.732 | 1493 | 1490 | 0.3483 |
| pooled | LIVE-K4CW-r16-fp | pt2 | Fireball | 1.295 | 518 | 478 | 0.5105 |
| pooled | LIVE-K4CW-r16-fp | pt2 | Zap | 3.840 | 1536 | 1533 | 0.5029 |
| pooled | LIVE-K4CW-r16-fp | pt2 | ElectroSpirit | 5.200 | 2080 | 2077 | 0.2990 |
| pooled | R3a | RF | Fireball | 1.157 | 463 | 418 | 0.4904 |
| pooled | R3a | RF | Zap | 5.300 | 2120 | 2111 | 0.5632 |
| pooled | R3a | RF | ElectroSpirit | 7.753 | 3101 | 3059 | 0.2109 |
| pooled | R3a | pt5 | Fireball | 1.923 | 769 | 749 | 0.5020 |
| pooled | R3a | pt5 | Zap | 3.058 | 1223 | 1223 | 0.5168 |
| pooled | R3a | pt5 | ElectroSpirit | 3.458 | 1383 | 1383 | 0.3138 |
| pooled | R3a | pt2 | Fireball | 1.532 | 613 | 593 | 0.5464 |
| pooled | R3a | pt2 | Zap | 3.730 | 1492 | 1485 | 0.5441 |
| pooled | R3a | pt2 | ElectroSpirit | 5.115 | 2046 | 2045 | 0.2621 |
| pooled | HPv2 | RF | Fireball | 1.140 | 456 | 435 | 0.5287 |
| pooled | HPv2 | RF | Zap | 5.155 | 2062 | 2057 | 0.6257 |
| pooled | HPv2 | RF | ElectroSpirit | 7.662 | 3065 | 3024 | 0.2361 |
| pooled | HPv2 | pt5 | Fireball | 2.272 | 909 | 887 | 0.4814 |
| pooled | HPv2 | pt5 | Zap | 3.228 | 1291 | 1289 | 0.5966 |
| pooled | HPv2 | pt5 | ElectroSpirit | 3.962 | 1585 | 1584 | 0.3889 |
| pooled | HPv2 | pt2 | Fireball | 1.615 | 646 | 630 | 0.5206 |
| pooled | HPv2 | pt2 | Zap | 3.897 | 1559 | 1556 | 0.6041 |
| pooled | HPv2 | pt2 | ElectroSpirit | 5.277 | 2111 | 2109 | 0.3239 |
| pooled | all | RF | Fireball | 1.092 | 1310 | 1215 | 0.5045 |
| pooled | all | RF | Zap | 5.340 | 6408 | 6377 | 0.5761 |
| pooled | all | RF | ElectroSpirit | 7.765 | 9318 | 9194 | 0.2276 |
| pooled | all | pt5 | Fireball | 1.947 | 2336 | 2271 | 0.4795 |
| pooled | all | pt5 | Zap | 3.158 | 3790 | 3785 | 0.5313 |
| pooled | all | pt5 | ElectroSpirit | 3.717 | 4461 | 4457 | 0.3520 |
| pooled | all | pt2 | Fireball | 1.481 | 1777 | 1701 | 0.5267 |
| pooled | all | pt2 | Zap | 3.822 | 4587 | 4574 | 0.5507 |
| pooled | all | pt2 | ElectroSpirit | 5.197 | 6237 | 6231 | 0.2953 |

Accepted play-log entries count plays. Fireball landing = play tick+ceil(distance from king(9,3) /0.6tiles/tick); Zap = next tick; ElectroSpirit = deployment at+20ticks. Use the first available perception frame at/after landing, counting ≥1enemy unit centre within2.5tiles of aim. No available frame is excluded from the share denominator. Towers and killed units are absent, so this observational proximity measure undercounts successful damage. ElectroSpirit is deployment proximity; actual later jump impact is unavailable. These RF1 definitions are reused without alteration.

## Goblin Barrel answers / Cannon placement

| Row | Opponent | Arm | Barrels | Answered ≤2s | Answer share ≤2s | ≤1.5s sensitivity | Cannon plays | Centre near king share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | LIVE-K4CW-r16-fp | RF | 267 | 38 | 0.1423 | 0.1236 | 964 | 0.0041 |
| l16 | LIVE-K4CW-r16-fp | pt5 | 250 | 17 | 0.0680 | 0.0560 | 808 | 0.0000 |
| l16 | LIVE-K4CW-r16-fp | pt2 | 263 | 28 | 0.1065 | 0.0951 | 798 | 0.0025 |
| l16 | R3a | RF | 178 | 21 | 0.1180 | 0.0730 | 866 | 0.0069 |
| l16 | R3a | pt5 | 182 | 24 | 0.1319 | 0.1044 | 784 | 0.0000 |
| l16 | R3a | pt2 | 171 | 24 | 0.1404 | 0.0994 | 745 | 0.0013 |
| l16 | HPv2 | RF | 191 | 27 | 0.1414 | 0.0942 | 930 | 0.0108 |
| l16 | HPv2 | pt5 | 189 | 25 | 0.1323 | 0.0847 | 814 | 0.0074 |
| l16 | HPv2 | pt2 | 184 | 24 | 0.1304 | 0.1087 | 740 | 0.0068 |
| l16 | all | RF | 636 | 86 | 0.1352 | 0.1006 | 2760 | 0.0072 |
| l16 | all | pt5 | 621 | 66 | 0.1063 | 0.0789 | 2406 | 0.0025 |
| l16 | all | pt2 | 618 | 76 | 0.1230 | 0.1003 | 2283 | 0.0035 |
| acc | LIVE-K4CW-r16-fp | RF | 272 | 36 | 0.1324 | 0.1140 | 1026 | 0.0029 |
| acc | LIVE-K4CW-r16-fp | pt5 | 261 | 17 | 0.0651 | 0.0536 | 873 | 0.0000 |
| acc | LIVE-K4CW-r16-fp | pt2 | 278 | 29 | 0.1043 | 0.0899 | 828 | 0.0024 |
| acc | R3a | RF | 189 | 19 | 0.1005 | 0.0529 | 981 | 0.0061 |
| acc | R3a | pt5 | 195 | 18 | 0.0923 | 0.0718 | 827 | 0.0000 |
| acc | R3a | pt2 | 183 | 30 | 0.1639 | 0.1093 | 823 | 0.0024 |
| acc | HPv2 | RF | 189 | 23 | 0.1217 | 0.0899 | 943 | 0.0223 |
| acc | HPv2 | pt5 | 175 | 19 | 0.1086 | 0.0800 | 821 | 0.0024 |
| acc | HPv2 | pt2 | 191 | 25 | 0.1309 | 0.0995 | 783 | 0.0089 |
| acc | all | RF | 650 | 78 | 0.1200 | 0.0892 | 2950 | 0.0102 |
| acc | all | pt5 | 631 | 54 | 0.0856 | 0.0666 | 2521 | 0.0008 |
| acc | all | pt2 | 652 | 84 | 0.1288 | 0.0982 | 2434 | 0.0045 |
| pooled | LIVE-K4CW-r16-fp | RF | 539 | 74 | 0.1373 | 0.1187 | 1990 | 0.0035 |
| pooled | LIVE-K4CW-r16-fp | pt5 | 511 | 34 | 0.0665 | 0.0548 | 1681 | 0.0000 |
| pooled | LIVE-K4CW-r16-fp | pt2 | 541 | 57 | 0.1054 | 0.0924 | 1626 | 0.0025 |
| pooled | R3a | RF | 367 | 40 | 0.1090 | 0.0627 | 1847 | 0.0065 |
| pooled | R3a | pt5 | 377 | 42 | 0.1114 | 0.0875 | 1611 | 0.0000 |
| pooled | R3a | pt2 | 354 | 54 | 0.1525 | 0.1045 | 1568 | 0.0019 |
| pooled | HPv2 | RF | 380 | 50 | 0.1316 | 0.0921 | 1873 | 0.0166 |
| pooled | HPv2 | pt5 | 364 | 44 | 0.1209 | 0.0824 | 1635 | 0.0049 |
| pooled | HPv2 | pt2 | 375 | 49 | 0.1307 | 0.1040 | 1523 | 0.0079 |
| pooled | all | RF | 1286 | 164 | 0.1275 | 0.0949 | 5710 | 0.0088 |
| pooled | all | pt5 | 1252 | 120 | 0.0958 | 0.0727 | 4927 | 0.0016 |
| pooled | all | pt2 | 1270 | 160 | 0.1260 | 0.0992 | 4717 | 0.0040 |

Enemy Barrel aim rotates into own frame as(18−x,32−y). Answer = own accepted nonbuilding play within3tiles of aim,0..40ticks after enemy play (≤2s); ≤30ticks is the sensitivity. It measures aimed response, not proof the unit arrived. Cannon centre near king = aimed column floor(x)∈{7,8,9,10} and distance≤5tiles from own king(9,3).

## Reproduced PT1 co-primary mechanisms

PT1 functions are byte-identical to the frozen definitions, with its static runtime card metadata. Idle body share includes Troop/Building cards, using no enemy within6tiles at the preceding poll. Dump rate uses config-only_buildings wincon cards, all accepted opponent plays, and an own play in the prior3s whose first following poll (before the enemy play) has elixir≤1. This differs from standing hz_report revealed-wincon spend. PT1’s exact crossing endpoint is enemy **Giant** crossing p50: same-lane detections separated by≤3s, at least5detections, first y<15, upper order-statistic p50. It is reproduced exactly and labelled Giant; the all-enemy standing crossing and separate Hog metric must not be mistaken for this endpoint. Ratios are ratios of sums; bootstrap resamples matched case clusters4000times withRandom(0), preserving within-game denominators. No claim that the Giant-only endpoint covers every enemy wincon.

| Row | Opponent | Arm | Mechanism | RF | Arm | Δ [95% CI] | Bootstrap SE | Usable draws |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l16 | LIVE-K4CW-r16-fp | pt5 | idle_body_play_share | 0.5025 | 0.4335 | -0.0690 [-0.0876, -0.0509] | 0.00935 | 4000 |
| l16 | LIVE-K4CW-r16-fp | pt5 | wincon_dump_rate | 0.0644 | 0.0252 | -0.0392 [-0.0582, -0.0207] | 0.00961 | 4000 |
| l16 | LIVE-K4CW-r16-fp | pt5 | elixir_at_enemy_giant_cross_p50 | 1.6420 | 8.1850 | +6.5430 [+2.2140, +8.7860] | 2.01775 | 3990 |
| l16 | LIVE-K4CW-r16-fp | pt2 | idle_body_play_share | 0.5025 | 0.4544 | -0.0481 [-0.0666, -0.0305] | 0.00917 | 4000 |
| l16 | LIVE-K4CW-r16-fp | pt2 | wincon_dump_rate | 0.0644 | 0.0484 | -0.0160 [-0.0374, +0.0065] | 0.01102 | 4000 |
| l16 | LIVE-K4CW-r16-fp | pt2 | elixir_at_enemy_giant_cross_p50 | 1.6420 | 3.7850 | +2.1430 [+1.3220, +8.3580] | 1.75361 | 3984 |
| l16 | R3a | pt5 | idle_body_play_share | 0.5481 | 0.4790 | -0.0691 [-0.0880, -0.0506] | 0.00952 | 4000 |
| l16 | R3a | pt5 | wincon_dump_rate | 0.0657 | 0.0186 | -0.0471 [-0.0682, -0.0259] | 0.01080 | 4000 |
| l16 | R3a | pt5 | elixir_at_enemy_giant_cross_p50 | 2.8390 | 3.8570 | +1.0180 [+0.1250, +1.7140] | 0.47664 | 4000 |
| l16 | R3a | pt2 | idle_body_play_share | 0.5481 | 0.5104 | -0.0377 [-0.0540, -0.0205] | 0.00846 | 4000 |
| l16 | R3a | pt2 | wincon_dump_rate | 0.0657 | 0.0278 | -0.0379 [-0.0599, -0.0154] | 0.01125 | 4000 |
| l16 | R3a | pt2 | elixir_at_enemy_giant_cross_p50 | 2.8390 | 3.5000 | +0.6610 [+0.1790, +1.0720] | 0.21344 | 4000 |
| l16 | HPv2 | pt5 | idle_body_play_share | 0.5354 | 0.4813 | -0.0542 [-0.0725, -0.0359] | 0.00933 | 4000 |
| l16 | HPv2 | pt5 | wincon_dump_rate | 0.0553 | 0.0166 | -0.0387 [-0.0607, -0.0179] | 0.01073 | 4000 |
| l16 | HPv2 | pt5 | elixir_at_enemy_giant_cross_p50 | 3.0000 | 4.7140 | +1.7140 [+0.9650, +2.9460] | 0.48991 | 4000 |
| l16 | HPv2 | pt2 | idle_body_play_share | 0.5354 | 0.5018 | -0.0336 [-0.0498, -0.0161] | 0.00861 | 4000 |
| l16 | HPv2 | pt2 | wincon_dump_rate | 0.0553 | 0.0361 | -0.0192 [-0.0414, +0.0013] | 0.01088 | 4000 |
| l16 | HPv2 | pt2 | elixir_at_enemy_giant_cross_p50 | 3.0000 | 3.3210 | +0.3210 [-0.1780, +1.2850] | 0.39163 | 4000 |
| l16 | all | pt5 | idle_body_play_share | 0.5284 | 0.4645 | -0.0638 [-0.0746, -0.0529] | 0.00550 | 4000 |
| l16 | all | pt5 | wincon_dump_rate | 0.0620 | 0.0201 | -0.0419 [-0.0537, -0.0302] | 0.00592 | 4000 |
| l16 | all | pt5 | elixir_at_enemy_giant_cross_p50 | 2.8390 | 4.5350 | +1.6960 [+1.2330, +2.1970] | 0.24077 | 4000 |
| l16 | all | pt2 | idle_body_play_share | 0.5284 | 0.4885 | -0.0399 [-0.0503, -0.0294] | 0.00523 | 4000 |
| l16 | all | pt2 | wincon_dump_rate | 0.0620 | 0.0372 | -0.0248 [-0.0375, -0.0126] | 0.00631 | 4000 |
| l16 | all | pt2 | elixir_at_enemy_giant_cross_p50 | 2.8390 | 3.5350 | +0.6960 [+0.2850, +1.0350] | 0.18341 | 4000 |
| acc | LIVE-K4CW-r16-fp | pt5 | idle_body_play_share | 0.4928 | 0.4193 | -0.0735 [-0.0893, -0.0577] | 0.00815 | 4000 |
| acc | LIVE-K4CW-r16-fp | pt5 | wincon_dump_rate | 0.0594 | 0.0260 | -0.0334 [-0.0515, -0.0151] | 0.00924 | 4000 |
| acc | LIVE-K4CW-r16-fp | pt5 | elixir_at_enemy_giant_cross_p50 | 3.2650 | 5.3920 | +2.1270 [-0.6300, +3.7770] | 1.04367 | 4000 |
| acc | LIVE-K4CW-r16-fp | pt2 | idle_body_play_share | 0.4928 | 0.4477 | -0.0452 [-0.0629, -0.0279] | 0.00889 | 4000 |
| acc | LIVE-K4CW-r16-fp | pt2 | wincon_dump_rate | 0.0594 | 0.0428 | -0.0166 [-0.0383, +0.0046] | 0.01103 | 4000 |
| acc | LIVE-K4CW-r16-fp | pt2 | elixir_at_enemy_giant_cross_p50 | 3.2650 | 3.8960 | +0.6310 [-1.5710, +6.6070] | 1.95686 | 3999 |
| acc | R3a | pt5 | idle_body_play_share | 0.5392 | 0.4653 | -0.0739 [-0.0910, -0.0559] | 0.00889 | 4000 |
| acc | R3a | pt5 | wincon_dump_rate | 0.0550 | 0.0199 | -0.0351 [-0.0540, -0.0175] | 0.00925 | 4000 |
| acc | R3a | pt5 | elixir_at_enemy_giant_cross_p50 | 3.0170 | 4.3570 | +1.3400 [+0.0360, +1.7320] | 0.47578 | 4000 |
| acc | R3a | pt2 | idle_body_play_share | 0.5392 | 0.4867 | -0.0526 [-0.0698, -0.0351] | 0.00900 | 4000 |
| acc | R3a | pt2 | wincon_dump_rate | 0.0550 | 0.0313 | -0.0237 [-0.0437, -0.0051] | 0.00991 | 4000 |
| acc | R3a | pt2 | elixir_at_enemy_giant_cross_p50 | 3.0170 | 3.7140 | +0.6970 [+0.1070, +1.1610] | 0.27894 | 4000 |
| acc | HPv2 | pt5 | idle_body_play_share | 0.5433 | 0.4703 | -0.0730 [-0.0894, -0.0555] | 0.00867 | 4000 |
| acc | HPv2 | pt5 | wincon_dump_rate | 0.0619 | 0.0274 | -0.0345 [-0.0544, -0.0149] | 0.00994 | 4000 |
| acc | HPv2 | pt5 | elixir_at_enemy_giant_cross_p50 | 3.0890 | 3.8920 | +0.8030 [+0.1970, +1.3220] | 0.29361 | 4000 |
| acc | HPv2 | pt2 | idle_body_play_share | 0.5433 | 0.4954 | -0.0479 [-0.0648, -0.0309] | 0.00870 | 4000 |
| acc | HPv2 | pt2 | wincon_dump_rate | 0.0619 | 0.0299 | -0.0321 [-0.0530, -0.0113] | 0.01083 | 4000 |
| acc | HPv2 | pt2 | elixir_at_enemy_giant_cross_p50 | 3.0890 | 4.1070 | +1.0180 [+0.3220, +1.5180] | 0.28996 | 4000 |
| acc | all | pt5 | idle_body_play_share | 0.5247 | 0.4511 | -0.0736 [-0.0834, -0.0636] | 0.00503 | 4000 |
| acc | all | pt5 | wincon_dump_rate | 0.0586 | 0.0243 | -0.0343 [-0.0453, -0.0238] | 0.00547 | 4000 |
| acc | all | pt5 | elixir_at_enemy_giant_cross_p50 | 3.0710 | 4.2670 | +1.1960 [+0.4490, +1.5350] | 0.30247 | 4000 |
| acc | all | pt2 | idle_body_play_share | 0.5247 | 0.4763 | -0.0484 [-0.0582, -0.0383] | 0.00508 | 4000 |
| acc | all | pt2 | wincon_dump_rate | 0.0586 | 0.0345 | -0.0240 [-0.0356, -0.0123] | 0.00601 | 4000 |
| acc | all | pt2 | elixir_at_enemy_giant_cross_p50 | 3.0710 | 3.8960 | +0.8250 [+0.3750, +1.1430] | 0.19700 | 4000 |
| pooled | LIVE-K4CW-r16-fp | pt5 | idle_body_play_share | 0.4975 | 0.4262 | -0.0714 [-0.0831, -0.0588] | 0.00614 | 4000 |
| pooled | LIVE-K4CW-r16-fp | pt5 | wincon_dump_rate | 0.0619 | 0.0256 | -0.0363 [-0.0497, -0.0233] | 0.00676 | 4000 |
| pooled | LIVE-K4CW-r16-fp | pt5 | elixir_at_enemy_giant_cross_p50 | 2.8210 | 5.8210 | +3.0000 [+1.3900, +4.9640] | 1.02710 | 4000 |
| pooled | LIVE-K4CW-r16-fp | pt2 | idle_body_play_share | 0.4975 | 0.4510 | -0.0466 [-0.0586, -0.0344] | 0.00619 | 4000 |
| pooled | LIVE-K4CW-r16-fp | pt2 | wincon_dump_rate | 0.0619 | 0.0456 | -0.0163 [-0.0315, -0.0009] | 0.00790 | 4000 |
| pooled | LIVE-K4CW-r16-fp | pt2 | elixir_at_enemy_giant_cross_p50 | 2.8210 | 3.8960 | +1.0750 [-0.2580, +4.3400] | 1.03373 | 4000 |
| pooled | R3a | pt5 | idle_body_play_share | 0.5435 | 0.4720 | -0.0716 [-0.0844, -0.0588] | 0.00651 | 4000 |
| pooled | R3a | pt5 | wincon_dump_rate | 0.0602 | 0.0193 | -0.0409 [-0.0552, -0.0272] | 0.00711 | 4000 |
| pooled | R3a | pt5 | elixir_at_enemy_giant_cross_p50 | 2.9280 | 4.2140 | +1.2860 [+0.3750, +1.6600] | 0.36736 | 4000 |
| pooled | R3a | pt2 | idle_body_play_share | 0.5435 | 0.4982 | -0.0454 [-0.0574, -0.0334] | 0.00620 | 4000 |
| pooled | R3a | pt2 | wincon_dump_rate | 0.0602 | 0.0296 | -0.0306 [-0.0457, -0.0164] | 0.00745 | 4000 |
| pooled | R3a | pt2 | elixir_at_enemy_giant_cross_p50 | 2.9280 | 3.5710 | +0.6430 [+0.3220, +0.9820] | 0.15515 | 4000 |
| pooled | HPv2 | pt5 | idle_body_play_share | 0.5393 | 0.4758 | -0.0635 [-0.0762, -0.0507] | 0.00652 | 4000 |
| pooled | HPv2 | pt5 | wincon_dump_rate | 0.0586 | 0.0219 | -0.0367 [-0.0513, -0.0229] | 0.00722 | 4000 |
| pooled | HPv2 | pt5 | elixir_at_enemy_giant_cross_p50 | 3.0710 | 4.3750 | +1.3040 [+0.8400, +1.8930] | 0.25727 | 4000 |
| pooled | HPv2 | pt2 | idle_body_play_share | 0.5393 | 0.4986 | -0.0408 [-0.0528, -0.0291] | 0.00615 | 4000 |
| pooled | HPv2 | pt2 | wincon_dump_rate | 0.0586 | 0.0330 | -0.0256 [-0.0408, -0.0109] | 0.00763 | 4000 |
| pooled | HPv2 | pt2 | elixir_at_enemy_giant_cross_p50 | 3.0710 | 3.7850 | +0.7140 [+0.1790, +1.2320] | 0.29572 | 4000 |
| pooled | all | pt5 | idle_body_play_share | 0.5265 | 0.4577 | -0.0688 [-0.0758, -0.0614] | 0.00371 | 4000 |
| pooled | all | pt5 | wincon_dump_rate | 0.0603 | 0.0222 | -0.0381 [-0.0460, -0.0302] | 0.00413 | 4000 |
| pooled | all | pt5 | elixir_at_enemy_giant_cross_p50 | 3.0000 | 4.4280 | +1.4280 [+1.0360, +1.6610] | 0.15601 | 4000 |
| pooled | all | pt2 | idle_body_play_share | 0.5265 | 0.4823 | -0.0443 [-0.0513, -0.0371] | 0.00362 | 4000 |
| pooled | all | pt2 | wincon_dump_rate | 0.0603 | 0.0358 | -0.0244 [-0.0330, -0.0157] | 0.00444 | 4000 |
| pooled | all | pt2 | elixir_at_enemy_giant_cross_p50 | 3.0000 | 3.6210 | +0.6210 [+0.3930, +0.9680] | 0.14387 | 4000 |

## Metric gate and paired standard errors

Ratio SEs use the paired-game influence formula used by LP2/KV1: for each arm with ratioR=sumN/sumD, per-case influence=n×(N−R×D)/sumD; SE=sampleSD(arm influence−reference influence)/sqrt(n). Hog median uses its matched-case4000-draw bootstrap SE; midpoint median is retained for even event counts. Delta is arm−RF. An adverse delta exceeding2SE is flagged. Counts/rates with an unspecified desirable direction, CPU and reaction remain descriptive. Missing denominators are NA, not measured zero.

| Arm | Metric (pooled all opponents) | RF | Arm | Δ | Paired SE | 2SE | Gate | Adverse >2SE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pt5 | elixir_at_cross_mean | 3.2592 | 4.5467 | +1.2875 | 0.02428 | 0.04856 | True | False |
| pt5 | elixir_at_cross_ge8 | 0.0029 | 0.0662 | +0.0634 | 0.00262 | 0.00524 | False | False |
| pt5 | incursion_undefended_5s | 0.1427 | 0.2437 | +0.1010 | 0.00467 | 0.00934 | False | True |
| pt5 | incursions_per_game | 13.0875 | 12.4283 | -0.6592 | 0.14073 | 0.28145 | False | True |
| pt5 | wincon_spend_share | 0.0614 | 0.0295 | -0.0320 | 0.00405 | 0.00811 | True | False |
| pt5 | idle_play_share | 0.5532 | 0.4752 | -0.0780 | 0.00394 | 0.00789 | True | False |
| pt5 | wrong_lane_share | 0.2526 | 0.1715 | -0.0811 | 0.00344 | 0.00689 | True | False |
| pt5 | cpu_ms_per_decision_pooled | 586.9303 | 737.7952 | +150.8649 | 3.51804 | 7.03608 | False | True |
| pt5 | hog_elixir_mean | 3.1694 | 4.2485 | +1.0791 | 0.04776 | 0.09551 | True | False |
| pt5 | hog_elixir_ge6 | 0.0358 | 0.1924 | +0.1566 | 0.00879 | 0.01757 | True | False |
| pt5 | hog_cannon_and_ge3 | 0.3282 | 0.3508 | +0.0226 | 0.01338 | 0.02676 | True | False |
| pt5 | barrel_answer_share | 0.1275 | 0.0958 | -0.0317 | 0.01179 | 0.02359 | True | True |
| pt5 | barrel_answer_share_1p5s | 0.0949 | 0.0727 | -0.0222 | 0.01051 | 0.02102 | False | True |
| pt5 | cannon_centre_near_king_share | 0.0088 | 0.0016 | -0.0071 | 0.00136 | 0.00273 | False | True |
| pt5 | Fireball_enemy_in_radius_share | 0.5045 | 0.4795 | -0.0250 | 0.01771 | 0.03543 | True | False |
| pt5 | Fireball_plays_per_game | 1.0917 | 1.9467 | +0.8550 | 0.04611 | 0.09222 | False | False |
| pt5 | Zap_enemy_in_radius_share | 0.5761 | 0.5313 | -0.0448 | 0.00964 | 0.01928 | True | True |
| pt5 | Zap_plays_per_game | 5.3400 | 3.1583 | -2.1817 | 0.06318 | 0.12635 | False | True |
| pt5 | ElectroSpirit_enemy_in_radius_share | 0.2276 | 0.3520 | +0.1244 | 0.00807 | 0.01615 | True | False |
| pt5 | ElectroSpirit_plays_per_game | 7.7650 | 3.7175 | -4.0475 | 0.07194 | 0.14388 | False | True |
| pt5 | idle_body_play_share | 0.5265 | 0.4577 | -0.0688 | 0.00369 | 0.00737 | True | False |
| pt5 | wincon_dump_rate | 0.0603 | 0.0222 | -0.0381 | 0.00407 | 0.00814 | True | False |
| pt5 | giant_undefended | 0.0354 | 0.0612 | +0.0258 | 0.01540 | 0.03080 | False | False |
| pt5 | hog_elixir_median | 3.0000 | 4.0230 | +1.0230 | 0.08334 | 0.16667 | True | False |
| pt2 | elixir_at_cross_mean | 3.2592 | 3.8314 | +0.5722 | 0.01929 | 0.03858 | True | False |
| pt2 | elixir_at_cross_ge8 | 0.0029 | 0.0209 | +0.0181 | 0.00136 | 0.00272 | False | False |
| pt2 | incursion_undefended_5s | 0.1427 | 0.1995 | +0.0568 | 0.00427 | 0.00854 | False | True |
| pt2 | incursions_per_game | 13.0875 | 12.5392 | -0.5483 | 0.14204 | 0.28408 | False | True |
| pt2 | wincon_spend_share | 0.0614 | 0.0387 | -0.0228 | 0.00429 | 0.00858 | True | False |
| pt2 | idle_play_share | 0.5532 | 0.5000 | -0.0532 | 0.00386 | 0.00772 | True | False |
| pt2 | wrong_lane_share | 0.2526 | 0.2041 | -0.0485 | 0.00359 | 0.00717 | True | False |
| pt2 | cpu_ms_per_decision_pooled | 586.9303 | 697.8887 | +110.9584 | 3.62162 | 7.24323 | False | True |
| pt2 | hog_elixir_mean | 3.1694 | 3.6387 | +0.4693 | 0.04159 | 0.08319 | True | False |
| pt2 | hog_elixir_ge6 | 0.0358 | 0.1026 | +0.0668 | 0.00651 | 0.01301 | True | False |
| pt2 | hog_cannon_and_ge3 | 0.3282 | 0.3400 | +0.0118 | 0.01260 | 0.02521 | True | False |
| pt2 | barrel_answer_share | 0.1275 | 0.1260 | -0.0015 | 0.01207 | 0.02415 | True | False |
| pt2 | barrel_answer_share_1p5s | 0.0949 | 0.0992 | +0.0043 | 0.01095 | 0.02191 | False | False |
| pt2 | cannon_centre_near_king_share | 0.0088 | 0.0040 | -0.0047 | 0.00155 | 0.00311 | False | True |
| pt2 | Fireball_enemy_in_radius_share | 0.5045 | 0.5267 | +0.0222 | 0.01897 | 0.03795 | True | False |
| pt2 | Fireball_plays_per_game | 1.0917 | 1.4808 | +0.3892 | 0.04450 | 0.08900 | False | False |
| pt2 | Zap_enemy_in_radius_share | 0.5761 | 0.5507 | -0.0254 | 0.00891 | 0.01782 | True | True |
| pt2 | Zap_plays_per_game | 5.3400 | 3.8225 | -1.5175 | 0.06409 | 0.12818 | False | True |
| pt2 | ElectroSpirit_enemy_in_radius_share | 0.2276 | 0.2953 | +0.0676 | 0.00681 | 0.01361 | True | False |
| pt2 | ElectroSpirit_plays_per_game | 7.7650 | 5.1975 | -2.5675 | 0.07252 | 0.14504 | False | True |
| pt2 | idle_body_play_share | 0.5265 | 0.4823 | -0.0443 | 0.00360 | 0.00721 | True | False |
| pt2 | wincon_dump_rate | 0.0603 | 0.0358 | -0.0244 | 0.00442 | 0.00884 | True | False |
| pt2 | giant_undefended | 0.0354 | 0.0371 | +0.0017 | 0.01316 | 0.02631 | False | False |
| pt2 | hog_elixir_median | 3.0000 | 3.3570 | +0.3570 | 0.06751 | 0.13503 | True | False |

### Stratified metric delta / SE

| Row | Opponent | Arm | Metric | Δ | Paired SE | Adverse >2SE |
| --- | --- | --- | --- | --- | --- | --- |
| l16 | LIVE-K4CW-r16-fp | pt5 | elixir_at_cross_mean | +1.2938 | 0.05245 | False |
| l16 | LIVE-K4CW-r16-fp | pt5 | wincon_spend_share | -0.0358 | 0.00954 | False |
| l16 | LIVE-K4CW-r16-fp | pt5 | idle_play_share | -0.0846 | 0.01016 | False |
| l16 | LIVE-K4CW-r16-fp | pt5 | wrong_lane_share | -0.0734 | 0.00802 | False |
| l16 | LIVE-K4CW-r16-fp | pt5 | hog_elixir_mean | +0.9947 | 0.12098 | False |
| l16 | LIVE-K4CW-r16-fp | pt5 | hog_elixir_ge6 | +0.1515 | 0.02189 | False |
| l16 | LIVE-K4CW-r16-fp | pt5 | hog_cannon_and_ge3 | +0.0187 | 0.03084 | False |
| l16 | LIVE-K4CW-r16-fp | pt5 | barrel_answer_share | -0.0743 | 0.02691 | True |
| l16 | LIVE-K4CW-r16-fp | pt5 | Fireball_enemy_in_radius_share | -0.0603 | 0.04782 | False |
| l16 | LIVE-K4CW-r16-fp | pt5 | Zap_enemy_in_radius_share | -0.0683 | 0.02175 | True |
| l16 | LIVE-K4CW-r16-fp | pt5 | ElectroSpirit_enemy_in_radius_share | +0.1326 | 0.02016 | False |
| l16 | LIVE-K4CW-r16-fp | pt5 | idle_body_play_share | -0.0690 | 0.00936 | False |
| l16 | LIVE-K4CW-r16-fp | pt5 | wincon_dump_rate | -0.0392 | 0.00974 | False |
| l16 | LIVE-K4CW-r16-fp | pt5 | hog_elixir_median | +0.8930 | 0.18020 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | elixir_at_cross_mean | +0.5770 | 0.04177 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | wincon_spend_share | -0.0200 | 0.01126 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | idle_play_share | -0.0644 | 0.01017 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | wrong_lane_share | -0.0422 | 0.00893 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | hog_elixir_mean | +0.4335 | 0.10984 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | hog_elixir_ge6 | +0.0650 | 0.01670 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | hog_cannon_and_ge3 | +0.0285 | 0.03037 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | barrel_answer_share | -0.0359 | 0.02734 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | Fireball_enemy_in_radius_share | +0.0137 | 0.05546 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | Zap_enemy_in_radius_share | -0.0415 | 0.02169 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | ElectroSpirit_enemy_in_radius_share | +0.0701 | 0.01719 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | idle_body_play_share | -0.0481 | 0.00905 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | wincon_dump_rate | -0.0160 | 0.01115 | False |
| l16 | LIVE-K4CW-r16-fp | pt2 | hog_elixir_median | +0.2500 | 0.16955 | False |
| l16 | R3a | pt5 | elixir_at_cross_mean | +1.2614 | 0.06367 | False |
| l16 | R3a | pt5 | wincon_spend_share | -0.0396 | 0.01134 | False |
| l16 | R3a | pt5 | idle_play_share | -0.0720 | 0.01013 | False |
| l16 | R3a | pt5 | wrong_lane_share | -0.0856 | 0.00909 | False |
| l16 | R3a | pt5 | hog_elixir_mean | +0.7887 | 0.10011 | False |
| l16 | R3a | pt5 | hog_elixir_ge6 | +0.1208 | 0.01835 | False |
| l16 | R3a | pt5 | hog_cannon_and_ge3 | -0.0092 | 0.03170 | False |
| l16 | R3a | pt5 | barrel_answer_share | +0.0139 | 0.03053 | False |
| l16 | R3a | pt5 | Fireball_enemy_in_radius_share | +0.0660 | 0.04368 | False |
| l16 | R3a | pt5 | Zap_enemy_in_radius_share | -0.0440 | 0.02552 | False |
| l16 | R3a | pt5 | ElectroSpirit_enemy_in_radius_share | +0.1092 | 0.01862 | False |
| l16 | R3a | pt5 | idle_body_play_share | -0.0691 | 0.00949 | False |
| l16 | R3a | pt5 | wincon_dump_rate | -0.0471 | 0.01069 | False |
| l16 | R3a | pt5 | hog_elixir_median | +0.8210 | 0.14581 | False |
| l16 | R3a | pt2 | elixir_at_cross_mean | +0.6604 | 0.04644 | False |
| l16 | R3a | pt2 | wincon_spend_share | -0.0380 | 0.01056 | False |
| l16 | R3a | pt2 | idle_play_share | -0.0453 | 0.00910 | False |
| l16 | R3a | pt2 | wrong_lane_share | -0.0427 | 0.00909 | False |
| l16 | R3a | pt2 | hog_elixir_mean | +0.4343 | 0.09147 | False |
| l16 | R3a | pt2 | hog_elixir_ge6 | +0.0549 | 0.01453 | False |
| l16 | R3a | pt2 | hog_cannon_and_ge3 | -0.0109 | 0.02825 | False |
| l16 | R3a | pt2 | barrel_answer_share | +0.0224 | 0.03025 | False |
| l16 | R3a | pt2 | Fireball_enemy_in_radius_share | +0.1022 | 0.04631 | False |
| l16 | R3a | pt2 | Zap_enemy_in_radius_share | -0.0062 | 0.02401 | False |
| l16 | R3a | pt2 | ElectroSpirit_enemy_in_radius_share | +0.0663 | 0.01569 | False |
| l16 | R3a | pt2 | idle_body_play_share | -0.0377 | 0.00853 | False |
| l16 | R3a | pt2 | wincon_dump_rate | -0.0379 | 0.01109 | False |
| l16 | R3a | pt2 | hog_elixir_median | +0.4110 | 0.15590 | False |
| l16 | HPv2 | pt5 | elixir_at_cross_mean | +1.2695 | 0.05619 | False |
| l16 | HPv2 | pt5 | wincon_spend_share | -0.0346 | 0.00919 | False |
| l16 | HPv2 | pt5 | idle_play_share | -0.0648 | 0.00936 | False |
| l16 | HPv2 | pt5 | wrong_lane_share | -0.0828 | 0.00830 | False |
| l16 | HPv2 | pt5 | hog_elixir_mean | +1.2126 | 0.11734 | False |
| l16 | HPv2 | pt5 | hog_elixir_ge6 | +0.1667 | 0.02127 | False |
| l16 | HPv2 | pt5 | hog_cannon_and_ge3 | +0.0260 | 0.03496 | False |
| l16 | HPv2 | pt5 | barrel_answer_share | -0.0091 | 0.02619 | False |
| l16 | HPv2 | pt5 | Fireball_enemy_in_radius_share | -0.0610 | 0.04120 | False |
| l16 | HPv2 | pt5 | Zap_enemy_in_radius_share | -0.0424 | 0.02189 | False |
| l16 | HPv2 | pt5 | ElectroSpirit_enemy_in_radius_share | +0.1444 | 0.01964 | False |
| l16 | HPv2 | pt5 | idle_body_play_share | -0.0542 | 0.00925 | False |
| l16 | HPv2 | pt5 | wincon_dump_rate | -0.0387 | 0.01074 | False |
| l16 | HPv2 | pt5 | hog_elixir_median | +1.1070 | 0.20932 | False |
| l16 | HPv2 | pt2 | elixir_at_cross_mean | +0.5489 | 0.05881 | False |
| l16 | HPv2 | pt2 | wincon_spend_share | -0.0218 | 0.00879 | False |
| l16 | HPv2 | pt2 | idle_play_share | -0.0403 | 0.00899 | False |
| l16 | HPv2 | pt2 | wrong_lane_share | -0.0604 | 0.00903 | False |
| l16 | HPv2 | pt2 | hog_elixir_mean | +0.4922 | 0.12009 | False |
| l16 | HPv2 | pt2 | hog_elixir_ge6 | +0.0649 | 0.01823 | False |
| l16 | HPv2 | pt2 | hog_cannon_and_ge3 | +0.0143 | 0.03718 | False |
| l16 | HPv2 | pt2 | barrel_answer_share | -0.0109 | 0.03577 | False |
| l16 | HPv2 | pt2 | Fireball_enemy_in_radius_share | -0.0311 | 0.04382 | False |
| l16 | HPv2 | pt2 | Zap_enemy_in_radius_share | -0.0306 | 0.02118 | False |
| l16 | HPv2 | pt2 | ElectroSpirit_enemy_in_radius_share | +0.0826 | 0.01567 | False |
| l16 | HPv2 | pt2 | idle_body_play_share | -0.0336 | 0.00872 | False |
| l16 | HPv2 | pt2 | wincon_dump_rate | -0.0192 | 0.01089 | False |
| l16 | HPv2 | pt2 | hog_elixir_median | +0.2230 | 0.17768 | False |
| l16 | all | pt5 | elixir_at_cross_mean | +1.2767 | 0.03340 | False |
| l16 | all | pt5 | wincon_spend_share | -0.0368 | 0.00578 | False |
| l16 | all | pt5 | idle_play_share | -0.0737 | 0.00573 | False |
| l16 | all | pt5 | wrong_lane_share | -0.0808 | 0.00490 | False |
| l16 | all | pt5 | hog_elixir_mean | +0.9961 | 0.06597 | False |
| l16 | all | pt5 | hog_elixir_ge6 | +0.1462 | 0.01193 | False |
| l16 | all | pt5 | hog_cannon_and_ge3 | +0.0120 | 0.01877 | False |
| l16 | all | pt5 | barrel_answer_share | -0.0289 | 0.01653 | False |
| l16 | all | pt5 | Fireball_enemy_in_radius_share | -0.0182 | 0.02564 | False |
| l16 | all | pt5 | Zap_enemy_in_radius_share | -0.0505 | 0.01334 | True |
| l16 | all | pt5 | ElectroSpirit_enemy_in_radius_share | +0.1304 | 0.01127 | False |
| l16 | all | pt5 | idle_body_play_share | -0.0638 | 0.00542 | False |
| l16 | all | pt5 | wincon_dump_rate | -0.0419 | 0.00600 | False |
| l16 | all | pt5 | hog_elixir_median | +0.8930 | 0.11439 | False |
| l16 | all | pt2 | elixir_at_cross_mean | +0.5976 | 0.02786 | False |
| l16 | all | pt2 | wincon_spend_share | -0.0265 | 0.00596 | False |
| l16 | all | pt2 | idle_play_share | -0.0501 | 0.00548 | False |
| l16 | all | pt2 | wrong_lane_share | -0.0482 | 0.00522 | False |
| l16 | all | pt2 | hog_elixir_mean | +0.4531 | 0.06148 | False |
| l16 | all | pt2 | hog_elixir_ge6 | +0.0615 | 0.00949 | False |
| l16 | all | pt2 | hog_cannon_and_ge3 | +0.0106 | 0.01847 | False |
| l16 | all | pt2 | barrel_answer_share | -0.0122 | 0.01797 | False |
| l16 | all | pt2 | Fireball_enemy_in_radius_share | +0.0265 | 0.02793 | False |
| l16 | all | pt2 | Zap_enemy_in_radius_share | -0.0254 | 0.01284 | False |
| l16 | all | pt2 | ElectroSpirit_enemy_in_radius_share | +0.0732 | 0.00934 | False |
| l16 | all | pt2 | idle_body_play_share | -0.0399 | 0.00507 | False |
| l16 | all | pt2 | wincon_dump_rate | -0.0248 | 0.00638 | False |
| l16 | all | pt2 | hog_elixir_median | +0.3210 | 0.09767 | False |
| acc | LIVE-K4CW-r16-fp | pt5 | elixir_at_cross_mean | +1.2805 | 0.05754 | False |
| acc | LIVE-K4CW-r16-fp | pt5 | wincon_spend_share | -0.0226 | 0.00934 | False |
| acc | LIVE-K4CW-r16-fp | pt5 | idle_play_share | -0.0831 | 0.00860 | False |
| acc | LIVE-K4CW-r16-fp | pt5 | wrong_lane_share | -0.0692 | 0.00813 | False |
| acc | LIVE-K4CW-r16-fp | pt5 | hog_elixir_mean | +0.9377 | 0.12899 | False |
| acc | LIVE-K4CW-r16-fp | pt5 | hog_elixir_ge6 | +0.1312 | 0.02124 | False |
| acc | LIVE-K4CW-r16-fp | pt5 | hog_cannon_and_ge3 | -0.0380 | 0.03398 | False |
| acc | LIVE-K4CW-r16-fp | pt5 | barrel_answer_share | -0.0672 | 0.02562 | True |
| acc | LIVE-K4CW-r16-fp | pt5 | Fireball_enemy_in_radius_share | -0.0232 | 0.04384 | False |
| acc | LIVE-K4CW-r16-fp | pt5 | Zap_enemy_in_radius_share | -0.0579 | 0.02312 | True |
| acc | LIVE-K4CW-r16-fp | pt5 | ElectroSpirit_enemy_in_radius_share | +0.0929 | 0.02112 | False |
| acc | LIVE-K4CW-r16-fp | pt5 | idle_body_play_share | -0.0735 | 0.00811 | False |
| acc | LIVE-K4CW-r16-fp | pt5 | wincon_dump_rate | -0.0334 | 0.00942 | False |
| acc | LIVE-K4CW-r16-fp | pt5 | hog_elixir_median | +0.8930 | 0.17470 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | elixir_at_cross_mean | +0.4608 | 0.04104 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | wincon_spend_share | -0.0114 | 0.01112 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | idle_play_share | -0.0539 | 0.00912 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | wrong_lane_share | -0.0383 | 0.00866 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | hog_elixir_mean | +0.3110 | 0.09975 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | hog_elixir_ge6 | +0.0545 | 0.01721 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | hog_cannon_and_ge3 | -0.0278 | 0.02949 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | barrel_answer_share | -0.0280 | 0.02517 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | Fireball_enemy_in_radius_share | +0.0236 | 0.04436 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | Zap_enemy_in_radius_share | -0.0377 | 0.02157 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | ElectroSpirit_enemy_in_radius_share | +0.0562 | 0.01803 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | idle_body_play_share | -0.0452 | 0.00877 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | wincon_dump_rate | -0.0166 | 0.01112 | False |
| acc | LIVE-K4CW-r16-fp | pt2 | hog_elixir_median | +0.1790 | 0.12232 | False |
| acc | R3a | pt5 | elixir_at_cross_mean | +1.2877 | 0.05910 | False |
| acc | R3a | pt5 | wincon_spend_share | -0.0322 | 0.01028 | False |
| acc | R3a | pt5 | idle_play_share | -0.0797 | 0.00974 | False |
| acc | R3a | pt5 | wrong_lane_share | -0.0799 | 0.00848 | False |
| acc | R3a | pt5 | hog_elixir_mean | +1.1894 | 0.09847 | False |
| acc | R3a | pt5 | hog_elixir_ge6 | +0.1535 | 0.01691 | False |
| acc | R3a | pt5 | hog_cannon_and_ge3 | +0.0519 | 0.02771 | False |
| acc | R3a | pt5 | barrel_answer_share | -0.0082 | 0.03159 | False |
| acc | R3a | pt5 | Fireball_enemy_in_radius_share | -0.0366 | 0.04279 | False |
| acc | R3a | pt5 | Zap_enemy_in_radius_share | -0.0490 | 0.02405 | True |
| acc | R3a | pt5 | ElectroSpirit_enemy_in_radius_share | +0.0970 | 0.01963 | False |
| acc | R3a | pt5 | idle_body_play_share | -0.0739 | 0.00897 | False |
| acc | R3a | pt5 | wincon_dump_rate | -0.0351 | 0.00937 | False |
| acc | R3a | pt5 | hog_elixir_median | +1.3570 | 0.15361 | False |
| acc | R3a | pt2 | elixir_at_cross_mean | +0.6395 | 0.04586 | False |
| acc | R3a | pt2 | wincon_spend_share | -0.0202 | 0.01084 | False |
| acc | R3a | pt2 | idle_play_share | -0.0593 | 0.00951 | False |
| acc | R3a | pt2 | wrong_lane_share | -0.0544 | 0.00827 | False |
| acc | R3a | pt2 | hog_elixir_mean | +0.5615 | 0.09395 | False |
| acc | R3a | pt2 | hog_elixir_ge6 | +0.0775 | 0.01355 | False |
| acc | R3a | pt2 | hog_cannon_and_ge3 | +0.0234 | 0.02668 | False |
| acc | R3a | pt2 | barrel_answer_share | +0.0634 | 0.03273 | False |
| acc | R3a | pt2 | Fireball_enemy_in_radius_share | +0.0151 | 0.04563 | False |
| acc | R3a | pt2 | Zap_enemy_in_radius_share | -0.0316 | 0.02012 | False |
| acc | R3a | pt2 | ElectroSpirit_enemy_in_radius_share | +0.0368 | 0.01570 | False |
| acc | R3a | pt2 | idle_body_play_share | -0.0526 | 0.00903 | False |
| acc | R3a | pt2 | wincon_dump_rate | -0.0237 | 0.01002 | False |
| acc | R3a | pt2 | hog_elixir_median | +0.5000 | 0.10999 | False |
| acc | HPv2 | pt5 | elixir_at_cross_mean | +1.3377 | 0.06764 | False |
| acc | HPv2 | pt5 | wincon_spend_share | -0.0265 | 0.00987 | False |
| acc | HPv2 | pt5 | idle_play_share | -0.0830 | 0.00977 | False |
| acc | HPv2 | pt5 | wrong_lane_share | -0.0970 | 0.00823 | False |
| acc | HPv2 | pt5 | hog_elixir_mean | +1.3636 | 0.12394 | False |
| acc | HPv2 | pt5 | hog_elixir_ge6 | +0.2192 | 0.02693 | False |
| acc | HPv2 | pt5 | hog_cannon_and_ge3 | +0.0889 | 0.03666 | False |
| acc | HPv2 | pt5 | barrel_answer_share | -0.0131 | 0.03030 | False |
| acc | HPv2 | pt5 | Fireball_enemy_in_radius_share | -0.0334 | 0.04137 | False |
| acc | HPv2 | pt5 | Zap_enemy_in_radius_share | -0.0147 | 0.02546 | False |
| acc | HPv2 | pt5 | ElectroSpirit_enemy_in_radius_share | +0.1613 | 0.01898 | False |
| acc | HPv2 | pt5 | idle_body_play_share | -0.0730 | 0.00876 | False |
| acc | HPv2 | pt5 | wincon_dump_rate | -0.0345 | 0.00980 | False |
| acc | HPv2 | pt5 | hog_elixir_median | +1.3120 | 0.20901 | False |
| acc | HPv2 | pt2 | elixir_at_cross_mean | +0.5448 | 0.05141 | False |
| acc | HPv2 | pt2 | wincon_spend_share | -0.0262 | 0.00987 | False |
| acc | HPv2 | pt2 | idle_play_share | -0.0552 | 0.00962 | False |
| acc | HPv2 | pt2 | wrong_lane_share | -0.0555 | 0.00837 | False |
| acc | HPv2 | pt2 | hog_elixir_mean | +0.5774 | 0.09512 | False |
| acc | HPv2 | pt2 | hog_elixir_ge6 | +0.0839 | 0.01546 | False |
| acc | HPv2 | pt2 | hog_cannon_and_ge3 | +0.0441 | 0.03366 | False |
| acc | HPv2 | pt2 | barrel_answer_share | +0.0092 | 0.02383 | False |
| acc | HPv2 | pt2 | Fireball_enemy_in_radius_share | +0.0146 | 0.04451 | False |
| acc | HPv2 | pt2 | Zap_enemy_in_radius_share | -0.0118 | 0.02268 | False |
| acc | HPv2 | pt2 | ElectroSpirit_enemy_in_radius_share | +0.0929 | 0.01730 | False |
| acc | HPv2 | pt2 | idle_body_play_share | -0.0479 | 0.00867 | False |
| acc | HPv2 | pt2 | wincon_dump_rate | -0.0321 | 0.01080 | False |
| acc | HPv2 | pt2 | hog_elixir_median | +0.4370 | 0.15443 | False |
| acc | all | pt5 | elixir_at_cross_mean | +1.2981 | 0.03522 | False |
| acc | all | pt5 | wincon_spend_share | -0.0272 | 0.00569 | False |
| acc | all | pt5 | idle_play_share | -0.0822 | 0.00543 | False |
| acc | all | pt5 | wrong_lane_share | -0.0813 | 0.00484 | False |
| acc | all | pt5 | hog_elixir_mean | +1.1600 | 0.06847 | False |
| acc | all | pt5 | hog_elixir_ge6 | +0.1666 | 0.01281 | False |
| acc | all | pt5 | hog_cannon_and_ge3 | +0.0333 | 0.01907 | False |
| acc | all | pt5 | barrel_answer_share | -0.0344 | 0.01683 | True |
| acc | all | pt5 | Fireball_enemy_in_radius_share | -0.0309 | 0.02457 | False |
| acc | all | pt5 | Zap_enemy_in_radius_share | -0.0391 | 0.01389 | True |
| acc | all | pt5 | ElectroSpirit_enemy_in_radius_share | +0.1185 | 0.01156 | False |
| acc | all | pt5 | idle_body_play_share | -0.0736 | 0.00500 | False |
| acc | all | pt5 | wincon_dump_rate | -0.0343 | 0.00550 | False |
| acc | all | pt5 | hog_elixir_median | +1.1070 | 0.11316 | False |
| acc | all | pt2 | elixir_at_cross_mean | +0.5474 | 0.02668 | False |
| acc | all | pt2 | wincon_spend_share | -0.0191 | 0.00617 | False |
| acc | all | pt2 | idle_play_share | -0.0561 | 0.00543 | False |
| acc | all | pt2 | wrong_lane_share | -0.0488 | 0.00492 | False |
| acc | all | pt2 | hog_elixir_mean | +0.4856 | 0.05615 | False |
| acc | all | pt2 | hog_elixir_ge6 | +0.0721 | 0.00891 | False |
| acc | all | pt2 | hog_cannon_and_ge3 | +0.0132 | 0.01722 | False |
| acc | all | pt2 | barrel_answer_share | +0.0088 | 0.01616 | False |
| acc | all | pt2 | Fireball_enemy_in_radius_share | +0.0183 | 0.02589 | False |
| acc | all | pt2 | Zap_enemy_in_radius_share | -0.0255 | 0.01235 | True |
| acc | all | pt2 | ElectroSpirit_enemy_in_radius_share | +0.0623 | 0.00989 | False |
| acc | all | pt2 | idle_body_play_share | -0.0484 | 0.00511 | False |
| acc | all | pt2 | wincon_dump_rate | -0.0240 | 0.00613 | False |
| acc | all | pt2 | hog_elixir_median | +0.3570 | 0.07871 | False |
| pooled | LIVE-K4CW-r16-fp | pt5 | elixir_at_cross_mean | +1.2871 | 0.03898 | False |
| pooled | LIVE-K4CW-r16-fp | pt5 | wincon_spend_share | -0.0292 | 0.00667 | False |
| pooled | LIVE-K4CW-r16-fp | pt5 | idle_play_share | -0.0839 | 0.00662 | False |
| pooled | LIVE-K4CW-r16-fp | pt5 | wrong_lane_share | -0.0712 | 0.00571 | False |
| pooled | LIVE-K4CW-r16-fp | pt5 | hog_elixir_mean | +0.9670 | 0.08833 | False |
| pooled | LIVE-K4CW-r16-fp | pt5 | hog_elixir_ge6 | +0.1414 | 0.01521 | False |
| pooled | LIVE-K4CW-r16-fp | pt5 | hog_cannon_and_ge3 | -0.0097 | 0.02306 | False |
| pooled | LIVE-K4CW-r16-fp | pt5 | barrel_answer_share | -0.0708 | 0.01853 | True |
| pooled | LIVE-K4CW-r16-fp | pt5 | Fireball_enemy_in_radius_share | -0.0413 | 0.03224 | False |
| pooled | LIVE-K4CW-r16-fp | pt5 | Zap_enemy_in_radius_share | -0.0631 | 0.01588 | True |
| pooled | LIVE-K4CW-r16-fp | pt5 | ElectroSpirit_enemy_in_radius_share | +0.1124 | 0.01465 | False |
| pooled | LIVE-K4CW-r16-fp | pt5 | idle_body_play_share | -0.0714 | 0.00616 | False |
| pooled | LIVE-K4CW-r16-fp | pt5 | wincon_dump_rate | -0.0363 | 0.00676 | False |
| pooled | LIVE-K4CW-r16-fp | pt5 | hog_elixir_median | +0.8930 | 0.12742 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | elixir_at_cross_mean | +0.5188 | 0.02938 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | wincon_spend_share | -0.0157 | 0.00791 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | idle_play_share | -0.0591 | 0.00681 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | wrong_lane_share | -0.0402 | 0.00621 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | hog_elixir_mean | +0.3731 | 0.07428 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | hog_elixir_ge6 | +0.0599 | 0.01197 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | hog_cannon_and_ge3 | +0.0007 | 0.02126 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | barrel_answer_share | -0.0319 | 0.01851 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | Fireball_enemy_in_radius_share | +0.0187 | 0.03498 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | Zap_enemy_in_radius_share | -0.0394 | 0.01532 | True |
| pooled | LIVE-K4CW-r16-fp | pt2 | ElectroSpirit_enemy_in_radius_share | +0.0631 | 0.01248 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | idle_body_play_share | -0.0466 | 0.00629 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | wincon_dump_rate | -0.0163 | 0.00786 | False |
| pooled | LIVE-K4CW-r16-fp | pt2 | hog_elixir_median | +0.2500 | 0.10208 | False |
| pooled | R3a | pt5 | elixir_at_cross_mean | +1.2747 | 0.04332 | False |
| pooled | R3a | pt5 | wincon_spend_share | -0.0358 | 0.00762 | False |
| pooled | R3a | pt5 | idle_play_share | -0.0760 | 0.00701 | False |
| pooled | R3a | pt5 | wrong_lane_share | -0.0828 | 0.00622 | False |
| pooled | R3a | pt5 | hog_elixir_mean | +0.9961 | 0.07174 | False |
| pooled | R3a | pt5 | hog_elixir_ge6 | +0.1378 | 0.01252 | False |
| pooled | R3a | pt5 | hog_cannon_and_ge3 | +0.0222 | 0.02103 | False |
| pooled | R3a | pt5 | barrel_answer_share | +0.0024 | 0.02207 | False |
| pooled | R3a | pt5 | Fireball_enemy_in_radius_share | +0.0116 | 0.03073 | False |
| pooled | R3a | pt5 | Zap_enemy_in_radius_share | -0.0465 | 0.01748 | True |
| pooled | R3a | pt5 | ElectroSpirit_enemy_in_radius_share | +0.1030 | 0.01353 | False |
| pooled | R3a | pt5 | idle_body_play_share | -0.0716 | 0.00651 | False |
| pooled | R3a | pt5 | wincon_dump_rate | -0.0409 | 0.00708 | False |
| pooled | R3a | pt5 | hog_elixir_median | +1.0350 | 0.13087 | False |
| pooled | R3a | pt2 | elixir_at_cross_mean | +0.6499 | 0.03263 | False |
| pooled | R3a | pt2 | wincon_spend_share | -0.0287 | 0.00759 | False |
| pooled | R3a | pt2 | idle_play_share | -0.0525 | 0.00660 | False |
| pooled | R3a | pt2 | wrong_lane_share | -0.0488 | 0.00614 | False |
| pooled | R3a | pt2 | hog_elixir_mean | +0.4997 | 0.06558 | False |
| pooled | R3a | pt2 | hog_elixir_ge6 | +0.0665 | 0.00994 | False |
| pooled | R3a | pt2 | hog_cannon_and_ge3 | +0.0066 | 0.01938 | False |
| pooled | R3a | pt2 | barrel_answer_share | +0.0436 | 0.02248 | False |
| pooled | R3a | pt2 | Fireball_enemy_in_radius_share | +0.0559 | 0.03268 | False |
| pooled | R3a | pt2 | Zap_enemy_in_radius_share | -0.0191 | 0.01556 | False |
| pooled | R3a | pt2 | ElectroSpirit_enemy_in_radius_share | +0.0512 | 0.01110 | False |
| pooled | R3a | pt2 | idle_body_play_share | -0.0454 | 0.00624 | False |
| pooled | R3a | pt2 | wincon_dump_rate | -0.0306 | 0.00746 | False |
| pooled | R3a | pt2 | hog_elixir_median | +0.4640 | 0.07626 | False |
| pooled | HPv2 | pt5 | elixir_at_cross_mean | +1.3033 | 0.04389 | False |
| pooled | HPv2 | pt5 | wincon_spend_share | -0.0307 | 0.00672 | False |
| pooled | HPv2 | pt5 | idle_play_share | -0.0738 | 0.00679 | False |
| pooled | HPv2 | pt5 | wrong_lane_share | -0.0899 | 0.00585 | False |
| pooled | HPv2 | pt5 | hog_elixir_mean | +1.2875 | 0.08575 | False |
| pooled | HPv2 | pt5 | hog_elixir_ge6 | +0.1927 | 0.01733 | False |
| pooled | HPv2 | pt5 | hog_cannon_and_ge3 | +0.0573 | 0.02541 | False |
| pooled | HPv2 | pt5 | barrel_answer_share | -0.0107 | 0.01986 | False |
| pooled | HPv2 | pt5 | Fireball_enemy_in_radius_share | -0.0473 | 0.02925 | False |
| pooled | HPv2 | pt5 | Zap_enemy_in_radius_share | -0.0291 | 0.01682 | False |
| pooled | HPv2 | pt5 | ElectroSpirit_enemy_in_radius_share | +0.1528 | 0.01366 | False |
| pooled | HPv2 | pt5 | idle_body_play_share | -0.0635 | 0.00640 | False |
| pooled | HPv2 | pt5 | wincon_dump_rate | -0.0367 | 0.00728 | False |
| pooled | HPv2 | pt5 | hog_elixir_median | +1.1760 | 0.16360 | False |
| pooled | HPv2 | pt2 | elixir_at_cross_mean | +0.5468 | 0.03902 | False |
| pooled | HPv2 | pt2 | wincon_spend_share | -0.0240 | 0.00659 | False |
| pooled | HPv2 | pt2 | idle_play_share | -0.0478 | 0.00660 | False |
| pooled | HPv2 | pt2 | wrong_lane_share | -0.0580 | 0.00616 | False |
| pooled | HPv2 | pt2 | hog_elixir_mean | +0.5346 | 0.07686 | False |
| pooled | HPv2 | pt2 | hog_elixir_ge6 | +0.0743 | 0.01199 | False |
| pooled | HPv2 | pt2 | hog_cannon_and_ge3 | +0.0291 | 0.02503 | False |
| pooled | HPv2 | pt2 | barrel_answer_share | -0.0009 | 0.02146 | False |
| pooled | HPv2 | pt2 | Fireball_enemy_in_radius_share | -0.0081 | 0.03130 | False |
| pooled | HPv2 | pt2 | Zap_enemy_in_radius_share | -0.0216 | 0.01552 | False |
| pooled | HPv2 | pt2 | ElectroSpirit_enemy_in_radius_share | +0.0877 | 0.01167 | False |
| pooled | HPv2 | pt2 | idle_body_play_share | -0.0408 | 0.00616 | False |
| pooled | HPv2 | pt2 | wincon_dump_rate | -0.0256 | 0.00767 | False |
| pooled | HPv2 | pt2 | hog_elixir_median | +0.3010 | 0.12988 | False |
| pooled | all | pt5 | elixir_at_cross_mean | +1.2875 | 0.02428 | False |
| pooled | all | pt5 | wincon_spend_share | -0.0320 | 0.00405 | False |
| pooled | all | pt5 | idle_play_share | -0.0780 | 0.00394 | False |
| pooled | all | pt5 | wrong_lane_share | -0.0811 | 0.00344 | False |
| pooled | all | pt5 | hog_elixir_mean | +1.0791 | 0.04776 | False |
| pooled | all | pt5 | hog_elixir_ge6 | +0.1566 | 0.00879 | False |
| pooled | all | pt5 | hog_cannon_and_ge3 | +0.0226 | 0.01338 | False |
| pooled | all | pt5 | barrel_answer_share | -0.0317 | 0.01179 | True |
| pooled | all | pt5 | Fireball_enemy_in_radius_share | -0.0250 | 0.01771 | False |
| pooled | all | pt5 | Zap_enemy_in_radius_share | -0.0448 | 0.00964 | True |
| pooled | all | pt5 | ElectroSpirit_enemy_in_radius_share | +0.1244 | 0.00807 | False |
| pooled | all | pt5 | idle_body_play_share | -0.0688 | 0.00369 | False |
| pooled | all | pt5 | wincon_dump_rate | -0.0381 | 0.00407 | False |
| pooled | all | pt5 | hog_elixir_median | +1.0230 | 0.08334 | False |
| pooled | all | pt2 | elixir_at_cross_mean | +0.5722 | 0.01929 | False |
| pooled | all | pt2 | wincon_spend_share | -0.0228 | 0.00429 | False |
| pooled | all | pt2 | idle_play_share | -0.0532 | 0.00386 | False |
| pooled | all | pt2 | wrong_lane_share | -0.0485 | 0.00359 | False |
| pooled | all | pt2 | hog_elixir_mean | +0.4693 | 0.04159 | False |
| pooled | all | pt2 | hog_elixir_ge6 | +0.0668 | 0.00651 | False |
| pooled | all | pt2 | hog_cannon_and_ge3 | +0.0118 | 0.01260 | False |
| pooled | all | pt2 | barrel_answer_share | -0.0015 | 0.01207 | False |
| pooled | all | pt2 | Fireball_enemy_in_radius_share | +0.0222 | 0.01897 | False |
| pooled | all | pt2 | Zap_enemy_in_radius_share | -0.0254 | 0.00891 | True |
| pooled | all | pt2 | ElectroSpirit_enemy_in_radius_share | +0.0676 | 0.00681 | False |
| pooled | all | pt2 | idle_body_play_share | -0.0443 | 0.00360 | False |
| pooled | all | pt2 | wincon_dump_rate | -0.0244 | 0.00442 | False |
| pooled | all | pt2 | hog_elixir_median | +0.3570 | 0.06751 | False |

## Artifacts / provenance

Validation receipt `validation.json`: original RF1 bootstrap parity PASS; opponent and PT1 bank nonoverlap PASS; all 36 stratum/arm Hog medians and CPU ratio totals match per-case features; all 20 original shards rc0 with 180 rows each. CPU cross-check allows relative tolerance 1e-12 for floating-point sum order (maximum observed absolute difference 1.2505552149377763e-12 ms/decision).

Analysis artifacts: `/mpac/sdicks02/jobs/clasher/bot-pq/watch-sol/ptr1`. Machine-readable results and all per-stratum denominators: `readout-data.json`; per-arm verdicts: `gate.json`; row paths and bank/finished receipts in the readout audit; unchanged source text and SHA256 receipts in `sources.json`; per-case features in `127x04-features.json` / `127x08-features.json`;10-minute checks and early command-event hashes in `watch-history.jsonl`.

Collected source revision `45ed20a7ae7f` at `2026-10-18T08:55:33.330059+00:00`. RF1 hz_report and scale_report SHA256s match the original RF1 readout. PT1 metadata SHA256 `354f7b9827fa6e02c706c58929101ca3ce21491987e56ce5eb0ec4da012cb665`. Runtime-only analysis artifact SHA256s computed at this report generation:

| Artifact | SHA256 |
| --- | --- |
| collect-source.txt | 5615b1abe2eea14f3f53b40454f749c58c5033d05a4169a8965462b0aedf5197 |
| collector-runtime-source.txt | d7c26634126fd6504fc7040fc6bf95e46b38f331a3ab443de78eb0474822d3ac |
| pt1-behaviour-source.txt | b2450a0c40bab52f3fd3cab60b8350e9f033aad169adf076a15de84da6906437 |
| remote-collect-source.txt | d746f94f05f15a4b1d9adc99c96c653b15fde9debfb54a329ae3b630865204e5 |
| remote-status-source.txt | e1a8e1a6d4616165fb07c57edd9a299f34fe08d36dc5c874a78aaeee157db415 |
| render-source.txt | 4199562dbcf589a6db2a036d3a98ffa2adf152eac1ab047b482b652772f8da21 |
| rf1-extra-source.txt | faeb1d4a13d57a6a2737a9d12090224e71ad2410edfcaa738298e2074e0346d1 |
| score-source.txt | 777ec1730d6b1ed3c8a9660025f2d384281d3f8df651acfc3d3f77b0333cbe6d |
| watch-source.txt | c67cbd6e2b8577effd37e9ed292e06aec7576c880b04de352cf7fa06daf1c1b3 |
| bot/livediag/live_metrics.py | 631dd56ae639a026b4e7e0d0049427595db04eb6de6f620b7111b889b0e840e5 |
| bot/livediag/l16_report.py | bb2067f2e827e4dff774718939dfebbe7a0867758f38e1a4fd715f11d3c4d34f |
| bot/fullpool/scale_report.py | 597726ecad0cc2c7a011647a06682d1d962216798ae98e4d933bdc70433dfe95 |
| bot/fullpool/hz_report.py | 595f91862b8f7471a47ee51c6a52a56e1e9ea430bf10bbabe8a9859fff240dc7 |
| bot/livediag/behaviour_diag.py | b2450a0c40bab52f3fd3cab60b8350e9f033aad169adf076a15de84da6906437 |

The recorder does not provide `from_second` selection provenance; its absence is unavailable, not a zero share. Spell damage and ElectroSpirit actual jump hits are also unavailable. All observed surrogate definitions and coverage are explicit above.
