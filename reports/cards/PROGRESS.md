# CARD LEAD progress (resumable)

Task: full current card pool in the stack (engine / tests / translator / perception), live-priority first.
Lead thread: `clasher-card-lead-20261016-r1`. Coordinator `0523ae6f-baa3-4d4e-b233-b392671670db`.
Worktree `/mpac/sdicks02/repos/clasher-cards`, branch `cards/lead`. Older per-card `*.md` audits in this dir are
from the retired Python-only era (e60edb010); they are not this project's status. Status lives in `COVERAGE.md`.

## Key facts (verified 2026-10-16)
- Pool = gamedata.json `spells` with `notVisible` unset, minus support cards: **122 cards**; C56 ⊂ pool; **66 missing**
  (`reports/cards/tools/pool.py`).
- Live pin r1-total native `681b5f2c` = 127x03 `jobs/clasher/e1-20261009-r1/native-source-v2` + NATIVE-TOTAL.diff.
  `engine-cards/` here is that tree (commit d9e9e075e); rebuilt on 08 it reproduces `681b5f2c` byte for byte.
  Repo `engine-rs/` is NOT the pin (has calibration batches 1+2).
- The native imports card config from the **Python engine** (`differential.config(cards)`), in the runtime from
  `clasher-bot-runtime/r1/src`. Native code is data-driven (≈15 name-specific branches).
- **Python engine already plays all 122 cards** (probe_engines.py; 5 "not deployed" were probe placement only).
- Observation vocab (ContractV5ObservationBuilder.token_id) already has tokens for every card and body
  (GoblinBrawler 128, GoblinCage 129, ...). The policy has never trained on non-C56 tokens.
- Runtime card scope = `c56_controller.CARDS` (config + metadata). Extending it is the main runtime change; native
  may not need changes for most cards (sweep below).

## Probes / hosts
- 08: `/mpac/sdicks02/jobs/clasher/cards/` — `root/engine-rs` (= engine-cards), `root/src` → runtime r1 src,
  `out-total/` (681b5f2c build), `tools/`. Native-vs-Python sweep: `probe-native.{log,json}`.
- 05: `probe-python.json` in `/mpac/sdicks02/jobs/clasher/cards/`.

## Plan (batches)
See COVERAGE.md "Batch plan".

## Log
- 2026-10-16 00:05Z start. LIVE LEAD inventory part 1 = `reports/live/loop/ARENA-CARDS.md` (main); part 2
  `reports/live/loop/opponent-decks.jsonl` pending. BOT LEAD rules: CPU on 03/04/08 via
  `clasher-bot/bot/exit/cpu_job.sh`, cargo nice ≤32 jobs, parity gate tools `reports/bot/learned-opponent/native-total-tools/`,
  new pin set `r1-cards1` (never change r1/r1-total), proxy table + hook diff to BOT LEAD before ship.
