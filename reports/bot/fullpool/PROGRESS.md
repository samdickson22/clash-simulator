# Full-pool learned components: progress (resumable)

Owner: BOT LEAD's full-pool worker (Opus writes code; game runs, long waits and data checks go to GPT-6.1-Sol
sub-workers via delegate_task, target codex/gpt-6.1-sol, reasoningEffort high). Rule (Sam, 10-16): nothing is
sealed; results are reported as soon as they exist. Docs: README.md (how to use), INVENTORY.md (C56 sites + fixes).

## State at 2026-10-16T02:23:11Z (code at origin/main 2c7966da0 + this commit)

**Worktree** 05:/mpac/sdicks02/repos/clasher-bot-fullpool, branch bot/fullpool (tracks origin/main; commits go to
main via a temp index + /mpac/sdicks02/cc/tools/bin/clasher-secret-scan). `.venv` is a symlink to
/mpac/sdicks02/repos/clasher-bot/.venv (python 3.12). Always PYTHONHASHSEED=0.

**Deliverables: all six done (exploration tier).**

| # | deliverable | files | status |
|---|---|---|---|
| 1 | inventory | reports/bot/fullpool/INVENTORY.md | done |
| 2 | vocab/embedding extension + converter + parity | bot/fullpool/extend.py, parity.py, models.py; bot/search/lopp_feat.py (Wv_x), lopp_train.py (--init) | done, parity PASS |
| 3 | deck sampler | bot/fullpool/decks.py, cards.py; reports/bot/fullpool/freq/ (frozen LIVE tables) | done |
| 4 | generation/eval options | bot/fullpool/banks.py; bot/eval/headline.py, bot/exit/generate.py (--decks/--bank/--belief-prior), bot/rl/actor.py (BOT_RL_DECKS), bot/search/lopp_record.py (--decks); belief: bot/fullpool/belief.py hooked in bot/players/search.py + bot/search/players.py | done |
| 5 | bank definitions | bot/fullpool/banks.py BANKS; README.md section 4 | done |
| 6 | smoke under r1-cards1 | bot/fullpool/smoke.sh, smoke_summary.py | done on the CARD LEAD's DEV root (all PASS, below); rerun on the released root when it exists |

**Results**
- Policy parity (05, 600 roots from 10 recorded C56 games; all 56 cards): RL r5 v10 (row and input init), R3a and
  v1 have 0/600 roots with any output or decision difference → PASS. K4L parity (pool, pool2L; 1000 recorded
  native views; row-wise and batched): 0 mismatches → PASS.
- Smoke, 08, DEV root 08:/mpac/sdicks02/jobs/clasher/cards/runtime/r1-cards1-dev (native 681b5f2c), pins
  r1-cards1, out 08:/mpac/sdicks02/jobs/clasher/bot-fullpool/smoke1 (02:04–02:22Z):
  - stu, extended RL r5 v10 vs R3a on FP-DEV: 40 games, 0 errors, score 0.65, 38 distinct new cards.
  - k4l, K4L-R-gs-mpoolfp vs R3a on FPO-DEV: 40 games, 0 errors, 0 lopp native failures, score 0.90, 28 new
    cards.
  - c56s, original vs extended student on HEADLINE x4s cases 0–19: 20/20 identical command hashes.
  - c56k, K4L mpool vs mpoolfp, cases 0–5: 6/6 identical command hashes.
  - gen, bot.exit.generate with the extended student and the K4S-b64 teacher on fullpool own=c56: 2 games, 0
    errors, 701 labelled rows.

  The 40-game scores are dev-bank smoke numbers, not claims.

**Extended models (not in git)**: 05 and 08 /mpac/sdicks02/jobs/clasher/bot-fullpool/ext/{rl5-v10-fp.pt
a6565cab…, rl5-v10-fp-input.pt, R3a-fp.pt ce7b0ea4…, main02-fp.pt 69313468…} (05 only for the last three; each with
.fullpool.json receipt), lopp-fp/{pool,pool2,pool2L,R3a,v1}fp.npz (+ originals); meta tokens meta/r1-cards1-meta.json.
Recorded parity roots 05 parity/roots-c56.pt.

**Run trees on hosts**: 03 and 08 /mpac/sdicks02/jobs/clasher/bot-fullpool/repo = bot/ of the base commit + the
CARD LEAD's UNCOMMITTED bot/players/runtime.py, bot/search/lopp_fast.py, bot/cards/{scope,fc_cut,balance_overlay}.py
from 05:/mpac/sdicks02/repos/clasher-cards (sha list in repo/OVERLAY-SHA256.txt). Rebuild the stage on 05 at
/mpac/sdicks02/jobs/clasher/bot-fullpool/repo-stage (commands in the log below), then rsync to the host. Once
r1-cards1 is on main, the overlay is no longer needed.

**Running jobs: none** (dry-run PGID 2694058 stopped by me; smoke PGID 2784725 finished; no cpu_job leases held).

**Tests**
- `cd /mpac/sdicks02/repos/clasher-bot-fullpool && PYTHONHASHSEED=0 .venv/bin/python -m pytest -q -p no:cacheprovider bot/fullpool/test_fullpool.py` (10 pass)
- policy parity: `PYTHONPATH=$PWD bot/players/run.sh -m bot.fullpool.parity policy --roots J/parity/roots-c56.pt --pair J/ckpt/policy-00010.pt J/ext/rl5-v10-fp.pt` (`--loader v1` for main02), J=/mpac/sdicks02/jobs/clasher/bot-fullpool
- K4L parity: `PYTHONHASHSEED=0 .venv/bin/python -m bot.fullpool.parity lopp --rec J/lopp-rec/rec-000.jsonl.gz --rows 1000 --pair J/lopp-models/pool.npz J/lopp-fp/poolfp.npz`
- smoke (on a host run tree): `W=12 N=40 bot/detach.sh LOG RECEIPT bot/exit/cpu_job.sh 14 bot/fullpool/smoke.sh OUT`, then `python -m bot.fullpool.smoke_summary OUT`

**Next (what is needed to start full-pool generation)**
1. CARD LEAD releases r1-cards1: the real root under clasher-bot-runtime/ and runtime.py/scope.py/fc_cut.py on main.
   Then rebase, drop the overlay, and rerun smoke.sh (all arms) on the released root (a Sol slice).
2. Search seats must hold C56 decks until R.bots is widened (CARD LEAD): generation uses `--decks …:own=c56`, i.e.
   `--bank FP-TRAIN1` with own=c56, or `--decks fullpool:11433651:freq=b53b02a1fde4,own=c56`. Policy-only RL self-play
   can use both full-pool decks (BOT_RL_DECKS=fullpool:11433651:freq=b53b02a1fde4; league games vs K4C-r16 get a C56
   opponent deck automatically).
3. Start from the extended checkpoints (RL: point policies/LATEST at rl5-v10-fp.pt). K4L retrain: lopp_record
   --decks …:own=c56, then lopp_train --init poolfp.npz.
4. LIVE refreshes arena-card-freq.json: run `python -m bot.fullpool.decks --refresh` and move FREQ. Banks keep
   their frozen freq.

## Log
- 2026-10-16T01:30:51Z start. Read: CARD LEAD SCOPE.md/INVENTORY.md (clasher-cards worktree, uncommitted bot/cards/scope.py,
  runtime.py pin r1-cards1), proxy_table, student/policy/RL/K4L code. Key facts: policy nets already have a 360-token
  vocab covering all 122 cards (non-C56 rows untrained); K4L .npz vocab = 57 (pad + C56 meta tokens); belief prior =
  C56 human catalog (closed world). Arena freq (LIVE, origin/main 70b27ec7) received.
- 01:44Z–01:49Z stopped (Claude usage limit; resumed, nothing was running, no leases).
- 2026-10-16T01:55:45Z code: bot/fullpool/{cards,decks,belief,banks,extend,models,parity,test_fullpool}.py; hooks in
  bot/eval/headline.py, bot/exit/generate.py, bot/rl/actor.py (--decks / --bank / BOT_RL_DECKS, default x4s
  unchanged), bot/players/search.py + bot/search/players.py (belief prior via bot.fullpool.belief.planner_belief;
  default = rt.PRIOR + frozen Belief), bot/search/lopp_feat.py (appended Wv_x block). Unit tests 9/9 pass.
- Parity, policy nets (05, 600 C56 roots sampled from 12,477 recorded single_features inputs of 10 C56 games:
  4 HEADLINE x4s cases + 6 human-catalog cover-deck games, all 56 cards; 86 distinct token ids):
  RL r5 v10 (init row and init input), R3a, v1: 0/600 roots with any output-tensor difference, 0 decision
  differences, recorded ids ∩ rewritten rows = ∅ → **PASS** (05 jobs/.../parity/policy-*.log).
  Extended: rl5-v10-fp.pt a6565cab…, R3a-fp.pt ce7b0ea4…, main02-fp.pt 69313468… (90 rows each).
- Parity, K4L (.npz, 05): pool/pool2L vs poolfp/pool2Lfp on 1000 recorded native public views (03 bot-lopp-rec
  rec-000/001): features, card index, trunk, gate, base logits, hand logits, argmax, tile logits all 0 mismatches,
  row-wise and batched → **PASS**. Meta tokens from the r1-cards1 dev root on 03 (121 cards).
  poolfp.npz faf6efbe…, pool2fp e202b0ff…, pool2Lfp 19b9def8…, R3afp 7b894d3e…, v1fp 04828a3a….
- 03 run tree: 03:/mpac/sdicks02/jobs/clasher/bot-fullpool/repo = my bot/ + the CARD LEAD's UNCOMMITTED
  runtime.py/lopp_fast.py/scope.py/fc_cut.py/balance_overlay.py (sha list in repo/OVERLAY-SHA256.txt); runtime root =
  CARD LEAD dev root 03:jobs/clasher/cards/runtime/r1-cards1-dev (read-only use).
- 01:57Z–02:03Z dry run on 08 (old freq pin 36bfa0cf, N=2): stu 2/2 games 0 errors (extended RL r5 v10 vs R3a,
  full-pool decks, ~50 s/game); k4l 2/2 games 0 errors (K4L-R-gs-mpoolfp, own C56 deck vs full-pool R3a, ~67 s).
- 2026-10-16T02:03:46Z LIVE refreshed arena-card-freq.json (e7beb00f, sha b53b02a1…: GS 12, BP 21, BB 8). Default FREQ pin moved;
  frozen copies in reports/bot/fullpool/freq/ (36bfa0cf…, b53b02a1…) selectable with ':freq=<sha12>'; every named
  bank pins freq=b53b02a1fde4; 'python -m bot.fullpool.decks --refresh' freezes a new table and prints the pin.
  Arena pooling now weights n_a·0.5^(A−a) (current arena counts most). Sampler: 95.9% decks with ≥1 new card,
  2.32 new/deck, all 121 cards seen. Also: lopp_train --init (fine-tune from an extended .npz, vocab order kept),
  lopp_record --decks; INVENTORY.md, README.md, smoke.sh, smoke_summary.py. Unit tests 10/10.
- 02:04–02:22Z full smoke on 08 (results in the state block). 2026-10-16T02:23:11Z handoff requested then cancelled by BOT LEAD
  (Sam: Opus keeps owning; non-coding slices go to Sol sub-workers). PROGRESS rewritten with a full state block.
- 2026-10-16T02:28:57Z BOT LEAD decision: train under live16402 (r1-cards2). PLAN.md written (ExIt G1 with a K4C-r16 teacher, 4,000
  games, ~1.5 M labels; F1 fit from rl5-v10-fp + the C56 corpus 1:1; R11 RL on GPU later; K4L K1 recording 2,400
  games + KF1 refit; CPU-first compute table; Sol slices S1–S7). smoke.sh takes PINS=<pin set>. Sol S1 delegated
  (smoke rerun on r1-cards1 once on main; clientRequestId fullpool-smoke-r1cards1-r1).
- 2026-10-16T02:34:47Z launch kit bot/fullpool/run/{env,stage,preflight,g1,k1,pack_g1,fit_f1,fit_kf1}.sh (PLAN.md commands);
  generate rows carry shards[seat].belief_rebuilds (FullPoolBelief only). CARD LEAD ETA for live16402-on-r1-cards2
  (native 5f07238c + R.bots widening): 2–4 h. Sol S3 (CPU fit timing probe on 08) delegated.
- 02:35–02:45Z preflight dry run on 08 (overlay tree repo-f7e195088c65-ovl, r1-cards1 dev root, OWN=c56): PASS.
  Meta tokens identical; receipts ok; G1 1 game 0 errors (457 labels, 267 CPU s for 6001 ticks, belief_rebuilds 1);
  K1 1 game 0 errors (859 rows, 146 CPU s). 2026-10-16T02:45:53Z PLAN.md: costs updated, GO runbook (section 6).
- 2026-10-16T02:46:48Z BOT LEAD approved the plan and kit; launch sizing rule added to PLAN.md §6 (04/08 up to 40 workers if live python < 60; 03 ≤16).
- 2026-10-16T03:29:52Z r1-cards1 released on main (merge 0ee42633e: pin, widened R.bots, lopp_fast content-hash cache). The assembled
  clasher-bot-runtime/r1-cards1 root does not exist yet on 03/04/08 (SCOPE.md §7 item 11). Sol S1 steered to run the
  smoke now on the r1-cards1 DEV root (native 681b5f2c = pin) with a tree from origin/main, all arms incl. k4lf/genf
  (now expected to pass). Worktree fast-forwarded to 9f75ab5f8: unit tests 10/10, NEW == main's scope.EXTRA_CARDS.
  The launch kit no longer needs the overlay. Waiting for r1-cards2/live16402b (generation start signal).
- 2026-10-16T03:43:25Z Sol S3 CPU-fit probe (08, 02:30–03:41Z): batch 4096 / 32 threads 242.7 s/step (1500 steps ≈ 101 h), batch 512 25.3 s/step, RSS 35 GB → F1 is GPU-only (PLAN.md updated); logs 08:/mpac/sdicks02/jobs/clasher/bot-fullpool/probe-fit/.
- 03:30–04:01Z Sol S1 smoke on r1-cards1 (08, PGID 885147, dev root r1-cards1-dev, tree origin/main d0eec65c, no
  overlay): **all PASS**. stu 40/0 err (0.65), k4l 40/0 (0.90), **k4lf 40/0 (0.875, K4L on full-pool decks via the
  widened R.bots)**, gen 2/0 (701 labels), **genf 2/0 (588 labels, K4S teacher holding non-C56 cards)**, c56s 20/20
  and c56k 6/6 identical hashes, and identical to smoke1 (40/40, 12/12). 0 lopp failures, 0 tracebacks.
  Out 08:/mpac/sdicks02/jobs/clasher/bot-fullpool/smoke-r1c1-d0eec65c0aeb(.summary.json/.comparison.json).
- 2026-10-16T06:45:52Z released root clasher-bot-runtime/r1-cards1 is on 03/04/08 (native 681b5f2c…, receipt source 0ee42633e,
  created 03:33Z). Sol confirmation smoke on it delegated (stu, k4lf, genf N=12 + c56s/c56k, hash comparison with
  the dev-root run). Still waiting for the r1-cards2/live16402b ping to start G1/K1.

## G1 + K1 generation (started 2026-10-16 06:54Z) — RUNNING

**Pin:** live16402b (r1-cards2 + 16.402.19 stats). Pins taken from cards/lead e545eb6bd and carried to main in
2ebaea73. Released root /mpac/sdicks02/repos/clasher-bot-runtime/live16402b on 03/04/08 (read-only):

| file | sha256 |
|---|---|
| native/clasher_core.abi3.so | de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1 |
| gamedata.json | a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb |
| RECEIPT.json (identical on 03/04/08) | 2311429803ed84321ab9d97456aa872ec7127734428d02468de6729e7f534aac |
| CARDS-RUNTIME-RECEIPT.json | 87d4cf225ebdaf39a00650080246a5b01d42c8ac54e702005aab0a2b1e50439c |
| LIVE16402-RECEIPT.json | 81f5ccb3e054449cd64788161514ef2f302481f28b1167a1594c6542f08d4204 |

The dev root 08:jobs/clasher/cards/runtime/live16402b-dev has the same native, gamedata and both inner receipts.
Every G1 shard receipt and row, and every K1 rec line and row, carries `runtime` (pins, root, receipt, native and
gamedata shas; bot/fullpool/provenance.py), so the data can be weighted or refreshed by pin when r1-cards3 or
live16402c (Batches B1/B2) land.

**Preflight PASS:**
- 08: live16402b-dev root, tree 2ebaea73, 06:47–06:53Z.
- 03 (07:01:59Z) and 04 (07:03:39Z): released root, tree 98f4e2b3.

On all three: meta tokens identical to the r1-cards1 dump (no K4L re-extension needed), the three checkpoint
receipts verified, and the 1-game G1 and K1 runs were identical across hosts (293 labels, 2 belief rebuilds; 563 K1
rows; 0 errors).

**Launches** (tree J/repo-98f4e2b36313, ROOT = released root, OWN=full, decks fullpool:11433651:freq=b53b02a1fde4,
G1 base 2613058991490864, K1 base +50,000,000). Each host had live python ≥ 60 at launch (08 74, 03 74, 04 82), so
every host got the 16-process split:

| host | G1 (shard, games, W, PGID) | K1 (shard, cases × 3 opponents, W, PGID) | launched |
|---|---|---|---|
| 08 | 2, 1600, 11, 2850130 | 2, 320, 3, 2850352 | 06:54:10Z |
| 03 | 0, 800, 11, 3862002 | 0, 160, 3, 3862040 | 07:04:38Z |
| 04 | 1, 1600, 11, 2819527 | 1, 320, 3, 2819629 | 07:04:39Z |

Logs and data are on each host: J/g1-x<h>.log, J/G1/ (games-*.jsonl, games/), J/k1-x<h>.log, J/K1-x<shard>/.
J = /mpac/sdicks02/jobs/clasher/bot-fullpool.

**Known runtime bug (CARD LEAD).** In 1 of the first 30 G1 games on 08 (game 2000024, student deck with Freeze),
`c56_scripted.ranked_actions:266` (`float(getattr(spell, 'building_damage', damage))`) raised TypeError on None.
The attribute exists but is None for Freeze, and probably for other non-damage spells. It fires when our or the
teacher's hand holds such a spell and an enemy non-crown building is on the board, and the whole game is lost. G1
records it as an error row. The fix belongs in the root (a None fallback). A rerun of the same command on a fixed
root retries exactly the errored games, since done_games skips only non-error rows.
- 06:46–06:59Z Sol smoke on the RELEASED r1-cards1 root (08, PGID 2370959; out 08:J/smoke-r1c1-released): **PASS**.
  stu 12/0 errors (0.833), k4lf 12/0 (0.833), genf 2/0 (582 labels), c56s 20/20 and c56k 6/6 identical within the run
  and identical to the dev-root run (40/40, 12/12); 0 lopp failures, 0 tracebacks. Full-pool command hashes differ
  from the dev root (stu 1/12, k4lf 1/12, genf 0/2). That is expected: the released root has the same native
  (681b5f2c) but 9 changed Python engine overlays (Batch A mechanics: battle.py, spawner.py, death_effects.py,
  entities.py, card_types.py, balance.py, mechanic_detector.py, differential.py, spawn_snapshot.py; source
  0ee42633e vs b7143dd7a). Released CARDS-RUNTIME-RECEIPT.json sha256
  13ecef349fa451bfb39c1e9f98b66a66f514501e4dcb85f5a286337b3cd31ace. C56 bit-identity holds on the released root.
- 07:05Z Sol babysitter for G1/K1 delegated (clientRequestId fullpool-g1k1-babysit-r1; log 05:J/babysit-g1k1.log;
  relaunch-same-command on death; an extra K1 shard per host once its G1 shard ends; stop and report on a new error
  type or >8% errors).
- 07:08Z **G1 scale-up** (coordinator): new G1 shards with fresh game indices on the same tree and live16402b root,
  via cpu_job.sh, nice 15. Memory check first: about 0.85 GB RSS per worker; 76–91 GB available. The 105 live-python
  cap binds (live 08 61, 03 79, 04 97):

  | host | shard | games | W | PGID | log |
  |---|---|---|---|---|---|
  | 08 | 5 | 3200 | 40 | 3611792 | J/g1-x08-s5.log |
  | 03 | 3 | 1700 | 21 | 3874483 | J/g1-x03-s3.log |
  | 04 | 4 | 2400 | 30 | 2936118 | J/g1-x04-s4.log (waits in cpu_job.sh until the host has room) |

  - **Shared output dir:** shards on a host share J/G1. Sealed shards are per game; games-<worker>.jsonl lines from
    two shards may share a file (append-mode single writes). done_games/pack read all of it.
  - **Babysitter rules:** steered to watch the GPUs on 04/08 (halve our extra shard if a GPU is under 70% on two
    checks), back off when a user logs in, and leave root switching to the owner.
  - **Patched root:** when live16402b-r2 (Freeze fix) lands, every later shard launches on it and the errored games
    are rerun there.
- 07:12Z G1 shard 6 on 03 (it11's C56 feeders stopped, so 03 was at live 38, 104 GB free, no users): 3000 games
  (indices 6,000,000+), W=50, PGID 3889910, J/g1-x03-s6.log. 04's queued shard 4 (W=30) now fits. Babysitter
  tracks all 7 G1 shards (0–6) and was restarted to keep its loop in one turn (its first turn had ended at 07:10Z).
- 07:31Z babysitter stopped on a NEW runtime error (jobs untouched):
  `ValueError('no C56 public model template: BarbarianRageDamage/AreaEffect')` in fair_player.root
  (engine-speed/stage5/fair_player.py:118). It is Lumberjack's death-rage area, which has no root template. One G1
  game (08, shard 5, game 5000110) and one K1 game (04, shard 1, case 1020). Second runtime-root bug for the CARD
  LEAD, after the Freeze building_damage None bug.
  Totals at 07:31Z:
  - G1: 894 games (884 ok), 352,938 labels, 10 errors (9 Freeze, 1 template), mean 210 CPU s/game.
  - K1: 113 games, 70,379 rec rows, 2 errors.

  Error share is 0.3–2.1% per host, under the 8% stop. The babysitter was resumed (07:34Z) with both errors marked
  known, and with the GPU rule refined: a low reading counts only when a compute process is present. 08 read 0% once
  between batches, then 93% with the LIVE process.
- 08:05Z **live16402b-r2** (CARD LEAD Python-only fix: Freeze building_damage None and the ThreeMusketeers missing-HP
  crash; same native de11f124 and gamedata a7de3e93). Root /mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r2;
  RECEIPT.json sha256 32028a65d30f08b5efdbde77c020f93e9aaf252d98a7efaec407e02b0ebb9499 (identical on 03/04/08).
  - Pins: r1-cards2-r2 and live16402b-r2 carried from cards/lead 43d688f85 to main (93c1fe1a). The launch kit
    defaults to PINS=live16402b-r2.
  - New option: `lopp_record --retry-errors` (k1.sh RETRY=1), because lopp_record counted error rows as done.
  - r2 preflight PASS on 04 (08:00:49Z) and 08 (08:01:19Z), tree repo-93c1fe1af8ca. On 03 it is queued in cpu_job
    (03 at 109 live python).
  - **r2 does NOT fix the BarbarianRageDamage/AreaEffect template error.** Replaying game 5000110 on r2 (08,
    07:54–07:57Z) failed identically. That one is still open for the CARD LEAD (fair_player.root has no template
    for Lumberjack's death-rage area).
  - Data tags: rows and shards made on r2 carry runtime.pins = live16402b-r2 and the r2 root path and receipt.
  - Plan: running shards finish on live16402b. Each finished shard's errored games are rerun on r2 (same shard
    command from the new tree; K1 with RETRY=1). Every new shard runs on r2. The babysitter owns the reruns and was
    steered at 08:05Z.
- 08:14–08:21Z **more shards on live16402b-r2**, after the BOT LEAD's cpu_room fix (live count excludes the YOLO
  `train_cr.py` loaders; fixed cpu_room.sh md5 614c878b5aa8, copied from /mpac/sdicks02/repos/clasher-bot into my
  tree repo-93c1fe1af8ca on 01/04/08; main still has the old one):

  | host | job, shard | size | W | PGID | live at launch |
  |---|---|---|---|---|---|
  | 04 | G1 shard 7 | 3200 games | 40 | 2656021 | 64 |
  | 08 | K1 shard 11 | 800 cases x3 | 40 | 3163805 | 58 |
  | 01 | K1 shard 10 | 800 cases x3 | 50 | 1704106 | 34; GPU 95% |

  - **01 root:** 01 had no live16402b-r2 root, so the released root was copied 04 → 01 over the LAN into
    J/roots/live16402b-r2. Its full-file manifest sha256 is 224a5e6f2f88649a80fa128afb8a4cd637acc66cdd1ae8788ff5125e7b85490a
    on both hosts; RECEIPT.json 32028a65…, native de11f124…. The r2 preflight on 01 PASSED at 08:20:56Z.
  - **01 size:** ~50 per the BOT LEAD (the LIVE LEAD's YOLO synth gets ~32 cores, their trainer ~8). No more shards
    go on 01.
  - **Babysitter:** steered with the new shards, GPU checks on 01/04/08, and halving order (newest shard first).
  - **cpu_feeder.sh** has the same live_py flaw (it counts the YOLO loaders). The feeders are off now; it11 must
    patch it before restarting them.

## 2026-10-16 16:22Z — packing/refit recovery closed at explicit blockers (Sol high)

Recovered in place after the provider-stream failure. Full evidence and source proof:
`reports/bot/fullpool/REFIT-AUDIT.md`; commands/results/failures, exact identities, snapshots and preserved
failed/current outputs: `05:/mpac/sdicks02/jobs/clasher/bot-fullpool/refit-recovery-20261016T1611Z/`.
An append-only pointer was added to the existing `babysit-g1k1.log`; its earlier history remains intact.

- **Packing:** existing packs 03/04/08 contain 2,262,299 / 2,953,699 / 1,976,795 rows = **7,192,793**.
  Complete metadata, source-index hashes and row sums agree; 23,266 sealed shards, zero duplicate source paths
  across packs. Array payload hashes were not all recomputed. No repack launched. Original pack PGIDs:
  03/1594987 (16:05:25–16:07:41), 04/558472 (16:05:25–16:08:39), 08/1660796 (16:05:26–16:07:37).
- **F1 invalid:** actual host source proved ratios 1.0 (08) and 2.0 (04) left `old=None`; required C56 replay
  corpora were not loaded. Old manifest hashes did not prove inclusion. Both trained entirely from G1,
  which itself can include C56 observations. `old_rows=0` was accurate, not accounting ambiguity.
- **Failed CUDA evidence:** first attempts 08/1905505 and 04/812758 failed by 16:10:02 with incompatible torch/
  driver; `fail1.log` files preserved. Their printed `rc 0` was false success from the wrapper. Prior provider
  deletion of first output dirs is documented; recovery deleted no outputs. Retry detach initially returned
  those stale receipts, not actual retry job identities.
- **Adopted current jobs:** F1a08 PGID1918203/trainer1918288, F1b04 PGID855251/trainer855446, actual process starts
  16:10:37. KF1a01 PGID2895857/trainer2896071 (16:06:11), KF1b01 PGID2896463/trainer2896759 (receipt16:06:12).
  Actual argv, boot/start ticks, source hashes, log descriptors, UID/cwd/executable and lease10 each were checked.
  KF1 loaded only K1 x0/x11/x10 (3,292,938 rows); required old C56 pool recording union was absent.
- **CPU gates failed:** KF1 configured16 training threads per lease10; extraction8 is an earlier phase, so
  peak16, not24. F1 configured8 trainer threads plus8 concurrent loaders, envelope16 per lease10.
  NLWP was not equated to compute demand. No live lease edits or capacity assumptions were made.
- **Authority and stop:** parent direction16:13:09 required exact guarded stop for these failures. LIVE
  temporarily lent only the exact existing04/08 F1 jobs; that did not waive correctness/capacity. Independent
  Sol review approved guard SHA256 `c15032d1a166d9d63f1f2d8ec42ad3245ec0586c959517e092f0958254c72dc3`.
  One SIGTERM after fresh identity/lease/source/log-fd revalidation per exact group:04 F1b16:17:21,
  08 F1a16:17:27,01 KF1a16:17:36,01 KF1b16:17:49. All had no live members by16:17:53; their own EXIT traps
  removed leases. Terminal snapshot16:18:20 confirmed no refit lease or GPU process. LIVE received GPU handback;
  GPU04/08 reverted to LIVE. No retry, extension, output deletion, SIGKILL or promotion occurred.
- **Output status:** F1a/f1b ended at recorded steps208/202; no checkpoint/complete marker. KF1a/b ended after
  epoch4; no model export. All original/current logs, receipts, inputs and train logs survive and were copied
  into the recovery evidence. These are invalid/incomplete attempts, not evaluated models.
- **Prepared fixes, independently reviewed:** fractional mixtures(.5 and2/3), rejected silent old omission,
  compatible CUDA venv default, current-lease CPU budget validation (F1 8+2=10; KF1 max8,8+parent=9), fresh names/
  output guards, real trainer exit propagation, safe `set -e` env sourcing, required `OLD_REC`, Path-safe KF1 JSON,
  finite/tolerance-checked gate/card/all-hand-tile serving parity before export completion JSON. Actual host
  source trees remain unchanged. Four light unit tests, shell syntax, both OWN env modes and diff checks passed;
  final independent source review approved preparation only. No corrected fit/export or eval ran.
- **Concrete remaining gates:** review immutable datasets and exact legacy KF1 recording identities/union;
  obtain fresh capacity/allocation; stage/review exact corrected host sources and fresh argv/log/receipt/output
  identities; separately authorize a relaunch and subsequent result gates. Earlier preflights/idle observations
  are not authority. Existing K1 first-pass groups04/2819629 and08/2850352 continue untouched (lease4 each);
  no failed-game retries or old gates were revived. Coordination blockers go to owning parent0523ae6f…;
  the shared bot lead remains context-blocked. No routine milestone DMs were sent.
- 17:10–17:50Z **F1 refits done** on GPU (fixed sources b32921a3: --new-ratio is the new-corpus fraction; the C56 replay is
  actually mixed). Each arm: one attempt inside the LIVE LEAD's 16:30–18:30Z GPU windows, CPU 10 (4 threads + 6
  loaders), 1200 steps, init rl5-v10-fp, new = the three G1 packs (6,836,154 train / 356,639 held-out rows),
  old = kc7a x01/x04/x08 (1,545,817 rows). Rows per batch: new 2048 (f1a2) / 2731 (f1b2).

  | arm | host | new fraction | held-out loss | threshold | step-001200.pt sha256 prefix |
  |---|---|---|---|---|---|
  | f1a2 | 08 | 0.5 | 4.943 | 0.644 | 0c03f79ffe5aa19e |
  | f1b2 | 04 | 2/3 | 4.930 | 0.642 | 34176b656d3a7bb8 |

  Checkpoints are every 250 steps, with complete.json. The old f1a/f1b dirs (invalid: no C56 replay) are kept.
- 17:46Z **BOT LEAD reset:** no permission process; the owner launches, fixes and retries; the pin is
  **live16402b-r3** (the CARD LEAD fixed the template-error class).
  - r3 roots: identical on 03/04/08 except the per-host RECEIPT.json (file manifest excluding RECEIPT.json
    1aa243756bd98494…). Copied 04 → 01 into J/roots/live16402b-r3 (same manifest).
  - Tree J/repo-b82939149f8a (main b8293914). Its first r3 preflight FAILED: ModuleNotFoundError
    clasher.rl.slot_permission. Main commit e883a80da (LIVE slot eligibility) imports a module that exists only in the
    repo's src/, while Runtime puts the root's clasher package first, so every search player on main breaks against
    the fleet roots. Workaround: the run tree overlays the four pre-e883a80da files (bot/search/{players,candidates,
    lopp_fast}.py, bot/live/player.py; shas in T/OVERLAY-pre-e883a80da.txt). In sim no packet has slot-permission
    data, so behaviour is unchanged. After the overlay, r3 preflight PASS on 03 (17:55:57Z) and 01 (17:56:39Z).
    **This needs a proper fix on main by the LIVE LEAD.**
- 17:48–17:57Z **launched on r3:**
  - G1 shard 8 (03, W50, 4000 games, PGID 1895853) and G1 shard 9 (01, W40, 3200 games, PGID 335988).
  - K1 shard 12 (03, W36, 1000 cases, PGID 1896024) and K1 shard 13 (01, W25, 600 cases, PGID 336557).
  - Reruns of the template-errored games: G1 shards 0–7 on their hosts (W4 each); K1 shards 2, 10, 11 (RETRY=1).
  - KF1 arm a on 01 (k1a1, CPU, from poolfp, PGID 4033434) and arm b on 08 (k1b1, fresh vocab, PGID 4178213).
    Both on K1 x0 + x2 + x10 + x11 plus the legacy bot-lopp-rec union; NAME/receipt in J.
  - The r2 K1 shard 1 on 04 (PGID 2819629) continues.
- 17:59Z Sol helper (fullpool-f1-screen-babysit-r3-20261016): F1 screen on FP-DEV, then C56-REG (f1a2, f1b2 vs the
  rl5-v10-fp baseline, opponents extended R3a and v1, 300 paired cases, on 04/08 via run/eval_f1.sh), plus
  babysitting and filling 04/08 with new G1 shards after the evals.
- 2026-10-16T18:15:52Z main fixed by 5bce7c28b (slot-permission change reverted, slot_permission.py deleted). Main's four files are byte-identical to my overlay (sha prefixes a58a4787/0c2e14fe/dd0a067c/3b4f27d7), so running jobs on repo-b82939149f8a are unaffected; the next stage drops the overlay.
- 2026-10-16T18:26:54Z **F1 screen, FP-DEV** (both decks full-pool, live16402b-r3, 300 paired cases per opponent, 1800 games, 0
  errors; rows on 04/08 at J/eval-f1-fpdev). Baseline = extended RL r5 v10 (0.5375); opponents are the extended R3a
  and v1.

  | opponent | base | f1a2 | f1b2 | f1a2 − base [95% CI] | f1b2 − base [95% CI] |
  |---|---|---|---|---|---|
  | R3a | 0.572 | 0.617 | 0.613 | +0.045 [−0.023, +0.110] | +0.042 [−0.022, +0.105] |
  | v1 | 0.800 | 0.833 | 0.830 | +0.033 [−0.017, +0.083] | +0.030 [−0.027, +0.087] |
  | pooled (n=600) | 0.686 | 0.725 | 0.722 | **+0.039 [−0.003, +0.082]** | +0.036 [−0.006, +0.078] |

  Both arms are about +0.04 over the baseline, but this is the dev (selection) bank, so it is not a claim. The C56-REG
  regression check was moved to 01 (W16), because live-diag has priority on 04/08 until ~20:05Z. The 08 eval lease
  was lowered from 51 to 8 so it stopped blocking live-diag.
- 19:00–19:45Z **live full-pool switch gate (top priority).**
  - **Bank LIVE-AB1** (base 2988209034608560, drawn 19:12Z before any game; decks e16bl = live e16 vs the LIVE LEAD's
    91 Battle Log opponent decks, opponent-decks-20261016.jsonl sha 3a7c4e78…; 13 of the 91 are C56-only).
  - **Arms:**
    - Arm A `aliased:K4L-R-gs-mpool`: the C56 bot. Its observation and belief see the live-perception alias from
      katacr_to_clasher.json (6548c95e…) `identity`: MegaMinion→Minions, BattleRam→HogRider, Bomber→Firecracker,
      Barbarians→Knight, Tombstone→Cannon, SpearGoblins→Goblins, GoblinCage→Cannon. A non-C56 card without a C56
      identity is dropped, and a merged look-alike repeat that the ordinary cycle rules out is dropped too. It uses the
      live C56-catalog belief. The sim plays the true cards (bot/fullpool/alias.py, play_match observe_alias hook).
    - Arm B `K4L-R-gs-mk1a1`: the KF1 net, the open-world full-pool belief and true ids.
  - **Opponents:** extended R3a and v1, 800 paired cases each (03 [0,500) PGID 2210521, 01 [500,800) PGID 4162443),
    plus `LIVE-K4CW-r16` (deterministic K4C-r16 with the live belief), 300 paired cases (03 [0,180) PGID 2242181,
    01 [180,300) PGID 340955).
  - **Dry runs:** 16 + 2 games, 0 errors. They caught two problems before the full run: stage.sh omitted
    reports/bot/fullpool/ab, and merged aliases broke the ordinary-cycle check. Both fixed.
  - **Capacity:** G1 shards 8/9 and K1 shards 12/13 are paused by the owner for the A/B. Per the plan of record, no
    new G1 shards on the current teacher; K1 resumes after the gate.
  - **rext-bc:** RoyaleSim-only (royalesim_match), and our RoyaleSim translator vocab is C56, so it can't be a
    full-pool row without a full-pool royalesim_vocab rebuild. Blocked; reported.
- **KF1 done:** k1a1 (from poolfp, best epoch 7) and k1b1 (fresh, epoch 5), 4.58M rows each (K1 x0, x2, x10, x11 +
  legacy). Validation: gate AUC 0.785 / 0.785, card top-1 0.679 / 0.681, tile within-2 0.585 / 0.577. Export parity
  passed on both. **k1a1 chosen.**
- **Bundle code on main:**
  - bot/live/player.py keeps the full-pool open-world belief when BOT_BELIEF_PRIOR is a full-pool spec (64c720ea).
  - headline resolves LIVE-/K4CW-/PERC- names.
  - packet_check (22ff0a60). The translator owner got the token-space answer and the checker.
- 19:45–19:56Z **bundle fixes and checks:**
  - **Live belief bug fixed:** the live wall-search planner (bot/live/player.py WallCandidatePlayer.start, the third
    PublicPlanner site) still used rt.PRIOR, so the live bundle player ran the plain C56 Belief even with
    BOT_BELIEF_PRIOR set. Found by an import-closure probe; fixed in 844d5655 (default unchanged).
    - After the fix, `LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res` runs FullPoolBelief. It reads the data files
      reports/bot/fullpool/freq/arena-card-freq-b53b02a1fde4.json and reports/live/loop/ARENA-CARDS.md (plus the ab/
      Battle Log decks only in sim cases).
    - Its bot/ import closure is 34 modules: bot/{cards/{fc_cut,scope}, eval/headline, exit/student,
      fullpool/{banks,belief,cards,extend,models}, live/{levels,player,translate},
      players/{base,ours,policy,royalesim_translate,runtime,search,variants},
      search/{candidates,lopp,lopp_fast,lopp_feat,oppmodel,players,reserve}} plus the __init__ files.
  - **The running gate is valid:** in its tree, arm B K4L-R-gs-mk1a1 runs FullPoolBelief (400 decks, 672,000 states)
    and arm A runs LiveBelief over the C56 catalog (4,914,000 states). The gate players don't use the patched live
    planner.
  - **`res` token** (main 7b693b8e4, bot/search/reserve.py): without the token, `K4L-R-gs-mk1a1` gives identical
    command hashes on the old tree (no reserve code) and on new main, 7 of 7 LIVE-AB1 cases, and the reserve is never
    called. With-token and lopp_fast (t2) variants are running on 08 (res-new2/res-old2). The p2 variant cannot run
    inside a Pool worker.
- **Mac scope:** the Mac snapshot manifest (scratch/live-loop/packages/manifest-simple-r2/bot-snapshot-20261016.sha256,
  71 files) vs main d4d32f9a. Changed: 16 files (bot/live/{births,levels,player,translate},
  bot/players/{ours,royalesim_match,royalesim_translate,royalesim_vocab,runtime,search},
  bot/search/{lopp,lopp_fast,lopp_feat,lopp_record,lopp_train,players}). Added: 220 (of which the live closure needs
  bot/cards/{fc_cut,scope,proxy_table}, bot/eval/headline, bot/exit/student, bot/fullpool/{banks,belief,cards,decks,
  extend,models}, bot/players/{policy,variants}, bot/search/{candidates,oppmodel,reserve}). Removed: bot/live/
  {mac_bench,mac_perc}.py.
- 20:01Z **`res` token proven for the full-pool player** (LIVE-AB1 cases 0–9 vs R3a, 08; bot/fullpool/res_check.py;
  old tree b3e81b9e without reserve code vs new main):
  - Without the token, `K4L-R-gs-mk1a1` and the lopp_fast path `K4L-R-gs-rw-fc-t2-mk1a1` both give identical command
    hashes, 10 of 10, and the reserve is never called.
  - With `-res`, both fire in 10 of 10 games, with penalty > 0 on 4,600 of 12,560 scored keys, and every command
    hash differs from the no-token run.
  - So the bundle can ship `LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res` if the ladder A/B keeps -res.
- lopp_time gained --decks/--bank (4f426736) for the post-gate timing on 04 (e16 vs Battle Log cases).
- 20:13–20:22Z **live16402c** (CARD LEAD: r3 + B1/B2, native 326ce6f9…, gamedata a7de3e93…, 08 RECEIPT.json
  2e0891da…; pins on main 2ce6abd7b). Preflight on 08, tree J/repo-bca383f068e7 (main bca383f0, with the fixed
  cpu_job.sh 5179f0f42): PASS at 20:21:28Z, meta tokens identical, 0 errors. K1 shard 14 launched on live16402c on 08
  (W35, 800 cases, PGID 232762), tagged pin live16402c. The bundle stays on live16402b-r3, and no new G1.
- 21:08Z **LIVE SWITCH GATE: PASS** (bank LIVE-AB1, fresh, base drawn 19:12Z before any game; e16 vs the 91 Battle Log
  decks; live16402b-r3; 3800 games, 0 errors; rows on 01/03 J/ab1-weak, J/ab1-k4cw; python -m bot.fullpool.ab_summary).
  A = current live (`aliased:K4L-R-gs-mpool`, live alias of off-vocab cards, C56 catalog belief).
  B = full-pool (`K4L-R-gs-mk1a1`, true ids, open-world belief). Paired by (opponent, case):

  | opponent | n | A | B | B − A [95% CI] | C56-only decks | off-vocab decks |
  |---|---|---|---|---|---|---|
  | R3a | 800 | 0.848 | 0.901 | **+0.054 [+0.024, +0.085]** | +0.009 (n107) | +0.061 [+0.027, +0.094] |
  | v1 | 800 | 0.939 | 0.966 | **+0.028 [+0.008, +0.048]** | +0.037 (n107) | +0.026 [+0.006, +0.046] |
  | LIVE-K4CW-r16 (strong) | 300 | 0.383 | 0.533 | **+0.150 [+0.073, +0.227]** | +0.073 (n41) | +0.162 [+0.081, +0.243] |
  | pooled R3a+v1 | 1600 | 0.893 | 0.934 | **+0.041 [+0.023, +0.059]** | | |
  | pooled all | 1900 | 0.813 | 0.871 | **+0.058 [+0.038, +0.078]** | +0.031 [−0.024, +0.086] (n255) | +0.062 [+0.041, +0.083] (n1645) |

  Gate: B ≥ A pooled (yes, CI excludes 0); no loss on C56-only decks (+0.031, CI includes 0, no regression); the
  strong-opponent row improves most (+0.15). Not in the gate: rext-bc (RoyaleSim-only; C56 RoyaleSim vocab),
  reaction time and undefended pushes (these rows have no play logs; BOT_PLAYLOG=1 adds them from now on).
- 21:20–21:27Z **bundle player timing** (an urgent check after deck-search's smoke showed 65% cutoffs on a 9-CPU
  lease on loaded 01). lopp_time on 03, 5 pinned physical cores per arm, LIVE-AB1 cases vs R3a, live16402b-r3,
  partial 3–5 games per arm (10 each still running); sibling SMT busy 4–8%:

  | arm | wall p50/p95/p99 ms | hit | default | search p50/p95 | prep p50/p95 |
  |---|---|---|---|---|---|
  | base `LIVE-K4L-R-gs-rw-fc-w200-t4-p4` | 82/190/199 | 4.8% | 2.0% | 41/118 | 39/78 |
  | `…-mk1a1` | 78/184/198 | 3.2% | 1.8% | 38/117 | 39/76 |
  | `…-mk1a1-res` | 80/177/200 | 3.1% | 1.6% | 39/114 | 39/69 |

  One-game profile, mean ms per search decision, base vs full-pool:
  - score_candidates 58 vs 51; candidates 9.1 vs 8.1; R.root 5.5 vs 5.9;
  - belief.update 3.8 vs 2.3; belief.sample 0.2 vs 0.1; fast tier per poll 17.6 vs 17.4;
  - prior rebuild 24–51 ms each, 2 per game.

  FullPoolBelief (672k states) is cheaper than the C56 LiveBelief (4.9M). The full-pool path is not slower; the 65%
  smoke result is host contention. The gate is unaffected: its arm B was the deterministic no-wall twin.
- 21:29–21:45Z **bundle package delivered to the loop owner** (thread live-loop-owner-r1, 21:4xZ), ahead of the 23:00Z
  deadline. Reference reports/bot/fullpool/BUNDLE.md (b8d41879). Code main 2fa5d496; 11 changed + 17 added closure
  files vs the Mac snapshot; 4 data files; models with sha and size; env for both players; res included.
  - f1a2 C56 regression DONE (1800 games, 0 errors): +0.001 [−0.037, +0.037] vs rl5-v10-fp, so f1a2 ships as the
    fast tier.
  - Mac-tree-copy equivalence: 40/40 command hashes identical (mk1a1, mk1a1-res, fast path t2, both). res is inert
    without the token and fires with it.
  - Timing (03, pinned): base 83/190/194 ms, 4.4% hit; mk1a1 78/184/193, 3.5%; mk1a1-res 85/173/200, 2.7%.
  - Deck-search's serial-twin hash mismatch was their own harness (a Recorder cached the 0.2 s deadline). Not the bot.
- 21:43Z **final timing**, 10 games per arm (03, pinned; 1101–1369 decisions):
  - base: 80/180/193 ms, hit 2.9%;
  - mk1a1: 78/183/193 ms, hit 2.9%;
  - mk1a1-res: 94/170/193 ms, hit 2.3%.

  Parity, sent to the loop owner. Babysitter r3 finished (generation: 27,441 rows; r3 2,542 rows, 0 errors;
  live16402c 491 rows, 0 errors). G1 shard 8 resumed on 03 (W55, PGID 2635204).
  **Running:** K1 14 (08), 15 (04), 16 (03) on live16402c; G1 8 (03) and 9 (01) on r3. Sol babysitter r4 tracks them.
- **Next for the track** (after the live switch), per Sam's direction: per-tick play/wait learned elixir banking.
  RL or ExIt against strong opponents (K4C-r16 class) with the fixed learned-leaf teacher; no G1 relabel until that
  teacher exists. Every eval reports reaction time and undefended pushes (headline BOT_PLAYLOG=1). The live16402c
  smoke of the bundle player follows after the swap is scheduled.

## 2026-10-17T00:06:11Z — plan step 2 GPU work: value net, leaf term, per-tick RL warm-up (BOT LEAD 23:15Z)

**Running**
| host | job | PGID | what | ETA |
|---|---|---|---|---|
| 04 GPU | vn0b | 3253578 | value_net.py on G1 a-packs x03/x04/x08 + C56 kc7a x01/x04/x08 (~11.9M train rows), init rl5-v10-fp trunk, heads d15/d30/d60/outcome, 6000 steps; out $J/vnet/vn0b | ~02:45–03:15Z (shares the GPU with LIVE YOLO) |
| 08 GPU | rlfp1 learner | 888224 | bot.rl.learner, init rl5-v10-fp, league v1 .15 / R3a .15 / self .25 / K4C-r16 .35 / LIVE-K4CW-r16 .10, full-pool decks (FP train sampler), RL bank 3368089670243744; run $J/rl/rlfp1 | warm-up: ~3 updates/h, snapshot every 5 |
| 08 CPU | rlfp1 actors b0 | 1040462 | 10 workers (08 full; add a block when room frees) | — |
| 03 CPU | leafgen1 | 3157102 | bot.value.gen, K4L-R-gs-rw-mk1a1 vs K4C-r16 ×2 / LIVE-K4CW-r16 / R3a / v1, full-pool decks, bank LEAF1 1388654536695216, 30 workers, games 0–2999; out $J/leafgen1 | first leaf v1 refit ~03:00Z |

**Owner-paused for room:** K1 s20 (08, 368 rows, 23:34Z) and K1 s15 (04, ~800/1200, 00:06Z); K1 s19 earlier. Resume
any of them by rerunning the same k1.sh command (done rows are skipped).

**Results so far**
- vn0a (23:23Z) was invalid. exit_r3 combined_batch returns rows grouped by store, so with 6 packs its targets
  were permuted against the inputs, and held-out corr stayed ~0 at step 1000. Fixed in value_net.VGroup.batch (sort
  the flat indices; store order is monotone in them). bot/rl/critic_pretrain.py's per-row opponent ids have the same
  latent misordering (outcomes there came from the batch itself); not fixed.
- Fixed value net, 2-pack test (200 steps): held-out corr d15 0.67, d30 0.57, d60 0.49, outcome 0.44.
  - Elixir check on the d30 head: +1 own +0.0099 (96 % of rows > 0), +1 opponent −0.0040 (71 % < 0), the right signs.
  - The outcome head has the wrong opponent-elixir sign (+0.035): the outcome target carries the on-policy confounding;
    the 30 s margin target does not.
- Leaf v0 (bot/fullpool/leaf_value.py; old C56 value-gen roots, 1670 games K4S-st vs R3a/v1; 195k rows; game%5 held out):
  - Held-out-game corr with the +30 s margin change: MLP 0.51, linear 0.46, phi difference 0.175.
  - Elixir weak: linear net +0.0004 per own elixir; MLP opponent-elixir sign wrong (+0.0017).
  - Model $J/leafvalue/c56v0/mlp-d30.npz, sha256 5aae9a08f0a30c8536a3f0ecbaa57025e808433ab971e62a7bf133b2389d77da (01/03/04/08).
- K4L leaf term (bot/search/lopp.py core.leaf_value + token vl<P>, serial only):
  - vl0 matches base command hashes 6/6 (LIVE-AB1, live16402c), so rollout_commands is bit-identical to rollout_e1 there.
  - vl50 changes play.
  - Handed to live-diag for -rh screens (K4L-R-gs-rw-rh-vl25/50).
- RL update 1 (critic warm-up, 120 games): init scores K4C-r16 0.18 (45), LIVE-K4CW-r16 0.00 (7), R3a 0.69, v1 0.79,
  self 0.36.
- Incident: a14fe9b55 dropped live-diag's lopp.py rh/lc tokens (stale worktree); restored in 505a6697b; worktree
  reset to origin/main; live-diag told.

## 2026-10-17T03:10:22Z — leaf v2 (distilled) passes the sign gate; max-level eval rule; RL eval at max levels

- **Leaf v0 vl screen (live-diag, BASE10 vs K4C-r16): negative.** -vl25-rh −0.07, -vl50-rh −0.06 vs base; −0.25 vs -res; -vl50-res −0.23 vs -res.
- **Leaf v1 (realized +30 s margin, leafgen1: 1486 full-pool games vs K4C-r16/K4CW/R3a/v1, strong ×3): sign gate FAIL.**
  - lin: own elixir −0.0029.
  - mlp: own +0.0052, opponent −0.0010 (40 % of rows < 0).
  - Not shipped.
- **Distillation:** bot.value.gen BOT_VN_TEACHER stores vn0b's heads on each root's own v5 packet (vn0b-t1 sha256
  83f00d1f099b7be3d311db51a973b59850d42fe0ffd1c887e0909bf0ccbb0d17); leafgen2 / 2b (03) / 2c (04): 2489 games, 0 errors.
- **Leaf v2 = fp2vn** (leaf_value --target vn, strong ×3): mlp-d30 sha256 0fbebb3cd1d72a335ef5c5e441792a64102a4e485e54057c02fd371456942301.
  - Held-out corr vs the teacher: 0.76 (0.75 vs strong); vs the realized change: 0.43.
  - Own elixir +0.0133 (95 % > 0); opponent −0.0043 (69 % < 0), −0.0111 vs strong. Sign gate PASS (lin also passes).
  - Handed to live-diag 03:11Z for the 5-arm vl screen. leafgen2/2b/2c drained (STOP files 03:04–03:09Z).
- **vn0b final (6000 steps):** d15 0.750, d30 0.662, d60 0.586, outcome 0.624.
  - d30 elixir: own +0.021 (98 %), opponent −0.0087.
  - The outcome head's opponent-elixir sign is wrong (confounded).
  - vn1 (+ G1 pack b-x03, 1.66M rows, 8000 steps) running on 04 since 02:32Z.
- **Max-level rule (Sam, 10-17 02:44Z)** — headline --levels max (7065dc345):
  - Setup: RoyaleSim only, every card L16, King towers L16 (live16402c gamedata max; RoyaleSim King HP 7728). Rows are
    tagged card16-tower16. Our engine refuses it (all-L11).
  - Limit: the RoyaleSim vocab is C56 (+7 extra cards in the deck-search combined vocab), so max-level evals use C56 decks.
  - Search planners keep their L11 rollouts.
- **Training data levels:** G1, K1, rlfp1 rollouts and leafgen all ran in our engine, every card and tower L11.
- **rlfp1 max-level snapshot eval (08, 03:01Z, PGID 4116722):**
  - Setup: v0 / v20 / v35 vs R3a / v1 / K4C-r16, 100 paired cases each; fresh bank 2497496291057792; RoyaleSim, card16-tower16, x4s decks.
  - Out $J/rl/rlfp1-evalmax1. RL actor block 2 stopped for room.
- **Owner-paused:** K1 s15/s19 (04), s20 (08); resume by rerunning the same k1.sh command.

## 2026-10-17T08:41:21Z — levels merge, leaf diagnosis, sibling leaf, filler, true-ids v3/v3b, eval banks

- **cards/levels merged** to main 3ea58c365 (BOT LEAD authority).
  - Post-merge levels=None parity: K4L-R-gs-mk1a1 vs R3a/v1, LIVE-AB1 0-4, 10/10 identical command hashes.
  - Spot check: 2 full-pool L16 games on our engine, 0 errors.
  - Open: pooled p<N> plans at L11.
  - Cost: exact-level planning is ~9x slower per game (975 vs 104-125 s), so headline --level-planner l11 is now an option.
- **Leaf v2 (fp2vn) diagnosis (leaf_diag.py):** no seat/sign/parity bug.
  - The term's within-decision spread was 1.5x phi's and uncorrelated with it.
  - vl sign A/B (our engine L11, s62 vs BL, K4C-r16, 60 paired vs -rh): vl5 -0.100, vl10 -0.067, vl50 -0.217, vln50 -0.450 (60/60 lost).
  - The state value carries direction but adds nothing at any kappa.
- **Sibling leaf (sibling_gen / sibling_fit):** realized 30 s margin of forced sibling branches, own deck rotating.
  - Fix: roots now need >= 2 scorable siblings (81 % of roots had only WAIT).
  - Features: crown-risk inputs (last tower x king damage, king threat).
  - First fit, 773 roots: pair accuracy V 0.551 / phi 0.544 / search score 0.571; kappa_max ~0.10. Data still accumulating.
- **Filler (bot/exit/filler.sh):**
  - scan-ahead groups;
  - NUMBA_CACHE_DIR (read-only roots plus the full $HOME quota killed every block);
  - crashed workers now fail their job;
  - Traceback backoff;
  - load-based admission (TARGET 100, python cap 112 / max-live);
  - shedding when real jobs push over the cap.
- **true-ids:** v3 (9 classes) and v3b (28 classes) all PASS on live16402b-r3 (v3 also on 16402c). Body-name notes: MiniSparkys=MiniZapMachine, RamRider=Ram, Heal=HealSpirit.
- **Running evals** (repo-93593905f11a):

  | job | host | out | setup |
  |---|---|---|---|
  | levels-ab1 | 04 | $J/levels-ab1 | planner l11 vs exact; collection levels vs the BL prior, King 7; K4C-r16/R3a; 100 paired; bank 2502749530331968 |
  | wv-arch1 / wv-bl | 08 | $J/wv-* | -res vs base; s62 vs archetype-core sampler decks / 91 Battle Log decks; K4CW/R3a; L16 truth, L11 planner; banks 1181552134866208 / 2442266774857200 |
  | dd1-res | 03 | $J/dd1-res | DD1 row, base vs -res vs LIVE-K4CW-r16, 200 cases, L16/L11 planner |

- **Deck-diverse row:** spec dd1 / bank DD1 3241892761760944; dd_summary.py; archetype.py.

## 2026-10-17T10:10:46Z — eval results; value-net v1 fails its gates

- **levels-ab1** (planner L11 vs exact; collection levels vs the Battle Log prior; King 7; e16 vs Battle Log decks; opponent planner L11; 400/400, 0 errors):

  | opponent | exact − L11 [95% CI] |
  |---|---|
  | K4C-r16 | −0.01 [−0.12, +0.10] |
  | R3a | +0.03 [−0.04, +0.10] |
  | pooled | +0.01 [−0.055, +0.08] |

  - Null: keep live planning at L11.
  - Game wall times were exact median 145 s vs 163 s at L11. The worst exact game, 1182 s, was a cold export; the earlier 9x was cold exports.
  - Per decision, exact is 1.4–1.5x L11 (p50 78 vs 51 ms).
  - The run was on the pre-7fa5bbadd tree. The CARD LEAD's warm-up fix (7fa5bbadd: prebuilt exports, on-disk cache, bot.levels.warm) changes speed only, so there is nothing to rerun. Future exact-level evals use a tree at or after 7fa5bbadd, prewarmed.
- **LIVE-K4CW-r16** = wall_ms None, threads 1: 2 games, 241 decisions, 0 hits / 0 fallbacks.
- **Wide-vocab -res vs base** (our engine, L16 truth, L11 planner, s62, 100 paired per opponent):
  - **arch1** (synthetic archetype cores): pooled +0.105 [+0.040, +0.170]; vs K4CW 0.58 → 0.77; air +0.155, siege +0.135; no flagged cell.
  - **bl** (91 Battle Log decks): pooled +0.08 [+0.01, +0.15]; vs K4CW 0.55 → 0.71; R3a 0.94 → 0.94; no flagged cell.
  - The ~1850-trophy deck file was not delivered yet.
- **Value-net v1** (vpv1, value_pv.py; 776k states, 1822 sibling roots; 08 GPU, 9 min): FAILS.
  - Realized corr: d15 0.41, d30 0.33, d60 0.29, outcome 0.41; vn30 0.74.
  - Elixir (d30): own +0.0086 (63 % > 0), opponent −0.0057 (60 % < 0); sign gate fail.
  - Sibling pair accuracy: V 0.524 vs phi 0.546 vs search score 0.552 (357 held-out roots).
  - Not used as a teacher or for the rlfp1 critic. vpv1.npz sha256 04164f00febbec9d.
- **Sibling data:** keeps accumulating in the filler (LIVE-K4CW-r16 heavy since the overnight plan). Refit every few thousand roots.

## 2026-10-17T16:54:59Z — learned-leaf track PARKED; 03 down; mirror

- **03 down (~16:3xZ).** Its in-flight blocks were replaced with fresh-range MC blocks on 01/04/08.
  - Unavailable until 03 returns: ~3.1k MC roots, K1 shards 22/26/30/34/38/42 rows, sibling rows after ~09:20Z, and the mc0* fits.
  - Copies of leafgen and earlier sibling data are on 08 (vpvdata).
- **Mirror (bot/exit/mirror_out.sh, Sol-reviewed, ff6ae1c7b):**
  - Hourly plain rsync -a, no delete, into bot-mirror/<src>/ on the peer (01->04->08->01).
  - Running on 01/04/08 since 16:47Z.
- **MC sibling targets (mc_gen):** 16 continuations per sibling, common random numbers.
  - The targets work: phi/search agree with MC truth 0.65 overall, 0.75 beyond 2 SE, 0.80 beyond 3 SE (realized outcomes: 0.55).
  - The siblings barely differ: the median |dMC| 0.032 is about one SE (0.028).
- **No learned leaf beats phi at ranking siblings** (held out by game):

  | model | all pairs | beyond 2 SE |
  |---|---|---|
  | mc0 (aggregates) | 0.637 vs phi 0.649 | — |
  | mc0r (residual on phi) | 0.650 vs 0.650 | — |
  | mc0c (confident pairs only) | — | 0.733 / 0.719 vs 0.749 |
  | set0 (body-set DeepSets, residual, 10.3k roots) | 0.593 vs phi 0.612 / search 0.600 | 0.671 vs 0.743 / 0.729 (3 SE: 0.723 vs 0.801) |

  - Every fit early-stops at step 50-100.
  - Together with v0, v1 and fp2vn, the learned-leaf track is PARKED and the vl A/B is not run.
  - Unlaunched mc/sib/leaf filler lines were replaced by no-op lines (01 272, 04 145, 08 148). Data kept.

## 2026-10-17T16:57:43Z — PRE-REGISTERED: search compute-scaling curve (SCALE1), before any game

- **Bank:** SCALE1 base 3115842700769728 = int.from_bytes(os.urandom(6),'big')<<4, drawn on 127x01 at 2026-10-17T16:57:43Z (check_bank: disjoint).
  - Driver: bot.livediag.l16_cadence --decks dd1 (DD1 deck-diverse own decks; opponent deck = distinct Battle Log deck).
  - RoyaleSim 16.402, cards L16, King towers L16, noise clean.
  - Opponents LIVE-K4CW-r16 (wall_ms None) and R3a, 200 paired cases each.
  - Shards 0/2 on 127x01 and 1/2 on 127x04, same bank.
- **Arms** (serial twins, no wall clock, all -res-wint):
  - Stage 1: res-wint (K1, the live player), res-K2-wint, res-K4-wint, res-K2-T16-wint (refine width x2 at K2).
  - Stage 2 (conditional): res-K8-wint, only if stage 1 shows K4 - K2 > 0 vs LIVE-K4CW-r16.
- **Prediction:** K4 - K2 > 0 vs LIVE-K4CW-r16. If K4 ~ K2 (point <= 0 or CI clearly spanning 0 around 0), stop at K4 and skip K8.
- **Report:** per arm vs K1, paired delta with bootstrap 95% CI (dd1_report, per opponent and per own deck); enemy->decision
  p50/p90 and undefended share; decisions and CPU-s per game-second, so mean CPU-ms per decision = CPU-s / decisions.

## 2026-10-17T19:18Z — SCALE1 stage 1 RESULT; K8 launched (prediction held)

- **Run:**
  - 01 was thermally throttled (BOT LEAD: Tctl 95 C, ~720 MHz). 08 took over shard-0 cases with `--only`: x08a = R3a, even i 0–94; x08b = both opponents, even i 96–198.
  - The bot-deckopt2(-sam) helpers were copied to 08 at the same paths (rsync --ignore-existing).
  - 01's job was killed (own PGID) at 18:54Z, once its even i<96 K4CW rows had landed.
  - 1600/1600 games, 0 errors. The 117 rows that 01 and 08 both ran have identical command events and outcomes; only timing differs.
  - Rows: 04 /mpac/sdicks02/jobs/clasher/bot-fullpool/scale1-s1-x04, 08 scale1-s1-x08{a,b}, 01 scale1-s1-x01.
  - Local copies are under /mpac/sdicks02/jobs/clasher/bot-fullpool-scale1/. Readout: `bot/fullpool/scale_report.py` (CPU from 04/08 only).
- **Results:**

  | arm | score | Δ vs K1 [95% CI] | Δ vs K4CW | Δ vs R3a | CPU-ms/decision median / pooled |
  |---|---|---|---|---|---|
  | K1 res-wint | 0.772 | — | (0.665) | (0.880) | 338 / 370 |
  | K2 | 0.740 | −0.033 [−0.085, +0.020] | −0.070 [−0.155, +0.015] | +0.005 | 451 / 492 |
  | K4 | 0.823 | +0.050 [−0.003, +0.100] | +0.045 [−0.04, +0.13] | +0.055 [−0.005, +0.11] | 660 / 721 |
  | K2-T16 | 0.738 | −0.035 [−0.088, +0.015] | −0.085 [−0.17, 0.00] | +0.015 | 546 / 607 |

  - **Pre-registered gate:** K4−K2 vs K4CW = +0.115 [+0.025, +0.205]; pooled +0.083 [+0.03, +0.13]. Prediction held, so K8 runs.
  - **T×2 at K2:** −0.003 [−0.048, +0.043]. No gain from wider refinement.
  - **Reaction:** identical across arms (serial twins). Enemy play → decision p50 0.15 s, p90 0.9–1.15 s; enemy play → our play p50 1.5 s, p90 6.0–6.25 s.
  - **Undefended Giant-push share:** 4.3 / 4.1 / 6.1 / 4.5 %, about 300 pushes per arm.
- **Stage 2:** res-K8-wint on the same bank, launched 19:19Z.
  - 04: shard 0/2, PGID 359645. 08: odd i, both opponents, PGID 2054036. 28 workers each.
  - 04/08 fillers are temporarily at target 60 / SHED_LOAD 80. 01 filler stays at target 50 (standing ≤60; no deadline work on 01).
