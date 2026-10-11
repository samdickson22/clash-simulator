# X4S2: stress test of the X4S student cutoff default (exploration, NEVER ADOPTABLE)

Reduced 2026-10-11T13:02:16Z from 16,980 new games (3,948 complete blocks, 12 interrupted blocks retired) plus the 5,400 paired X4S games. Opponent: the exact X4S/S1 v1 policy. Settings: d = 27, capacity 1, honest lateness, 4 search threads per game on dedicated 5-core slots. Hosts: 127x03 and 127x08.

**Status: exploration only, NEVER ADOPTABLE.** R3a stays killed under R3 Stage 1. Nothing here admits any arm to live
play. Plan: [PLAN.md](PLAN.md), with Amendment 1 after the coordinator extended 127x08 to 12:30Z. Log:
[PROGRESS.md](PROGRESS.md). Full tables: [RESULTS-tables.md](RESULTS-tables.md) and [results.json](results.json).

## Bottom line
1. **The X4S conclusion survives.**
   - **Stressed scaling:** S-default (K4S) still rescues 4-thread K4 when the student's inference (K4Sh) or *all*
     decision preparation (K4Sf) is charged an extra 1/s on top of the shorter budget. At 0.8×, 0.7×, 0.6× and 0.5×,
     K4Sh loses 21.7%, 23.2%, 24.0% and 25.5% against v1, where K4 loses 27.8%, 47.3%, 89.0% and 100%. These are
     within −2 to +3.5 pp of the X4S K4S numbers on the same seeds.
   - **Held-out decks:** on human opponent decks that were in no R1 training matchup, K4S − K4 at 140 ms is −31.4 pp
     [−34.9, −27.6] over 1,068 seeds. At 120 ms on the same decks, K4 collapses to 92.1% while K4S holds **22.8%** (−69.4 pp [−72.2, −66.3]) and K4Sh holds 21.0%. Both are *below* K4-200's 26.7% there (−4.0 [−7.4, −0.7] and −6.0 [−9.3, −2.7]).
2. **X4S caveat 1 was mis-specified.** Under a uniform slow core, budget equivalence already charges inference *and*
   preparation at 1/s. All in-timer work W (fleet-ms) must satisfy W ≤ 192·s, versus 200·s − 8 in the emulation. The
   measured poll (~10 ms) and pre-scoring work (~40 ms) were inside that timer all along. So K4Sh and K4Sf are
   **stress tests** of a student or preparation that is a further 1/s slower relative to search (e.g. inference at
   s²). They are not corrections. Even then the result holds.
3. **Threshold.** K4 (WAIT default) is fine down to 0.9×: K4-180 − K4-200 = +0.8 pp [−2.5, 4.2]. It breaks between
   0.9× and 0.8×: K4-160 is +9.3 pp vs K4-200, and K4-180 − K4-160 = −8.5 pp [−12.5, −4.3]. S-default's effect goes
   from about +2 pp at 1.0× (X decks; −0.3 on the guard decks) to −2.2 [−5.2, 0.8] at 0.9× and −9.7 at 0.8×.
   Pooled over both populations (1,668 seeds), the full-speed cost is **+0.6 pp [−0.8, 2.2]**.

   **Recommendation (exploration-grade):** enable S-default on any Mac whose measured search speed is **below 0.95×
   fleet**. That means a budget-equivalent of <190 ms, i.e. a K4 cutoff rate above ~5%. Make S-default the default
   at **≤0.9×**, where its point estimate is already favourable and K4 alone is one step from its cliff. If a single
   always-on configuration is preferred, the measured full-speed cost is small and not significant
   (pooled +0.6 pp [−0.8, 2.2] at 1.0×). A preregistration should test the threshold rule directly; this study cannot adopt it.
4. **S-lite does not remove the full-speed gap and is not needed.** S-lite applies the student only when the coarse
   scan is incomplete.
   - At 200 ms: K4Sl − K4 = +2.3 [−0.3, 5.0] and K4Sl − K4S = +0.2 [−1.8, 2.2].
   - At 140 ms and 160 ms it rescues just as well as full S-default: −25.5 and −7.8 pp vs K4.

   Student defaults are under 1% of decisions at 200 ms, so the small 200 ms gap is not produced by the default rule.
   It is most likely noise; the guard decks show −0.3.

## Loss vs v1, X population (X4S five decks, the same 600 X4S seeds; paired 95% CIs)
`x4s:` marks the X4S games on these seeds. All other arms are new here. Rates are % of search decisions.

| Budget (≈ speed) | K4 | K4S (X4S) | K4Sh (inference stressed) | K4Sf (all prep stressed) | K4Sl (lite) | K4Sh − K4 (pp) | K4Sh − K4S (pp) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 200 (1.0×) | 18.5 [15.3, 21.7] | 20.7 [17.5, 24.0] | – | – | 20.8 [17.7, 24.2] | – | – |
| 180 (0.9×) | 19.3 [16.3, 22.7] | 17.2 [14.2, 20.2]* | – | – | 18.8 [15.8, 22.0] | – | – |
| 160 (0.8×) | 27.8 [24.3, 31.5] | 18.2 [15.2, 21.3] | 21.7 [18.5, 25.0] | – | 20.0 [16.8, 23.2] | −6.2 [−10.3, −2.2] | +3.5 [0.0, 6.8] |
| 140 (0.7×) | 47.3 [43.3, 51.3] | 22.2 [19.0, 25.7] | 23.2 [20.0, 26.5] | 22.2 [18.8, 25.5] | 21.8 [18.5, 25.2] | −24.2 [−28.8, −19.3] | +1.0 [−3.0, 5.2] |
| 120 (0.6×) | 89.0 [86.5, 91.5] | 26.0 [22.5, 29.7] | 24.0 [20.7, 27.5] | 23.8 [20.7, 27.2] | – | −65.0 [−69.0, −60.8] | −2.0 [−6.0, 2.3] |
| 100 (0.5×) | 100.0* | – | 25.5 [22.0, 29.2] | – | – | −74.5 [−78.0, −70.8] | – |

\* new in X4S2 (K4-100, and K4/K4S/K4Sl at 180 ms).

Further X contrasts:
- K4Sf-140 − K4S-140 = 0.0 [−4.3, 4.2]; K4Sf-120 − K4S-120 = −2.2 [−6.2, 1.8].
- Versus K4-200: K4Sh-160 +3.2 [−0.7, 7.0], K4Sh-140 +4.7 [0.5, 8.8], K4Sh-120 +5.5 [1.5, 9.7],
  K4Sh-100 +7.0 [2.8, 11.2], K4Sf-120 +5.3 [1.3, 9.3].
- **Drift control:** K4S-140r, a rerun of X4S's K4S-140 on the same seeds, differs by −0.7 [−4.5, 3.2]. So
  cross-run pairing with X4S is sound.

| Arm | Cutoff % | Student default % | Coarse complete at cutoff % | Play % | Charged poll ms | Scale sleep ms | Prep ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| K4Sh-160 | 16.1 | 4.5 | 74.3 | 33.1 | 10.0 | 2.6 | 46.6 |
| K4Sh-140 | 39.8 | 12.5 | 67.0 | 32.8 | 10.1 | 4.4 | 49.3 |
| K4Sh-120 | 70.9 | 25.3 | 35.4 | 31.3 | 10.3 | 6.9 | 52.6 |
| K4Sh-100 | 83.8 | 23.6 | 8.3 | 24.3 | 10.4 | 10.5 | 56.7 |
| K4Sf-140 | 69.0 | 24.4 | 33.2 | 30.8 | 10.3 | 21.6 | 71.4 |
| K4Sf-120 | 86.0 | 20.9 | 6.9 | 21.4 | 10.5 | 33.3 | 83.0 |
| K4S-140r | 27.4 | 8.0 | 72.0 | 32.8 | 10.1 | 0 | 39.8 |
| K4-100 | 98.2 | 0 | 4.8 | 2.4 | 11.0 | 0 | 47.7 |

Prep ms is the wall time from decision start to the start of scoring (or the whole decision, if it never scored),
including any scale sleep.

## Loss vs v1, G population: L2-v4 own decks vs held-out guard decks (fresh seeds)
Own decks: Hog 2.6, X-Bow cycle, Royal Hogs spawners. Opponent decks: Hog EQ, Goblinstein Royal Hogs and ArcherQueen
Royal Delivery, which are in no R1 training matchup. The 18 cells are 3 own × 3 opponent × 2 seats.

| Budget (≈ speed) | Seeds | K4 | K4S | K4Sh | K4S − K4 (pp) | K4Sh − K4 (pp) |
|---|---:|---:|---:|---:|---:|---:|
| 200 (1.0×) | 1,068 | 26.7 [24.0, 29.3] | 26.4 [23.8, 29.1] | – | -0.3 [-2.2, 1.7] | – |
| 140 (0.7×) | 1,068 | 58.6 [55.6, 61.7] | 27.2 [24.6, 30.0] | 23.5 [21.0, 26.0] | -31.4 [-34.9, -27.6] | -35.1 [-38.8, -31.5] |
| 120 (0.6×) | 1,080 | 92.1 [90.5, 93.6] | 22.8 [20.2, 25.4] | 21.0 [18.7, 23.4] | -69.4 [-72.2, -66.3] | -71.1 [-73.8, -68.1] |

Against K4-200 on these decks:
- K4S-140 +0.6 [-2.8, 3.9]; K4Sh-140 -3.2 [-6.6, 0.2];
- K4S-120 -4.0 [-7.4, -0.7]; K4Sh-120 -6.0 [-9.3, -2.7].

K4Sh − K4S: -3.7 [-6.9, -0.6] at 140 and -1.8 [-4.9, 1.2] at 120.

Cutoff rates:

| Arm | 120 ms | 140 ms |
|---|---:|---:|
| K4 | 86.1% | 45.1% |
| K4S | 63.4% | 35.1% |
| K4Sh | 77.4% | 49.7% |

Student-default rates are 20.3% / 26.3% at 120 ms (K4S / K4Sh). The cells are balanced (59–60 seeds per cell).

On these decks K4 is weaker even at full speed (26.7% vs 18.5% on X). Loss decreases as student use increases:
K4Sh ≤ K4S ≤ K4 at 120 and 140 ms. Read this cautiously, because the own decks are in R3a's training distribution.

### Pooled X + G (stratified bootstrap)
| Contrast | Seeds X / G | pp | 95% CI |
|---|---:|---:|---|
| K4S minus K4 at 200 ms | 600 / 1068 | +0.6 | [-0.8, 2.2] |
| K4S minus K4 at 140 ms | 600 / 1068 | -29.1 | [-32.0, -26.4] |
| K4Sh-140 minus K4-140 | 600 / 1068 | -31.2 | [-34.0, -28.3] |
| K4S-120 (X4S / G) minus K4-120 | 600 / 1080 | -67.1 | [-69.3, -64.8] |
| K4Sh-120 minus K4-120 | 600 / 1080 | -68.9 | [-71.2, -66.6] |

## Mechanism
- **Why the stress barely matters.** At ≤0.7× the K4S family plays on about 31–33% of decisions, the same as K4-200.
  K4 instead collapses into WAIT: 2.4% plays at 100 ms, and 10.5% at 120 ms in X4S.
  - Extra inference or preparation cost raises the cutoff rate, e.g. K4Sh-120 at 71% vs X4S K4S-120 at 57%, and
    K4Sf-120 at 86%.
  - Each extra cutoff without a complete play becomes a student play. The student alone is a reasonable policy
    (S1: 28.2% at one core).
  - So loss degrades only slowly, from ~22% toward the student-only level.
- **What remains of search.** At the lowest settings (K4Sh-100, K4Sf-120), 84–86% of decisions cut off and only
  7–8% of cutoffs had finished the coarse scan. In that regime the bot is effectively "student + search-chosen
  waits". It still beats the one-core K0c-200 anchor from X4S (43.2%) by a wide margin.
- **Measured costs.** The charged search-seat poll is 10.0–11.0 ms, not the 6.4 ms quoted in X4S (that was the bare
  forward). Pre-scoring preparation is ~40 ms at fleet speed, about 20% of a 200 ms budget. That 40 ms is a larger
  lever than inference for slow Macs.

## Caveats
- **Emulation, not hardware.** Budget equivalence models a uniformly slower core, and K4Sh/K4Sf add *relative*
  slowdowns on top. A real Mac may differ: different core counts, Neural Engine or GPU inference, thermal throttling
  and perception load.
  - The 8 ms reserve is not scaled (≤4 ms difference).
  - Overruns are under-penalized by the factor s, but they occur on ~0.1% of decisions.
- **One opponent policy (v1).** The decks and seeds differ by population. The G own decks are in R3a's training
  distribution; only the opponent decks are held out. All guard decks are `bridge_wincon`.
- **Statistics.** Many contrasts are reported with unadjusted pointwise 95% CIs (about 60). Readings near zero
  (e.g. K4Sh-140 − K4S-140 on G, −3.7 [−6.9, −0.6]) should not be over-read.
- **Cross-run pairing.** X-population contrasts pair new games with X4S games from a different run on the same
  seeds. The K4S-140r replicate bounds the drift at −0.7 [−4.5, 3.2].
- **Retired blocks.** 127x08's planned 09:15Z stop interrupted 12 D blocks. They were retired, not re-run. The G
  population is 1,068 of 1,080 seeds, and the cells stay balanced to within one seed.

## Provenance and execution
- **Commits:**
  - de48533f: freeze (plan, harness, seed audit, qualification);
  - c1ddfacf: Phase D added before launch;
  - 1501be97: Amendment 1, after the coordinator moved 08's stop to 12:30Z (07:28Z), adding phases E and F;
  - phase receipts: 3ed4cb63 (A), 00328d1b (B), a88d5b8e (C), 16fec968 (B+D), b577a255 (E);
  - progress: aca9216c;
  - this report: see PROGRESS.
- **Qualification ([receipts/](receipts/)):**
  - 42 unit tests;
  - 125-state corpus: anchor_x equals S1 anchor, with no deadline and under injected cutoffs; K4/K4S/K4Sl
    frozen-equal; S-lite rule checks on 1 and 4 threads;
  - no-deadline K4/K4S/K4Sl/K4Sh/K4Sf command hashes identical on both populations;
  - three smokes, with a per-decision production check of the prep charge (sleep share = target ± 0.02 on every exit
    path);
  - guard-card support: 27 cards;
  - STOP test on 08: exit 2 s after STOP, 0 processes left.
- **Sol reviews** (gpt-6.1-sol, high effort):
  - r1: 2 blockers and 4 should-fixes, all fixed;
  - r2: 2 blockers in the K4Sf timeout charge, fixed with scaled internal deadlines;
  - r3: no blockers.
- **Execution** (12 five-core slots per host on cores 0–59, nice 19, no console users at any check, min MemAvailable
  117.6 GiB, max owned PSS 4.6 GiB; 164 CPU-h in total):

  | Host | Phase | Window (UTC) | Blocks | Exit |
  |---|---|---|---:|---|
  | 127x03 | rep03 (A, B) | 04:56:59 → 08:17:25 | 570 | rc 0 |
  | 127x03 | rep03C (C, D) | 08:17:25 → 10:34:00 | 870 | rc 0 |
  | 127x03 | rep03EF | 10:34:05 → 13:01:01 | 840 | rc 0 |
  | 127x08 | rep08 (A, B, D) | 04:56:58 → 09:15:09 | 772 | planned 09:15Z stop; 12 interrupted D blocks retired |
  | 127x08 | rep08L | 09:15:14 → 09:31:49 | 56 | rc 0 |
  | 127x08 | rep08EF | 09:31:49 → 12:00:00 | 840 | rc 0 |

  Every supervisor exited with an empty process group.
- **127x08 vacancy:**
  - zero X4S2 processes at 12:00:53Z;
  - the 05 backstop touched STOP at 12:15:16Z and its census found 0 X4S2 processes
    ([receipts/vacate08.jsonl](receipts/vacate08.jsonl));
  - the sync's final pull and retirement of 08 was at 12:16:12Z, with no contact after that.
- **127x03:**
  - all work ended at 13:01:01Z, and there were 0 X4S2 processes at 13:01:23Z;
  - STOP was placed at 13:01Z, and the sync retired 03 at 13:01:41Z.
- **Raw data:** games remain under /mpac on 03/08 and in the 05 mirror (`/mpac/sdicks02/jobs/clasher/x4s2-20261011`).
  They are not committed.
- **Statistics:**
  - 5,000 paired-seed bootstrap resamples (RNG 2026101105), percentile 95% CIs, unadjusted;
  - X contrasts pair with the X4S games by seed;
  - phases were reduced only after they ended; in-progress populations stayed sealed (`--pops`/`--g-max`).
