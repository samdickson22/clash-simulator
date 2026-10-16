# Full-pool learned components: progress (resumable)

Worker for BOT LEAD (Opus, code). Worktree 05:/mpac/sdicks02/repos/clasher-bot-fullpool (branch bot/fullpool from origin/main).
Scratch: 05:/mpac/sdicks02/jobs/clasher/bot-fullpool/ (ckpt/ = RL r5 v10 copy from 04, sha e188e2ae…; lopp-models/ = 04's
bot-lopp-models). Heavy runs only on 03/04/08 via bot/exit/cpu_job.sh, nothing on 01. Rule (Sam 10-16): no sealing or
release windows; every result reported as soon as it exists.

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
