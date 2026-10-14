# Step 3: strength baseline (exploration)

2026-10-14, BOT LEAD. The protocol is HEADLINE-v1 (`reports/bot/HEADLINE.md`): a fixed pool and a fresh seed bank,
300 cases per opponent, the same cases for every candidate and opponent. Win counts 1, draw 0.5. The 95% CIs are
bootstrapped over games; paired differences are on the same case indices.

## Our engine (Python C56, X4S-pinned runtime r1)

| candidate | vs v1 | vs R3a | vs scripted-balanced | vs scripted-pressure | pool P1 |
|---|---|---|---|---|---|
| **K4S-b64** (search with R3a default, deterministic 64-rollout budget) | 0.830 [0.787, 0.870] | 0.633 [0.580, 0.687] | 0.997 | 0.996 | **0.864 [0.847, 0.882]** |
| R3a student alone (calibrated gate) | 0.743 [0.693, 0.790] | — | 0.923 | 0.937 | 0.868* [0.847, 0.889] |
| R3a with the gate **sampled** | 0.500 [0.443, 0.557] | — | 0.667 | 0.740 | 0.636* [0.604, 0.667] |
| v1 (human prior, T=1 sampling) | 0.487 (self-play) | — | 0.497 | 0.472 | 0.485* [0.452, 0.517] |

\* These pool means cover 3 opponents (v1 and the two scripted bots), not P1. They are not comparable with K4S's
4-opponent pool.

- **The search beats the student head-to-head.** K4S beats R3a 0.633, and beats v1 0.830 against R3a's 0.743. The
  search's edge over its own default policy is moderate.
- **The scripted opponents are saturated** for both K4S and R3a, so they only check for regressions. The pool should
  gain stronger members, such as K4S self-play and future students, as the bots improve. A pool change will be
  versioned (HEADLINE-v2), never edited in place.
- **Cost:** K4S-b64 takes 44–84 CPU s per game.

## ClashAI's lesson: greedy vs sampled play/wait gate (student R3a)

Paired R3a-sampled − R3a (calibrated threshold gate) on the same 300 cases:

| opponent | sampled − threshold |
|---|---|
| v1 | **−0.243 [−0.307, −0.180]** |
| scripted-balanced | −0.257 [−0.313, −0.203] |
| scripted-pressure | −0.197 [−0.247, −0.147] |

- The sampled gate plays **more** cards: 44.7–51.2 per game against 36.9–37.9. This is the overspending mechanism
  ClashAI saw live, and it matches their ~−20 pp.
- **Rule for us:** every deployed policy uses a calibrated play threshold. Never sample the gate.
- The argmax of v1's gate at each poll **never plays** (P(play) ≥ 0.5 on 0.01% of polls). So "greedy" must mean a
  threshold calibrated to the play rate.
  - Over 700,541 v1 polls the mean P(play) is 0.0436. The matching threshold is τ = 0.1387.
  - **The v1-τ arm (threshold gate, argmax card and tile) collapses.** It plays only 6.9–13.9 cards per game,
    against 26–32 for sampled v1. Paired against sampled v1 on the same cases:

    | opponent | v1-τ − sampled v1 |
    |---|---|
    | v1 | −0.453 [−0.513, −0.397] |
    | scripted-balanced | −0.440 |
    | scripted-pressure | −0.358 |

    A threshold calibrated on the sampled policy's visited states does not keep the play rate once decoding is
    greedy, because the greedy policy visits different states.
  - **Lesson:** calibrate thresholds **on-policy**, iterating on the greedy policy's own trajectories, or use a
    play-rate controller. R3a's threshold already behaves well (37–38 plays per game).

## RoyaleSim (0.1.34, 15.535.29 rules; our bots via `bot/players/royalesim_*`, search still plans on our engine)

| candidate | vs v1 | vs R3a | vs scripted-balanced | vs scripted-pressure | pool P1 |
|---|---|---|---|---|---|
| K4S-b64 | 0.797 [0.750, 0.840] | 0.617 [0.563, 0.673] | 0.993 | 0.997 | **0.851 [0.833, 0.869]** |

Paired RoyaleSim − ours on the same 300 cases:
- vs v1: −0.033 [−0.093, +0.023]
- vs R3a: −0.017 [−0.077, +0.047]
- vs scripted-balanced: −0.003
- vs scripted-pressure: 0.000

Planner model mismatch costs little at this strength. The engine decision is in `DECISION-ENGINE.md`.

Raw logs:
- `/mpac/sdicks02/jobs/clasher/bot-headline-rsim-r1/` on 03 (RoyaleSim);
- `/mpac/sdicks02/jobs/clasher/bot-headline-r1/` on 03;
- `/mpac/sdicks02/jobs/clasher/bot-gate-r1/` on 04, including `v1-pplay.jsonl`.

Summaries: `python -m bot.eval.summarize DIR [--paired A,B]`.
