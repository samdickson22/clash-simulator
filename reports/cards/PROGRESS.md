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
- 00:20Z Native sweep done: all 66 new cards native==Python (solo+Knight 900 ticks); only C56 IceGolemite diverges
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
| cards-batchA-opus-r1 | Opus | Batch A mechanics fixes in engine-cards (C56 bit-identical); stat fixes → overlay | engine-cards/, reports/cards/batchA/ |
| cards-proxy-v2-sol-r1 | Sol | proxy table v2 per BOT LEAD Sol review (8 findings + weak proxies) | bot/cards/proxy_table.py |
| cards-balance-size-haiku-r1 | Haiku | DONE c76bf1fff: C56 13/56, others 22/66 material vs 16.402.19 | reports/cards/stats/BALANCE-SIZE.md |
| cards-b1-opus-r1 | Opus | Batch B1 troops mechanics (worktree clasher-cards-b1, branch cards/b1) | reports/cards/b1/ |
| cards-b2-opus-r1 | Opus | Batch B2 spells mechanics + Poison-dash/Mirror-bomb native fixes (clasher-cards-b2, cards/b2) | reports/cards/b2/ |
| cards-live16402-opus-r1 | Opus | live16402 overlay generator + pin + gate | bot/cards/balance_overlay.py, reports/cards/live16402/ |

## Definition of done per card
engine native==Python (probe + mixed games) · fidelity PASS vs RoyaleSim (or documented 16.402) · C56 parity gate
unchanged · in r1-cards1 scope · translator mapping (real body under r1-cards1; proxy on r1-total) · perception = LIVE.
- 00:29Z Proxy table b55c3b017 sent (BOT LEAD Sol review pending). Decisions: class-only unknowns not charged to elixir
  (BOT LEAD + translator agree); Barbarian HP stays 691 in r1-cards1 (C56 bit-identity wins; calibration is a separate
  pin decision). Translator hook must rebase on BOT LEAD's revised livefix revealed-set patch. Stats diff 3a3bcaa74.
- 00:44Z Coordinator/BOT LEAD ruling: build `live16402` = r1-cards1 + RoyaleSim 16.402.19 stat overlay for ALL cards
  (C56 included; no bit-identity; gate = 0 crashes + K4L vs R3a/v1 200 cases per pin). Overlay never in git. Calibration
  (15.535-measured) only where RS 15.535==16.402 on that field. Live client = 160402020 (RS table 16.402.19; flag).
  r1-cards1 stays sim-continuity (C56 bit-identical). Proxy v1 NOT approved (Sol review) → v2 in progress; review by a
  fresh instance, not the writer.
- 01:24Z Proxy table approved (3 Sol rounds) and LANDED ON MAIN a382530c9 (temp-index commit). Batch A: 37/42 fidelity
  scenarios PASS (mech+stats), native==Python 42/42, C56 gate queued on 04 (PID 2204895). Batch A ETA to coordinator
  03:30–04:00Z. r1-cards1 roots 600/600, HEADLINE gate on 03; timing probe of non-C56 live-search fallback is top
  priority (scope worker). Sam: official client data allowed (scratch only, hashes). Null's Royale fresh instance
  (LIVE LEAD building) → native fixtures for the 66; never touch sealed AVD ~/.cache/clasher-native-reference
  (until 2026-10-25). Rule: native wins on mechanics; 16.402 stats from RoyaleSim unless Null's is 16.402.
- 01:36Z Fidelity all 66 (2fcaa794f): PASS 4 (MegaMinion, Pekka, SkeletonKing, Mirror) / DIFF 62, grouped: stats(15) →
  live16402 overlay; spawning/formation, spells, special mechanics, attack/targeting timing, death releases → Opus
  batches. Native mixed-deck diff: 600 games, 0 panics; new-card native≠Python: BossBandit dash ×MightyMiner/Monk (4),
  ElectroDragon chain hook (4), MegaKnight splash discard (2), Mirror×SkeletonBalloon level (2), Poison during dash (2),
  IceSpirit×BossBandit interrupt (1); C56-in-mixed: InfernoTower retarget (8), Xbow clock (5), Valkyrie (1);
  IceGolemite 75 = harness alias (IceGolemite vs IceGolem name) artifact.
  NEXT after Batch A commit: native-parity follow-ups → Batch A worker; then parallel Opus workers in separate worktrees
  per mechanic group (spells / spawning+death / special / timing), each with its own C56 gate.
- 01:38Z Batch A WIP committed 7720915a8 (gate on 04: fixtures 386/577 at 01:38Z; I watch it and wake the
  worker — its turn ended). B1/B2 worktrees from 7720915a8. Timing cause found (side tables uncut → >1 MiB config
  re-shipped per decision); fix = fc_cut side tables + content-hash pool cache (scope worker). 03/04/08 busy with LIVE
  compositing 12–24 h → workers use cpu_job N≤8.
- 01:50Z RESUME after the Claude usage stop (~01:45Z). Resumed in place: scope, b1, b2 (Opus). live16402 kept running.
  Batch A gate r2 on 04 PID 2388512 (native 1923619e, serialization fix; Batch A edits after 7720915a8 uncommitted in
  this worktree), watched by the lead; wake cards-batchA-opus-r1 only for code fixes. Routing now: non-coding (gates,
  sweeps, reviews, bookkeeping) → Sol; engine code → Opus; narrow → Haiku. No duplicate threads found.
