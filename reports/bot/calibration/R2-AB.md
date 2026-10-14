# Does a more faithful planner model make the bot stronger? Runtime r2 vs r1 (exploration)

2026-10-14, calibration batch-2 agent. Exploration tier, no preregistration.

## Answer

**No measurable gain.** K4S-st plans on the calibrated engine (runtime r2) and plays in RoyaleSim 15.535, the trusted
evaluator. It scores the same as with the uncalibrated model (r1):

| | paired r2 − r1, both opponents |
|---|---|
| HEADLINE cases 0–299 (600 games) | −0.005 [−0.038, +0.028] |
| 1,800 games, cases 0–899 | **−0.010 [−0.031, +0.010]** |

This holds even though the planner's model moved much closer to native:
- train no-tower ≤¼ tile: 50.7 → 72.3 (batch 1 + 2), against RoyaleSim's 78.8;
- HP exact: 65.0 → 80.5;
- Python↔Rust digest parity: 429 → 574/577.

Per opponent, over the 1,800 games: R3a +0.002 [−0.029, +0.033]; v1 −0.022 [−0.049, +0.004]. A 2–3 pp change in either
direction would have been detected. A larger gain is ruled out; a small loss against v1 is not.

In our own engine, where both the game and the planner change, r2 − r1 = +0.028 [−0.008, +0.065]. That is not a planner
test: both players now play in the calibrated physics.

**Recommendation for the lead:** switching the bot's planner to r2 is strength-neutral. Keep r1 as the default.
- Switch to r2 only if the planner must model native mechanics for another reason (e.g. ExIt labels or live play),
  since it costs nothing measurable.
- The gains in the search-scaling study came from candidate quality (K4S-st); model fidelity was not the bottleneck at
  this level.
- The near-tied phi leaf (search-scaling RESULTS.md: median best-vs-second gap 0.0004–0.0005) is the likelier limit.

## Protocol

- **Cases:** HEADLINE-v1 (`bot.eval.headline`, base 1455777415631152), extended to 0–899 for power.
- **Players:** candidate K4S-st (search-scaling RESULTS.md; `make_player`), opponents R3a and v1.
- **Scoring:** win 1, draw 0.5, loss 0.
- **One tree, two runtimes.** All arms run from the same isolated eval tree on 127x03,
  `/mpac/sdicks02/jobs/clasher/bot-calib2-eval/tree` (bot/ and reports/explore/x4s copied from the worktree). Only these
  differ between arms:
  - `CLASHER_BOT_RUNTIME`: `clasher-bot-runtime/r1` or `/r2`;
  - `CLASHER_BOT_RUNTIME_PINS`: `r1` or `r2`.
- **Pairing:** by (opponent, case index). 95% percentile bootstrap over cases, 4,000 draws, seed 0. "Both" is the
  equal-weight mean of the two opponents, resampling cases within each (`eval/paired.py` in the eval dir).
- **What r2 changes.** r2 = r1 plus the calibrated engine diff (BATCH1.md + BATCH2.md; RUNTIME-R2-PLAN.md, "Executed").
  - Native `c50cb066…`, built with r1's recipe; that recipe reproduces r1's `44874fd6` byte for byte. Checkpoints
    unchanged.
  - In RoyaleSim, the game engine is identical in both arms. The runtime only changes the planner's model (the Python
    config export and the native core) and the runtime engine code used on the opponents' observation path.

**Validity:**
- The r1 arms reproduce the original search-scaling runs exactly: `command_sha256` identical on 600/600 games in
  RoyaleSim (`bot-search-rsim-st`) and 600/600 in ours (`bot-search-bc`).
- No game errored in any arm. 143 of the 1,800 RoyaleSim games (8%) are command-identical between r1 and r2.
- Every arm ran with no wall-clock budget cut.

## Results

| planner runtime | engine | cases | vs R3a: r1 → r2 (paired) | vs v1: r1 → r2 (paired) | **both, r2 − r1** |
|---|---|---|---|---|---|
| **r2 (final)** | **RoyaleSim 15.535** | **0–299 (HEADLINE)** | 0.723 → 0.720, −0.003 [−0.053, +0.047] | 0.890 → 0.883, −0.007 [−0.050, +0.037] | **−0.005 [−0.038, +0.028]** |
| r2 | RoyaleSim 15.535 | 300–899 | 0.740 → 0.745, +0.005 [−0.033, +0.045] | 0.878 → 0.848, −0.030 [−0.063, +0.002] | −0.012 [−0.038, +0.013] |
| **r2** | **RoyaleSim 15.535** | **0–899 (1,800 games)** | 0.734 → 0.737, +0.002 [−0.029, +0.033] | 0.882 → 0.860, −0.022 [−0.049, +0.004] | **−0.010 [−0.031, +0.010]** |
| r2 | ours (calibrated game too) | 0–299 | 0.720 → 0.737, +0.017 [−0.040, +0.073] | 0.860 → 0.900, +0.040 [−0.007, +0.087] | +0.028 [−0.008, +0.065] |
| c10 (interim: batch 2 through §5) | RoyaleSim 15.535 | 0–899 | 0.734 → 0.727, −0.008 [−0.040, +0.022] | 0.882 → 0.866, −0.017 [−0.043, +0.009] | −0.012 [−0.033, +0.007] |
| c10 | ours | 0–299 | 0.720 → 0.760, +0.040 [−0.010, +0.093] | 0.860 → 0.877, +0.017 [−0.033, +0.063] | +0.028 [−0.005, +0.063] |
| int1 (batch 1 + BarbLog HP + Rust fixes) | RoyaleSim 15.535 | 0–299 | 0.723 → 0.707, −0.017 [−0.070, +0.033] | 0.890 → 0.897, +0.007 [−0.037, +0.050] | −0.005 [−0.038, +0.028] |
| int1 | ours | 0–299 | 0.720 → 0.767, +0.047 [−0.003, +0.100] | 0.860 → 0.847, −0.013 [−0.060, +0.033] | +0.017 [−0.018, +0.053] |

- Three engine stages were measured: int1 at about 62.5% ≤¼, c10 at 68.0%, and r2 at 72.3%. None moves the RoyaleSim
  score; the point estimates stay within ±0.02.
- The final r2 and the c10 interim differ by +0.002 [−0.011, +0.016] over the 1,800 games.
- **Latency.** Equal-load A/B on 03 (r1 and r2 run at the same time, cases 0–11 against both opponents, 24 games each):
  RoyaleSim game CPU per 1,000 ticks is 17.98 for r1 and 18.81 for r2 (+4.6%, within the plan's 10%).
  - In our engine, CPU per game also includes the Python game simulation. That is ~30% slower with the calibrated rules (measured under different load),
    mostly the Royal Ghost now A*-routing.

## Caveats

- **One bot.** K4S-st with 160-tick balanced/pressure/defense rollouts and the phi leaf. A planner with a learned value
  or longer horizons may be more sensitive to model fidelity.
- **Two opponents.** Only R3a and v1, both policy bots (the RoyaleSim P1 pool's scripted opponents are saturated at
  0.99+). External/human opponents were not tested.
- **The evaluator is not native either.** RoyaleSim is 78.8% ≤¼ faithful. Our calibrated engine (72.3%) is now within
  6.5 pp of it, but the two differ in other ways, so "faithful" means "closer to native", not "closer to RoyaleSim".

Raw logs (127x03, `/mpac/sdicks02/jobs/clasher/bot-calib2-eval/`):

| arms | directories |
|---|---|
| r1 | `r1-rsim`, `r1-rsim-x`, `r1-ours` |
| r2 | `r2-rsim` (0–899), `r2-ours` |
| c10 | `c10-rsim`, `c10-rsim-x`, `c10-ours` |
| int1 | `int1-rsim`, `int1-ours` |
| latency A/B | `lat-r1`, `lat-r2` |
| pooled 0–899 | `all-r1-rsim`, `all-c10-rsim` |

Paired summaries are in `*.paired.txt`. Launchers: `hl.sh RUNTIME ENGINE OUT W [args]` and
`hl2.sh ROOT PINS ENGINE OUT W [args]`.
