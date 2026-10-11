# X4S: R3a cutoff default (S-default) inside K4 at slower-core budgets

**Exploration only, NEVER ADOPTABLE.** Reduced 2026-10-11T04:21:20Z; 600 complete paired seeds (all nine arms) from 4503604807370496+[0,600), hosts {'127x03': 300, '127x08': 300}. Opponent: the exact S1/K2 v1 policy. Honest lateness, d=27/capacity 1, five decks, alternating seats. Budgets emulate ≈1.0/0.8/0.7/0.6× fleet core speed (budget equivalence, not real underclocking).

## Loss vs v1 (paired-seed 95% CIs)

| Budget | K4 loss % | K4S loss % | K4S − K4, pp | K4 cutoff % | K4S cutoff % | K4S student-default % of decisions |
|---|---:|---:|---:|---:|---:|---:|
| 200 ms | 18.50 [15.33, 21.50] | 20.67 [17.50, 23.83] | 2.17 [-0.33, 4.67] | 4.02 [3.48, 4.65] | 3.18 [2.86, 3.52] | 0.76 [0.64, 0.89] |
| 160 ms | 27.83 [24.17, 31.33] | 18.17 [15.16, 21.33] | -9.67 [-13.50, -6.00] | 18.61 [17.13, 20.16] | 12.41 [11.55, 13.28] | 3.40 [3.03, 3.80] |
| 140 ms | 47.33 [43.33, 51.50] | 22.17 [18.83, 25.50] | -25.17 [-29.67, -20.67] | 45.52 [43.55, 47.51] | 28.30 [27.18, 29.42] | 8.14 [7.58, 8.72] |
| 120 ms | 89.00 [86.50, 91.33] | 26.00 [22.33, 29.50] | -63.00 [-67.00, -59.00] | 88.59 [87.57, 89.55] | 57.40 [56.23, 58.56] | 19.51 [18.91, 20.11] |

Anchor K0c-200 (S1 one-core cached-v1 coarse-first): loss 43.17 [39.17, 47.00], cutoff 78.86%.

## Paired contrasts (pp, 95% CI)

| Contrast | pp | 95% CI |
|---|---:|---:|
| K4S-200 minus K4-200 | 2.17 | [-0.33, 4.67] |
| K4-200 minus K0c-200 | -24.67 | [-29.17, -20.17] |
| K4S-200 minus K0c-200 | -22.50 | [-27.17, -18.00] |
| K4S-160 minus K4-160 | -9.67 | [-13.50, -6.00] |
| K4-160 minus K0c-200 | -15.33 | [-20.00, -10.50] |
| K4S-160 minus K0c-200 | -25.00 | [-29.67, -20.17] |
| K4-160 minus K4-200 | 9.33 | [5.33, 13.17] |
| K4S-160 minus K4-200 | -0.33 | [-3.67, 3.17] |
| K4S-160 minus K4S-200 | -2.50 | [-6.00, 1.00] |
| K4S-140 minus K4-140 | -25.17 | [-29.67, -20.67] |
| K4-140 minus K0c-200 | 4.17 | [-0.50, 9.00] |
| K4S-140 minus K0c-200 | -21.00 | [-25.50, -16.33] |
| K4-140 minus K4-200 | 28.83 | [24.50, 33.33] |
| K4S-140 minus K4-200 | 3.67 | [0.33, 7.17] |
| K4S-140 minus K4S-200 | 1.50 | [-2.17, 5.17] |
| K4S-120 minus K4-120 | -63.00 | [-67.00, -59.00] |
| K4-120 minus K0c-200 | 45.83 | [41.67, 50.00] |
| K4S-120 minus K0c-200 | -17.17 | [-21.67, -12.67] |
| K4-120 minus K4-200 | 70.50 | [66.83, 74.17] |
| K4S-120 minus K4-200 | 7.50 | [3.33, 11.50] |
| K4S-120 minus K4S-200 | 5.33 | [1.17, 9.50] |

## Readings (pre-declared, descriptive)

"Rescues" = upper CI(K4S-b − K4-b) < 0. "Holds" = upper CI(K4S-b − K4-200) ≤ +5 pp (S1 margin).

| Budget | Rescues K4 | Holds within 5 pp of K4-200 |
|---|---|---|
| 200 ms | False | None |
| 160 ms | True | True |
| 140 ms | True | False |
| 120 ms | True | False |

## Timing and defaults

| Arm | W/L/D | Decisions | Fallback % | Overrun % | Wall p50/p95/p99/max ms | Overrun p50/p99/max ms | Cut returns > budget+8 ms | Prep cutoffs | Game CPU h |
|---|---:|---:|---:|---:|---|---|---:|---|---:|
| K0c-200 | 341/259/0 | 118043 | 46.53 | 0.05 | 192.5/192.7/192.9/229.7 | 5.5/24.2/29.7 | 16 | {"scoring_or_none": 117770, "belief": 171, "sample": 102} | 9.13 |
| K4-200 | 489/111/0 | 70180 | 0.74 | 0.14 | 114.7/184.1/192.9/214.1 | 3.6/12.0/14.1 | 18 | {"scoring_or_none": 69931, "belief": 175, "sample": 74} | 8.26 |
| K4S-200 | 476/124/0 | 69545 | 0.74 | 0.15 | 114.0/177.3/192.9/220.3 | 3.8/13.0/20.3 | 17 | {"scoring_or_none": 69297, "belief": 178, "sample": 70} | 8.12 |
| K4-160 | 433/167/0 | 72824 | 0.94 | 0.12 | 118.5/152.8/153.0/179.3 | 5.1/16.8/19.3 | 24 | {"scoring_or_none": 72299, "belief": 466, "sample": 59} | 8.42 |
| K4S-160 | 491/109/0 | 70357 | 0.96 | 0.14 | 114.8/152.9/153.0/185.7 | 5.1/17.1/25.7 | 24 | {"scoring_or_none": 69840, "belief": 462, "sample": 55} | 8.12 |
| K4-140 | 316/284/0 | 79631 | 1.07 | 0.06 | 128.3/132.9/133.0/152.3 | 5.3/12.3/12.3 | 12 | {"scoring_or_none": 78974, "belief": 609, "sample": 48} | 8.70 |
| K4S-140 | 467/133/0 | 71266 | 1.16 | 0.06 | 115.4/133.0/133.1/156.9 | 5.6/14.2/16.9 | 10 | {"scoring_or_none": 70604, "belief": 607, "sample": 55} | 7.98 |
| K4-120 | 66/534/0 | 95698 | 1.36 | 0.14 | 112.6/112.9/113.0/141.5 | 4.1/13.6/21.5 | 23 | {"scoring_or_none": 94881, "belief": 713, "sample": 104} | 8.45 |
| K4S-120 | 444/156/0 | 74221 | 1.55 | 0.12 | 112.5/113.0/113.1/131.7 | 5.4/10.0/11.7 | 14 | {"scoring_or_none": 73412, "belief": 711, "sample": 98} | 7.71 |

## What it means

**Yes: the R3a cutoff default rescues K4 on slower cores, and it does so by breaking K1's WAIT spiral.** Without it, K4's loss is strongly non-linear in budget: 18.5% → 27.8% → 47.3% → 89.0% at 200/160/140/120 ms. Cutoffs rise 4.0% → 18.6% → 45.5% → 88.6%. At 160 ms that is higher than REVIEW-K's lower-bound projection of 13.7% (which did not model the spiral); at 140/120 ms it is close to or above the 27–49% projected for 0.7–0.6×. With the student default, loss stays at 20.7% / 18.2% / 22.2% / 26.0%.

- **Mechanism.** At 120 ms, K4 plays on only 10.5% of decisions, and its median candidate set is 24 (elixir full; [mechanism diagnostics](receipts/mechanism-diagnostics.json)). K4S keeps its play rate at about 33% at every budget, the same as K4-200, and its candidate sets stay at a median of 12. So K4S also cuts off less (57% vs 89% at 120 ms). The student is directly responsible for only 3–20% of decisions, but those plays keep the game state out of the regime where search cannot finish.
- **Mac implication (exploration-grade).** With a WAIT default, 4-core K4 needs roughly ≥0.9× fleet per-core speed. At 0.8× (160 ms) it already loses +9.3 pp [5.3, 13.2] vs K4-200, and at ≤0.7× it is no better than, or worse than, the one-core K0c anchor. With the S-default:
  - 0.8× is indistinguishable from fleet-speed K4: −0.3 pp [−3.7, 3.2].
  - 0.7× is +3.7 pp [0.3, 7.2]: within 5 pp at the point estimate, but not by the CI rule.
  - 0.6× is +7.5 pp [3.3, 11.5]. That is still no worse than S1's 1-core student tier at its full 200 ms (28.2%, on different seeds), and 17.2 pp better than K0c-200 here.
- **At 200 ms the default is not free.** K4S−K4 is +2.2 pp [−0.3, 4.7]. It is not significant, but it points toward a small cost when cutoffs are rare. A deployment would use the S-default only below some speed threshold, which would itself need its own pre-registered test. This study cannot adopt anything.

## Caveats
- **Budget equivalence, not real slow hardware.** Rollout and student inference both run at fleet speed inside a smaller budget. Student inference measured about 6.4 ms per poll on the fleet (S1 qualification p50). On truly 0.6× cores it would take about 10.6 ms, so the K4S arms are slightly flattered at low budgets, by roughly 4 ms of an uncharged budget. The emulation also does not slow belief preparation or observation building by the speed factor. It only shrinks the deadline they share.
- One opponent (the v1 policy), five decks, symmetric delay 27, fleet load. There was no Mac, no perception load, no live play, and no heldout data. Each 4-thread game ran on 5 dedicated physical cores with no SMT siblings in its mask.
- The R3a student remains killed and **NEVER ADOPTABLE** under R3 Stage 1. This is a compute-tier exploration only.
- The contrasts and readings are unadjusted pointwise 95% CIs: 30 contrasts were examined.

## Provenance
- **Freeze:** plan, harness, seed audit and qualification were committed in 63538665 before any reporting game.
- **Seeds:** 4503604807370496+[0,600). All 600 paired blocks completed on both hosts. There were no interrupted or excluded blocks, and each of the 50 (seat, own-deck, opponent-deck) cells has 12 seeds.
- **Qualification ([receipts](receipts/)):**
  - unit tests: 31 passed;
  - 125-state corpus: K4/K4S frozen-equal and mutually equal on 125/125, zero-budget → R3a on 125/125, 124 injected student defaults;
  - no-deadline K4 and K4S games produce identical command hashes on 2/2 seeds;
  - smoke: 72 games;
  - two live STOP tests on 127x08, each exiting in about 2 s with no processes left.
- **Sol review r1:** the 9 operational findings were fixed before launch.
- **Execution ([execution.json](receipts/execution.json)):**
  - 127x03: 01:50:49Z → 04:18:12Z, 37.4 CPU-h for the whole tree;
  - 127x08: 01:50:50Z → 04:18:32Z, 37.6 CPU-h;
  - 12 five-core slots per host on physical cores 0–59, supervisor on core 62, all at nice 19;
  - minimum MemAvailable was 117.7 GiB, and peak owned PSS was 4.1 GiB.
- **Shutdown:** no STOP occurred during reporting. Both supervisors exited cleanly with empty process groups. STOP files were written afterwards only to retire the 05 sync. 127x08 has had zero X4S processes since 04:18:32Z.
- **Raw data:** the 5,400 games remain under /mpac on 03/08 and in the 05 mirror and are not committed.
- **Statistics:** 5,000 shared paired-seed bootstrap resamples (RNG 2026101104). An independent recount from the raw game files, using a separate 2,000-resample bootstrap, reproduces every loss count and the K4S−K4 contrasts within 0.3 pp.
- **Full data:** [results.json](results.json), [plan](PLAN.md), [progress](PROGRESS.md).
