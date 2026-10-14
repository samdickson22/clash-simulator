# BOT LEAD progress (exploration)

Mandate: the strongest bot, judged by a trusted win rate. Coordinator ruling: COORDINATOR 91e2bb67 (exploration
tier). Report to coordinator thread 0523ae6f.

## Layout

- **Worktree:** `/mpac/sdicks02/repos/clasher-bot` on 05, branch `bot/lead`.
  - Code lives in `bot/`, reports in `reports/bot/`.
  - The tree is synced to 03 and 04 with `rsync -a bot/ HOST:/mpac/sdicks02/repos/clasher-bot/bot/`.
- **Envs on 03:**
  - `/mpac/sdicks02/repos/clasher-bot/.venv` (py3.12, `uv sync`, plus royalesim 0.1.34);
  - `/mpac/sdicks02/repos/clasher-bot-rsim/.venv` (`royalegym[all]` 0.1.24);
  - upstream clones (read-only reference) in `/mpac/sdicks02/repos/clasher-bot-rsim/upstream/{RoyaleSim,RoyaleGym}`.
  - Source `bot/env.sh` for the cargo and uv cache paths.
- **Data on 03:** `/mpac/sdicks02/repos/clasher-bot-data/t1-trainval/` holds the 577 train+val match dirs (no
  video), copied read-only from 01. `t1-split.json` is the registered split.
- **Job dirs:** `/mpac/sdicks02/jobs/clasher/bot-*` on 03 and 04.

## Done

- **2026-10-14 ~03:15Z, step 1 fidelity:** `reports/bot/FIDELITY.md`. Results are in `bot-fid-r2` on 03.
  - No towers, within ¼ tile: RoyaleSim 15.535 **78.8%**, ours **51.4%**, RoyaleSim 16.402 72.1%.
  - Paired: +26.1 pp for RoyaleSim, better in 530/577 fixtures.

- **2026-10-14 ~03:25Z, step 2 speed:** `reports/bot/SPEED.md`.
  - Rust core 34.3k ticks/s with a 5 µs clone; RoyaleSim 30.8k (16.402 rules) or 14.2k (15.535 rules) with a ~5 ms
    save+load branch; Python 521.

- **2026-10-14 ~03:45Z, RoyaleSim clone spike:** `reports/bot/RSIM-CLONE-SPIKE.md`.
  - `restore_from` takes 9.8 µs. The fork is byte-identical to the PyPI wheel on fidelity.
- **2026-10-14 ~04:00Z, step 3 (our engine):** `reports/bot/STRENGTH.md` and `HEADLINE.md`.
  - K4S-b64 pool score 0.864 [0.847, 0.882].
  - Sampling the gate costs −24 pp; v1's calibrated threshold is τ = 0.1387.

- **2026-10-14 ~04:35Z:**
  - RoyaleSim headline: K4S-b64 pool 0.851.
  - Step 4 decision ACCEPTED by the coordinator: plan and train on our Rust core, trusted headline in RoyaleSim,
    calibrate ours behind the 577-fixture gate (`DECISION-ENGINE.md`).
- The v1-τ arm collapsed (−45 pp): thresholds must be calibrated on-policy.

- **2026-10-14 afternoon:**
  - The engine calibration batch 1+2 is merged into main (0ecdd97d, tag `engine-r1`). Fidelity is 72.3/74.5%; parity 574/577.
  - The planner A/B on r2 vs r1 is null. Learned leaf value: negative. Candidate round 2: R3a top-16 confirmed.
  - **Best bot: K4C-r16** (fresh-bank +0.021 over K4S-st). RoyaleSim P1 0.921, v3 0.924.
  - **Best student: it5s2** (ExIt; 0.883 vs v1). HEADLINE-v3 adds the human-clone external `rext-bc`.

## Running (2026-10-14 17:59Z)

- **ExIt iteration 6+ owner** (`bot-lead-exit-it6-r1`, Opus) on 01/04/08.
  - CPU feeders: `bot/exit/cpu_feeder.sh`, state in `<J>/cpu-feed/`.
  - GPU queues with keep-alives: `<J>/gpuq/`.
  - The teacher is being switched to K4C-r16.
  - J1=/mpac/sdicks02/jobs/clasher/bot-exit-r1-01, J4=…-04, J8=/mpac/sdicks02/jobs/clasher/bot-exit-r1.
- **Daily headline:** T3 scheduled task at 13:00Z (v1 + v3).
- **Hosts:** 01, 03, 04, 08 (05 light only).
  - Exclusions: 01 PGID 516161, x4s4-onpolicy, t1-*; 08 v4-b-20261012-r1.

## Next

1. ExIt: next best student, both engines plus rext-bc. Feeders switch to on-policy behaviour.
2. Search scorer: the scripted opponent models inside rollouts. These are the remaining lever after the candidate and
   leaf nulls.
3. Re-headline the best bot when the code changes. Live play is a separate, later authorization.
