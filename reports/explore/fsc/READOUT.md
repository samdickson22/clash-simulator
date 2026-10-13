# FSC pre-declared readout (U3/U4, exploration, NEVER ADOPTABLE)

Declared before any FSC game, smoke included. Taken from the fleet utilization plan r1 (Items 3–4), adopted as U3/U4 in
COORDINATOR 2026-10-13 01:15Z. The reducer is [reduce.py](reduce.py); outcomes are read only after the host's STOP
session. During the run only counts are read (`progress.json`, proof counts).

## What counts
- A block counts only if its proof exists, every game SHA-256 matches, and every game passes X4S2's `check_game` plus the
  FSC checks: X deck mapping (own `decks[i%5]`, opponent `decks[(i//5)%5]`), checkpoint SHA per arm, `s_default` flag,
  native 44874fd6, config SHA ∈ {plan-fsc.json, plan-fsc-04.json}, host as launched.
- **Prefix rule (as X4S-4 [E8]).** Each host's blocks are cut to the **largest complete prefix in that host's worklist
  order**: `wl-03.json` has indices 0–2399 at 200 ms and `wl-04.json` has 2400–3899 at 180 ms.
  - **Amendment r2, before any game:** the top-up segments (3900–7899) are dropped. Under the K4S runner's condition, STOP
    must be verified shortly after STOP_AT, and every phase's `--stop-at` is ≤ STOP_AT ≤ `DEADLINE` (07:30Z since the coordinator's 2026-10-13 raise). Neither worklist is expected to finish, so both
    outcomes come from time-cut prefixes.
  The prefix ends at the first block that is not complete. Complete blocks beyond it are dropped and their count is
  disclosed. So the sample is never selected by game duration.
  - Blocks interrupted by the final STOP or `--stop-at` are retired and end the prefix.
  - Blocks interrupted by an intermediate **console-user yield** STOP are retired and *skipped inside* the prefix.
    Their never-started blocks continue, in order, in the next phase.

## Primary: Δ200 = loss(K4S-200) − loss(K4-200)
- Paired by seed, over every 200 ms block in the 03 prefix (indices 0–2399; 04 runs no 200 ms blocks).
- 5,000-rep percentile bootstrap over seeds, RNG seed 2026101301, 95% CI, unadjusted.
- **Outcome**, using the first rule that matches:
  1. **always-on supported** if the upper 95% CI ≤ +1.0 pp. If the lower CI is also > 0, the label says
     "small positive cost".
  2. **speed gate needed** if the lower 95% CI > 0.
  3. **unresolved** otherwise.
- About 2 h of reporting gives roughly 1,100 seeds, for an expected half-width of about ±1.8 pp. At 2,400 seeds it
  would be ±1.25 pp; both scale from X4S's ±2.5 pp at 600 seeds.

## Secondary and descriptive (no outcome)
- Δ200 pooled with X4S's 600 X seeds, `x4s:K4S-200 − x4s:K4-200`. Bootstrap stratified by source; seeds weighted equally.
- **Δ180 = K4S-180 − K4-180** on the 04 prefix (indices 2400–3899): the 0.9× point. Also pooled with X4S2 phase E's X
  seeds, stratified.
- Per arm: loss, cutoff, student-default, overrun and fallback rates; poll and wall-latency quantiles; game CPU-hours.

## Interpretation limits (stated now)
- Exploration only. R3a stays killed under R3 Stage 1, and nothing here admits any arm to live play.
- "Always-on supported" means the measured full-speed cost is ≤ 1 pp on X decks under the fleet emulation. It is
  evidence for a future Mac prereg, not a decision.
- The guard (G) population is not run.
