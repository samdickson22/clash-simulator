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

## Running (2026-10-14 04:40Z)

- **HEADLINE-v2 external opponents:** K4S-b64 vs rgym-{patient,push,defend,first-affordable} in RoyaleSim, on 04.
  Out `bot-headline-v2-rsim-r1`, launch script `bot-headline-v2-rsim-r1.sh` (sets `ROYALEGYM_SRC`).
- **`bot-lead-external-opponents-r1`** (Opus): RoyaleLearn/RoyaleImitate baselines plus a RoyaleLearn-trained
  policy on our decks. Writes `reports/bot/external-opponents/` and `bot/players/rext_*`.
- **`bot-lead-exit-pipeline-r1`** (Opus): ExIt on 08. Writes `bot/exit/` and `reports/bot/exit/`.
- **`bot-lead-search-scaling-r1`** (Opus): on 03. Writes `bot/search/` and `reports/bot/search-scaling/`.
- **`bot-lead-calib-batch1-r1`** (Opus): engine calibration batch 1, fidelity-gated. Writes
  `reports/bot/calibration/`.
- **Daily headline:** T3 scheduled task at 06:00 local (13:00Z).

## Next

1. HEADLINE-v2 numbers, then report.
2. Integrate ExIt and search-scaling winners into the best bot, and re-headline.
3. Runtime r2 with the calibrated engine.
