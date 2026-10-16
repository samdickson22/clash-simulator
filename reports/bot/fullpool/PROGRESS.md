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
