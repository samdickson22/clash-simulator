# External opponents round 2 (rext-bc, rext-bcppo): progress log

Task (BOT LEAD sub-agent, exploration tier): RoyaleImitate BC on IL_Replay human games -> rext-bc; RoyaleLearn PPO
fine-tune from it (warm start + KL anchor) on our 5 X4S decks -> rext-bcppo; wrap as Players; eval vs RoyaleGym
scripted ladder, vs rext-rlppo, K4S-st and v1 vs each (HEADLINE bank, rsim15535). No ClashAI anything. No commits.
Hosts: 04 (GPU <=24 GB, procs <=110 total), 08 (same), 03 CPU. Never 05. Job dirs /mpac/sdicks02/jobs/clasher/bot-ext2-*.

## Log
- 2026-10-14T09:11Z start. 03 at 145 python procs (over cap -> unusable), 08 at 110 (full), 04 at 74.
- royaleimitate 0.2.13 reads IL_Replay's own replays/*.parquet (payload_json); local copy (03 clasher-local-data,
  HF rev 059d43a0) copied to 04:/mpac/sdicks02/jobs/clasher/bot-ext2-data/il_replay (788 MB). pyarrow 26.0.0 added to
  learnvenv on 04+08 (needed by royaleimitate replays).
- Data stats (first 2 parts, 10k matches): 83% replayable by catalogue; both decks in C56 2.8%, one deck 25.6%;
  X4S decks exactly: 6.7% of seats (bridge 322, siege 164, bait 174, chip 8, beatdown 0).
- New files: bot/players/rext_imitate_replays.py (stats/replay/merge), rext_imitate_clone.py, rext_imitate_ppo.py.
- Replay variants under our engine delay 27/27 (50 matches, c56any): stock royaleimitate replay keeps only ~18% of
  attempted matches (refused plays: card not back in hand / slot pending). Retry (refused play waits <=6 decisions)
  keeps 86%, 4% of plays delayed. Shift -27 ticks is worse. -> shift 0, retry 6.
- 2026-10-14T09:21:09Z LAUNCHED demos-r1 on 04 (PID/PGID 2710345): 24 workers x 400 matches, scope c56any
  (rows of C56-deck seats only), noop-keep 0.25 (weight 4), then merge. Out /mpac/sdicks02/jobs/clasher/bot-ext2-data/demos-r1
  (merged/<engine key>/), log demos-r1.log, per-worker demos-r1.w<i>.log. Script bot-ext2-data/replay_all.sh.
- 09:24Z COORDINATOR RULING (binding): IL_Replay = INTERNAL EVALUATION ONLY (IL_REPLAY-LICENSE.md). Data, derived
  shards and rext-bc/bcppo weights live only under /mpac/sdicks02/jobs/clasher/bot-ext2-*/ (never the worktree);
  wrappers load from /mpac/sdicks02/jobs/clasher/bot-ext2-models/; reports disclose the source.
- PPO plumbing dry run (04, bot-ext2-train/dry1, 50-match test clone): warm_start + reference_kl OK (imitation/clone/* metrics).
- 09:24:01Z demos-r2 (PID 2720637): same, --first-part 24 (parquet parts 24..51, disjoint from r1's 0..23).
- Both done 09:28Z: 19,200 matches (C56-deck seats), 2,894,949 rows (140,800 validation): 820,412 play rows,
  2,074,537 kept no-ops (w=4), 6,222,949 dropped; replay skips: 42,502 out of scope, 8,916 card not in catalogue,
  639 not 8-card, 2,808 refused after retries; 51,775 plays (6.3%) waited 1-6 decisions.
  merged: bot-ext2-data/demos-all/merged/090cad9bbbea1acc (symlinks to demos-r1/r2 parts).
- 09:28:38Z LAUNCHED bc-r1 on 04 (PID/PGID 2737874): rext_imitate_clone, batch 1024, lr 5e-4, <=12 epochs, patience 2,
  packed rows in memory (41.5 GB) -> /mpac/sdicks02/jobs/clasher/bot-ext2-models/bc-r1; log bot-ext2-data/bc-r1.log.
  Epoch 1 packs while it trains (~1 GB/min -> ~40 min); later epochs from memory.
  Not resumable mid-way: relaunch = rm -rf bc-r1 and same command.
- headline.py make_player: rext-bc*/rext-bcppo* -> RextPolicyPlayer(/mpac/sdicks02/jobs/clasher/bot-ext2-models/<name>)
  (env REXT_EXT2_MODELS overrides). Synced to 04+08 (host copies differed only by this edit).
- Ladder eval script: 04:/mpac/sdicks02/jobs/clasher/bot-ext2-eval/run_evalset.sh MODEL TAG [GAMES] (learnvenv CPU).
NEXT: bc-r1 done -> ladder eval (40/rung) + launch PPO bcppo-r1 on 04 (r4 config + warm start + KL anchor 0.1).
- 10:44Z bc-r1 DONE: 12 epochs, validation NLL 0.7057 -> 0.6356 (best = last), digest 29876dfe60518ae2...;
  folder /mpac/sdicks02/jobs/clasher/bot-ext2-models/bc-r1, copied to 03/04/08; installed as .../bot-ext2-models/bc
  (actor sha256 prefix 385af5123b631c81) = rext-bc.
- Smoke on 04 (bot-ext2-eval/smoke-bc-a): v1 vs rext-bc 4/4 v1 wins; rext-bc plays 25-31 cards/game, all accepted.
- Ladder (100/rung) rext-bc: noop .995 random .85 first-aff .76 defend .80 push .72 patient .69 -> mean5 0.764 (rlppo 0.576).
- PPO attempts on 08: bcppo-r1 (10:44Z) and bcppo-r2 (+policy_head_float32, 10:47Z) died at update 5 on RoyaleLearn's
  ratio invariant (0.0056/0.0059 > tf32 tol 0.005: peaked cloned actor under TF32 GPU convs vs CPU rollouts);
  bcppo-r3 (+no TF32) failed the warm-start probe self-test (2.8e-5 > 1e-5: probes recorded under TF32).
- 10:53:29Z LAUNCHED bcppo-r4 on 08 (PID/PGID 2603063): rext_imitate_ppo r4 config + warm start bc-r1 + freeze 1M env
  steps + reference_kl(clone) budget 0.1 coef 1.0, policy_head_float32, TF32 off, self_test_atol 1e-4, 22 workers x 32,
  8 eval workers, overlap, vram 0.45. ~3.7k steps/s. Run dir /mpac/sdicks02/jobs/clasher/bot-ext2-train/bcppo-r4,
  log bcppo-r4.log. Resume = same command (args in rext_imitate_ppo_args.json). Stop by SIGINT to PID ~13:15Z.
  Mirror: 08 mirror.sh (PID in mirror-r4.receipt.json) copies to 04:bot-ext2-train/mirror-127x08/ hourly.
  NOTE 08 proc count: raw `grep -c python` was 102-110 because ~70 are <defunct> zombies of the ExIt agent's pools
  (parents bot.exit.generate / bot.eval.headline); live python ~74 before my 31.
- 10:58:59Z 03 bc-batch (PID 3714686): headline K4S-st vs rext-bc, then v1 vs rext-bc, 300 games, 40 workers
  -> 03:/mpac/sdicks02/jobs/clasher/bot-ext2-eval/hl-{st,v1}-vs-bc(.summary.md). Script bot-ext2-eval/headline.sh.
- 10:59:16Z 04 h2h rext-bc vs rext-rlppo (royalegym.evaluate, 4x50 games) -> 04:bot-ext2-eval/results/h2h-bc-vs-rlppo-s*.json.
- 11:05:22Z 04 cycle.sh (PID 3125933): every 40 min pulls newest bcppo-r4 checkpoint from 08 -> 04:bot-ext2-eval/ckpts/r4,
  ladder eval 40/rung -> results/r4-ck<step>-*.json.
- Results so far (HEADLINE bank, rsim15535, 300 games): K4S-st vs rext-bc 0.833 [0.790, 0.877]; v1 vs rext-bc 0.583
  [0.527, 0.640]; K4S-st vs rext-rlppo 1.000; v1 vs rext-rlppo 0.727 [0.673, 0.777]. rext-bc vs rext-rlppo
  (royalegym.evaluate, 200 games) 152-48 = 0.76. NOTES-2.md drafted (sections 4/6 pending).
- 11:2xZ bcppo-r4 at ~4.3M steps, 2.8k steps/s; KL(clone) ~0.08 vs budget 0.1; lr backoff to 1.25e-4. 04 at 109 live
  procs (others' evals) -> no second PPO variant.
- 11:51Z r4 ckpt 6.12M ladder (40/rung): random .95 first-aff .80 defend .725 push .75 patient .725 -> mean5 0.79.
  h2h vs rext-bc (03, 4x50): 106-94 = 0.53. metrics at 10M steps: KL(clone) 0.14 (lambda 0.088, in band), entropy_norm
  0.19, noop rate 0.90, EV 0.90, lr 1e-4 (backoff). Only gate record snap-v0 so far.
  03 h2h tool: bot-ext2-eval/h2h03.sh A B TAG [BLOCKS] [GAMES] (rsim .venv + PYTHONPATH).
PLAN: SIGINT bcppo-r4 (PID 2603063 on 08) at ~13:20Z -> bot/ saved; install as bot-ext2-models/bcppo on 03/04/08;
  finals: ladder 100/rung (04), h2h bcppo vs bc and vs rlppo (03), headline K4S-st and v1 vs rext-bcppo 300 (03).
- 13:18Z bcppo-r4 STOPPED by SIGINT (PID 2603063, verified): 24.1M decisions / 16.06M env steps, final checkpoint
  000016055424 + bot/ saved; mirrored to 04 (final 13:17:40Z). Installed bot-ext2-models/bcppo on 03/04/08
  (actor sha256 5e1bef59bc9cab87...). Gates: v1 0.52, v2 0.525 vs v0 (clone), not promoted.
- Finals: ladder bcppo (100/rung, 08) mean5 0.760; h2h (08) bcppo vs bc 206-194, bcppo vs rlppo 139-61;
  headline (04) K4S-st vs rext-bcppo 0.933 [0.903, 0.960], v1 vs rext-bcppo 0.480 [0.423, 0.537].
  Paired bc->bcppo: K4S-st +0.100 [+0.053, +0.143], v1 -0.103 [-0.167, -0.040].
- 13:40Z DONE. NOTES-2.md complete. No processes of mine left on 03/04/08 (checked). Nothing committed.
