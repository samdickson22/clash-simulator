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

## Running (2026-10-14 04:10Z)

- **`bot-lead-rsim-adapter-r1`** (Opus): our bots in RoyaleSim. Writes `bot/players/royalesim_*` and
  `reports/bot/rsim-adapter/`.
- **`bot-lead-exit-pipeline-r1`** (Opus): ExIt on 08. Writes `bot/exit/` and `reports/bot/exit/`; job dirs
  `bot-exit-*`.
- **`bot-lead-div-{goblinstein,ghost,huts,swarms,towers,miner}-r1`** (Haiku): our-engine divergence notes. Write
  `reports/bot/divergence/`; scratch `bot-div/` on 03.
- **v1-τ0.1387 arm:** on 04, `bot-gate-r2.sh`, out `bot-gate-r1`.
- **Hosts:** 03 (CPU), 04 (A6000), 08 (A6000, from COORDINATOR 19693dce; never `v4-b-20261012-r1` or `t1-*`).

## Next

1. RoyaleSim headline, then the step-4 engine decision.
2. Daily headline schedule (T3 `schedule_task`).
3. Train at scale on the chosen engine.
