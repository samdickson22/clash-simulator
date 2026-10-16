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
| cards-batchA-gate-sol-r1 | Sol | shepherd Batch A C56 gate on 04 (PGID 2388512), fill RESULTS §6, triage spec on FAIL | reports/cards/batchA/ |
| cards-c1-spec-sol-r1 | Sol | Batch C specs: attack/targeting/dash cards + 4 native≠Python bugs | reports/cards/specs/C1-SPECS.md |
| cards-c2-spec-sol-r1 | Sol | Batch C specs: special mechanics, death releases, stats-only confirmations | reports/cards/specs/C2-SPECS.md |
| cards-b2-gate-sol-r1 | Sol | B2 C56 gate relaunch on 04 + RESULTS; wakes Opus B2 on FAIL | clasher-cards-b2 reports/cards/b2/ |
| cards-scope-gate-sol-r1 | Sol | r1-cards1 policy gate + noncore final (08) → SCOPE.md; wakes Opus scope on FAIL | reports/cards/runtime/ |
| cards-batchA-review-r1 | Sol | review Batch A engine diff 7e64d8b93..9eed63029 | (verdict) |
| cards-r1cards2-sol-r1 | Sol | assemble r1-cards2 (scope+Batch A, native 1923619e) + live16402b; gates | reports/cards/r1-cards2/ |
| cards-runtime-review-r1 | Sol | review runtime/overlay code 0874da215 | (verdict) |
| cards-nulls-fixtures-sol-r1 | Sol | Null's Royale (15.535!) native fixtures: offline prep, then LIVE-granted slots | reports/cards/nulls/ |
| cards-release-roots-sol-r1 | Sol | released read-only roots on 03/04/08 (r1-cards1 done; r1-cards2 + live16402b in progress) | reports/cards/release/ |
| cards-c1-opus-r1 (task prefix 6b4c485c) | Opus | Batch C1 attack/targeting/dash + 4 native≠Python bugs (clasher-cards-c1, cards/c1) | reports/cards/c1/ |
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
- 02:16Z Sam: 'use some sol'. Non-coding moved to Sol (gate shepherd, C1/C2 spec writers). Cannon stall = live
  own-deck tracker out of sync (driver deck still Skeletons), not engine scope: Cannon + whole live deck are C56.
- 02:20Z **Batch A C56 gate PASS** (02:18Z: fixtures 577/577, rust-only 577/577, roots 600/600; native 1923619e;
  commit 9eed63029). Reported to coordinator. Runtime/overlay code committed 0874da215. Opus owners (scope, B2,
  Batch A, live16402) idle after handoff; B1 continues on Opus. Sol shepherds gates/reviews/assembly (Sam: Opus owns,
  Sol = workhorse incl. tedious code). Merge to main after Sol reviews of Batch A engine + runtime code.
- 02:25Z Batch A engine review REJECT: Freeze inheritance after first update in Python vs before drain in Rust
  (death_effects.py:285 / lib.rs:3519) + wave siblings visible in first update → Opus Batch A owner fixing, then re-gate.
  r1-cards2 assembly holding long gates for the new sha. BOT LEAD: (1) widen R.bots in r1-cards1 (Opus scope owner
  assigned); live switch ships as bundle r1-cards1 + their extended nets + open-world belief; (2) full-pool retrain
  generates under **live16402 on r1-cards2** → tell BOT LEAD when that opt-in pin is ready (start signal).
  Null's slots: reference AVD, client 15.535.13 → mechanics only; slot 1–2 h via LIVE LEAD.
- 02:36Z Batch A review r2 REJECT (same class: spell-killed spawner → death-spawn first update vs spell status pass,
  Python synchronous, Rust after direct_spell). Opus owner told to close the CLASS (audit table of all mid-phase spawn
  paths + probe per row), relaunch gate. Gate r3 (5f07238c) to be killed; r1-cards2/live16402b gates continue on
  5f07238c, final native swapped in with smoke + K4L sha check.
- 02:37Z Runtime code review (0874da215) REJECT: fc_cut drops Mirror level12:<card> payloads (BLOCKER), assembler staging
  can delete BASE (BLOCKER), symlink-follow in rsync overlay, lopp_fast fc stale base config, r1-cards1 wrong-root
  gamedata pin. Split: Opus scope owner (fc_cut/lopp_fast/runtime.py + R.bots), Sol r1-cards2 worker (assemblers +
  tests). Then fresh Sol review round 2 before main.
- 03:08Z Landed: d6c347ac1 (R.bots widened + runtime review fixes; gate4 K4L 12/12, mirror 80/80, own deck w/ new cards 0
  errors), f97b2052e/a71a7643a (assembler safety, Sol), 878d5f459 (Batch A boundary-class fix, native de11f124, 21
  paths × 2 seats audited). Running: Batch A gate r4 (04, PGID 3671549; Sol shepherd), Batch A review r3, runtime review
  r2 (fresh Sol), r1-cards2/live16402b assembly+gates (Sol; swap to final native/runtime when gates finish).
- 03:28Z **MERGED cards/lead → main 0ee42633e**: Batch A (gate run 4 PASS on native de11f124; review r3 APPROVE),
  r1-cards1 (R.bots widened; runtime review r3 APPROVE after lead fix 99b26b995), live16402 tooling. Told BOT LEAD +
  coordinator. Pending: live16402b final (Sol r1cards2 worker) = BOT LEAD generation start signal.
- 06:47Z RESUME after the 2nd usage stop (~04:00Z). live16402b FINAL (native de11f124; smoke 2/2, K4L 12/12, totality
  0 panics; e545eb6bd) → BOT LEAD start signal sent; generating on 08 dev root. r1-cards1 released on 03/04/08; release
  worker releasing r1-cards2 + live16402b (send 03/04 receipts to BOT LEAD). B2-fix C56 gate PASS (577/600) → B2 Opus
  merging onto cards/lead (sync first-update design) + re-gate. C1/C2 specs committed b16716481; C1 Opus started.
  Null's worker READY FOR SLOT 120 min → requested from LIVE LEAD. B1 resumed by coordinator.
- 06:53Z r1-cards2 + live16402b RELEASED read-only on 03/04/08 (receipts c02c5a58c; recomputed by lead); BOT LEAD told.
  B2 merged onto cards/lead (9e881f00a/27ef53e5c, native 466aeba3; parity 28/28 + 42/42 + 42/42); b2-merge C56 gate on
  04 PID 2123864 (Sol shepherd cards-b2merge-gate-sol) + fresh Sol review cards-b2-review-r1 (task prefix 6b4c485c).
  Null's 120-min slot GO from LIVE LEAD; wake cards-nulls-fixtures-sol-r1 when the Null's owner says probe idle.
- 07:07Z B2 review r1 REJECT (scope_targets misses dash-travel guard → Curse/Vines/Void on dashing Bandit native-only;
  Clone slides ignore bounds/terrain) → Opus B2 fixing + class audit, b2-merge gate killed, b2-merge2 to follow.
  BOT LEAD bug: c56_scripted.ranked_actions float(None) building_damage (Freeze) → Sol fix + 122-card None-stat audit +
  live16402b-r2/r1-cards2-r2 release (cards-nonestat-fix-sol-r1). main ← cards/lead merged again f75889654.
- 07:53Z None-stat fix 43d688f85 (Freeze building_damage, 3M HP; 4 sites; 122-card probe 55,834 checks 0 exc; C56 K4L 12/12)
  → live16402b-r2 / r1-cards2-r2 RELEASED 03/04/08 (receipts recomputed by lead); BOT LEAD told. Fresh Sol review running.
- 08:06Z None-stat fix review APPROVE → main 57941b370. BOT LEAD: 'no C56 public model template: BarbarianRageDamage/AreaEffect'
  (Lumberjack, ~2/1000) → Sol worker cards-template-fix-sol-r1: class probe of all reachable objects × lookup tables,
  generic fix, r3 roots (live16402b-r3 / r1-cards2-r3).
