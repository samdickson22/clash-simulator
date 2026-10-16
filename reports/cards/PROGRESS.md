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
- 00:50Z Native sweep done: all 66 new cards native==Python (solo+Knight 900 ticks); only C56 IceGolemite diverges
  (t=307, known). Python baseline committed as engine-cards/py (7e64d8b93).
- Fidelity group 1 (vs RoyaleSim 16.402): PASS MegaMinion, Pekka; DIFF 12 (stats: Brawler HP 1080/1121, Bomber dmg
  225/212, Barbarian HP 691/716 [shared with C56 BarbLog]; spawner first-spawn timing Tombstone/BarbarianHut; hit
  timing SpearGoblins/SkeletonDragons/Mortar/DartBarrell; Guards speed).

## Workers (taskIds: node:delegated-task:command%3Amcp%3A9a073ec3-0825-4649-8b7b-6d04c9b33067%3Adelegate-task%3A<id>)
| id | model | job | output |
|---|---|---|---|
| cards-fidelity-sol-r1 | Sol | RoyaleSim scenario fidelity, all 66 | reports/cards/fidelity/ |
| cards-statsdiff-haiku-r1 | Haiku | gamedata vs 16.402 stat diff | reports/cards/stats/ |
| cards-runtime-scope-opus-r1 | Opus | full-pool scope, r1-cards1 assembler, parity + K4L no-crash gate, baked-in C56 inventory | bot/players/runtime.py, bot/cards/, reports/cards/runtime/ |
| cards-proxy-haiku-r1 | Haiku | proxy table (named + class-only) | bot/cards/proxy_table.py |
| cards-native-diff-sol-r1 | Sol | ≥600 mixed-deck native-vs-Python games | reports/cards/native-diff/ |
| cards-batchA-opus-r1 | Opus | Batch A fidelity fixes in engine-cards (C56 bit-identical) | engine-cards/, reports/cards/batchA/ |

## Definition of done per card
engine native==Python (probe + mixed games) · fidelity PASS vs RoyaleSim (or documented 16.402) · C56 parity gate
unchanged · in r1-cards1 scope · translator mapping (real body under r1-cards1; proxy on r1-total) · perception = LIVE.
