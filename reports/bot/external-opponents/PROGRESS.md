# External opponents (rext-*): progress log

Task: external (RoyaleGym-org, MIT) opponents for the headline pool. Sub-agent of BOT LEAD. No ClashAI anything.
Steps: (1) survey shipped policies/checkpoints; (2) train RoyaleLearn PPO on X4S decks, wrap as rext-rlppo;
(3) smoke K4S-b64 vs each, 4 games + determinism repeat.

## Log
- 2026-10-14T04:31Z start on 127x05. Hosts: 03 at 96 python procs (cap 96 -> no new procs there now),
  04 93 procs (lead's eval), 08 100 procs, GPU idle (104 MiB).
- 2026-10-14T04:38Z SURVEY done: no pretrained policies/checkpoints anywhere in the RoyaleGym org (no GitHub release
  assets but wheels; RoyaleLearn/Imitate/Viser have no releases; HF has no RoyaleGym models; packages ship no weights).
  Only shipped baselines = RoyaleGym scripted opponents (already wrapped as rgym-*). FAQ: their own ladder bots are
  playable only via Discord 1v1, not downloadable. RoyaleBot (MIT) is a Nulls Royale client (rb-build.exe), no policy.
- learnvenv built on 08: /mpac/sdicks02/repos/clasher-bot-rsim/learnvenv (py3.12.12, torch 2.7.1+cu118, royalegym 0.1.24,
  royalelearn 0.5.18, royalesim 0.1.34, royaleimitate 0.2.13, nvidia-ml-py). CUDA on A6000 OK.
- new files: bot/players/rext_envs.py (build_env), bot/players/rext_train.py (Learner launcher). Env check: lvl-11 towers
  4824/3052, 6 elixir start, delay 27/27, 15.535.29 arms.
- dry run dry1 (4 workers) OK: ~1300 steps/s, env-bound.
- 2026-10-14T04:37:51Z LAUNCHED rlppo-r1 on 08: PID/PGID 1277650, log /mpac/sdicks02/jobs/clasher/bot-ext-train/rlppo-r1.log,
  save_dir /mpac/sdicks02/jobs/clasher/bot-ext-train/rlppo-r1 (resumable: re-run same cmd). 20 workers x 32 games,
  overlap, 32768 steps/update, ckpt every 2M, target 60M (stop by SIGINT to PID at ~3-3.5h wall -> saves).
  Cmd: cd /mpac/sdicks02/repos/clasher-bot && OMP_NUM_THREADS=4 nice -n 10 learnvenv/bin/python -m bot.players.rext_train
  --save-dir J --total-steps 60000000 --workers 20 --games-per-worker 32 --steps-per-update 32768 --checkpoint-every 2000000 --threads 4 --overlap
- r1 (launched 04:39:13Z, PID 1282643) STOPPED by SIGINT after 0.87M steps: PPO ppo_batch_size=steps_per_update (quickstart
  advice) = 2 Adam steps/update -> kl ~1e-6 (RoyaleLearn kl_dead alarm 19x), policy still uniform (entropy_norm 0.99996).
  Throughput 3200 steps/s, learner-bound (update 10 s / 33.6k steps). Kept as rlppo-r1 (checkpoint 582400), not used.
- 2026-10-14T04:44Z LAUNCHED rlppo-r2 on 08: same + --batch-size 4096 --epochs 2 (16 Adam steps/update), python -u.
  receipt /mpac/sdicks02/jobs/clasher/bot-ext-train/rlppo-r2.receipt.json, log /mpac/sdicks02/jobs/clasher/bot-ext-train/rlppo-r2.log. Resume = same command.
- bot/players/rext_policy.py (RextPolicyPlayer) written; vendor dir /mpac/sdicks02/repos/clasher-bot-rsim/rext-vendor
  (royalegym 0.1.24, royalelearn 0.5.18, pettingzoo 1.27.0, --no-deps) on 03 and 04; imports OK in our venv.
- 2026-10-14T04:51Z WRAPPER VERIFIED on 04: rext_check (5 X4S games, 1846 checks every 10 ticks): our match battle via
  SlotRemapBattle == RoyaleGym RustEngine reset with the same setup: identical BattleState, masks, obs both seats,
  state_hash equal. (RoyaleGym slot_of_k [[0,1,2],[0,2,1]] vs ours [[0,1,2],[0,1,2]] only changes state_json's red
  tower order -> remapped in the proxy.) rext-rlppo-r1 vs rgym-patient 3 games: 0 illegal, 0 frame mismatch, all OK.
- headline.py make_player: 'rext-<model>[-greedy]' -> RextPolicyPlayer(MODELS/<model>) (synced to 03/04).
- plumbing smoke (r1 untrained model) on 04: K4S-b64 vs rext-rlppo-r1, 4 games x 2 reps -> 4/4 wins, identical hashes.
  out /mpac/sdicks02/jobs/clasher/bot-ext-smoke/plumb-r1-{a,b}. NOTE 04 needs no ROYALEGYM_SRC for rext (vendor dir).
- bot/players/rext_eval.py (royalegym.evaluate vs its ladder, learnvenv) tested on 08: ~5 s/game.
NEXT: at ~07:45-08:15Z SIGINT r2 trainer (verify PID from receipt), copy r2/bot -> rext-models/rlppo on 03+04,
  eval checkpoints vs ladder (rext_eval, 6 procs on 08), final smoke 4 games x2 into bot-ext-smoke/, write NOTES.md.
- 2026-10-14T04:55Z BOT LEAD: 04 now mine too (<=24 GB GPU, <=36 procs). learnvenv built on 04 (same pins).
  rext_train.py gained --channels/--blocks/--policy-lr/--critic-lr/--ent-coef/--vram-fraction (defaults = r2's).
- 2026-10-14T04:52:36Z LAUNCHED rlppo-r3 on 04: PID/PGID 1777427, /mpac/sdicks02/jobs/clasher/bot-ext-train/rlppo-r3(.log,.receipt.json).
  Config: RoyaleLearn default net (32ch x 2 blocks, cheaper update), 32 workers x 32 games (35 procs), 65536 steps/update,
  batch 2048 x 3 epochs (96 Adam steps/update), lr 5e-4/5e-4, entropy = RoyaleLearn default schedule, opponent self,
  overlap, vram_fraction 0.45, ckpt every 4M, target 100M. Resume = same command (see receipt dir rext_train_args.json).
  Early: 5800 steps/s, kl 3e-4 (r2: 1e-5..6e-5), GPU 6.5 GB.
PLAN: stop both ~08:00Z by SIGINT to receipt PIDs; eval checkpoint series of both vs RoyaleGym ladder (rext_eval);
  pick better -> rext-models/rlppo; cross-copy checkpoints 04<->08 into /mpac/sdicks02/jobs/clasher/bot-ext-train/mirror-<host>/.
- ~05:38Z FINDINGS: (a) RoyaleLearn's gate = 1000 games (eval_seed_count 500 x 2 seats) on 2 eval workers, run every 1M env
  steps (Learner's 'self' setting; LadderConfig default is 4M): r3 gate 2 took 1327 s; >50% of wall in gates.
  (b) opponent='self' scripted share = only noop + random_legal (LadderConfig default).
  (c) UPSTREAM BUG royalelearn 0.5.18: eval workers cache snapshots/index.json at start -> gate vs a later snapshot
  raises KeyError("no snapshot 'snap:v2'") and kills the run. r3 DIED of it at ~4.5M steps (no checkpoint yet; snapshots
  v0-v2 kept). Workaround in rext_envs.py (_patch_snapshot_index: re-read index on miss; every worker imports env_fn).
- r2 STOPPED (2x SIGINT 05:40-05:44Z, stuck in a 1000-game gate) at 2.99M steps; no checkpoint, snapshots v0,v1 kept.
  Curves in rlppo-r2/metrics.jsonl. r3 curves in rlppo-r3/metrics.jsonl.
- rext_train.py gained --eval-workers --candidate-every --gate-games --all-scripted.
- 2026-10-14T05:42:22Z LAUNCHED rlppo-r4 on 04 (PID/PGID 1950217): r3's PPO config (32ch x 2, batch 2048 x 3 ep, lr 5e-4,
  default entropy schedule) + league fixes: all six RoyaleGym scripted rungs in the scripted share, gate every 4M env
  steps with 200 games, 10 eval workers; 23 rollout workers x 32; ckpt every 2M env steps; vram 0.45. ~6200 steps/s.
- 2026-10-14T05:45:01Z LAUNCHED rlppo-r5 on 08 (PID/PGID 1527125): 64ch x 4 net, batch 4096 x 3 ep (48 Adam steps/update),
  lr 3e-4, same league fixes, 32 workers + 12 eval workers, vram 0.5. ~2300 steps/s (update 28 s / 66k).
  Both: same command resumes (args in <save_dir>/rext_train_args.json). Stop target ~08:45Z.
