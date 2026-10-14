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

## Running

- Delegated Opus task `bot-lead-inventory-r1` (bot inventory + `bot/players/` adapters). It writes
  `reports/bot/inventory/`.

## Next

1. Step 2 speed: same host (03), single core, same decks/seeds; ticks/s and state clone/save cost for ours (Python
   and Rust) and RoyaleSim.
2. Step 3 strength baseline: fixed opponent pool plus deck/seed protocol; headline in both engines; greedy vs sampled
   play/wait for the student.
3. Step 4 engine decision, then train at scale.
