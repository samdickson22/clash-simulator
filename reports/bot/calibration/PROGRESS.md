# Engine calibration batch 1: progress (resumable)

Owner: calibration sub-agent of BOT LEAD. Worktree 127x05 /mpac/sdicks02/repos/clasher-bot (bot/lead, HEAD a4a4a97bf, no commits).
Work dir: 127x05 /mpac/sdicks02/jobs/clasher/bot-calib-r1/ (harness.sh OUTNAME [workers]; tools/).
Hosts: 03/04/08 each already at 91-98 of my python procs (cap 96) at 04:39Z 10-14, so harness runs on 05
(load ~2, 128 threads; worktree host). Fixtures copied 04 -> 05 /mpac/sdicks02/repos/clasher-bot-data (split sha 3edbd25b…5258 checked).

## Log
- Baseline rerun on 05 matched r2 train headline (50.7) but 95/577 fixtures differed run to run: BattleState.rng
  is an unseeded random.Random() used by Arrows volley jitter / radial spell spreads (spells.py:382,424).
  Fix (harness only): bot/fidelity/engines.py OursEngine.reset seeds b.rng.seed(0). Two seeded runs: 0/577 differ.
  Reference baseline = base-s0 (train no-tower ≤¼ 50.72, HP 64.97). RNG noise between unseeded runs: ±0.1 pp overall, ≤0.3 pp/card.
- Gate tool: bot/fidelity/compare_runs.py BASE NEW --split train (ACCEPT/REJECT).

## Status
| # | change | state | out dir |
|---|---|---|---|
| 1 | spirit HP | ACCEPTED (LOO+live) | c1L |
| 2 | lane-2 mirror 5/6/15 | ACCEPTED (LOO+live) | c2L (new baseline; *L dirs carry live view) |
| 3 | Goblinstein formation | ACCEPTED (live strict; LOO) | c3L-goblinstein (new baseline) |
| 4 | hut first spawn (4a furnace, 4b goblin hut) | ACCEPTED (4a live strict; 4b final rule) | c4a-furnace, c4b2-hutradius (new baseline) |
| 5 | Miner (5a snap, 5b route, 5c emergence targetable, 5d tunnel end) | ACCEPTED (5b only with 5c) | c5a, c5b (rejected alone), c5c, c5d-minerend = FINAL |
| 6 | Rust parity | DONE: 427/577 full parity vs HEAD 429/577; 4 new edge cases (untouched code) | parity577-*.jsonl |
| 7 | runtime r2 plan | written (RUNTIME-R2-PLAN.md); r1 untouched | |
- Live view added (run.py res["live"]: score only up to our game end). Reran base/c1/c2 as baseL/c1L/c2L: standard
  numbers identical to base-s0/c1-spirithp/c2-lane2mirror (0/577 differ). Code states saved in states/<name>/.
- Accept rule: strict gate, or failing cards pass under both LOO and live (and live passes the full gate).
- Python side FINAL = c5d-minerend (states/c5 + pathfinding/miner/battle edits). Tests: tests/test_calibration_batch1.py (22).
- Rust: 04 copy /mpac/sdicks02/repos/clasher-bot-calib (calibrated) and -calib-head (HEAD); build via
  jobs/.../bot-calib-r1/build.sh (CARGO_TARGET_DIR jobs/.../cargo-target). Built .so copies: jobs/.../so-{cal,head,r1}.
  Rust edits: engine-rs/src/{astar,c56,lib,spawn}.rs; engine-rs/differential.py (mirror_x 5/6/15, skip_deploy_snap,
  tunnel_path). Parity tool: bot/fidelity/rs_parity.py (+ rs_parity_debug.py). r1 native == HEAD build (120/120 same).
- Full pytest: shards in jobs/.../pytest-cur2 (calibrated) vs pytest-head (HEAD export /tmp/sdicks02/headtree); diff failed.txt.
- NOTE: 04 python-proc count fluctuates (other jobs); size workers = 96 - current count before launching.
- DONE 2026-10-14: all batch-1 items accepted; final = c5d-minerend; Rust parity 427/577 (HEAD 429); tests updated (BATCH1 §7);
  runtime r2 plan written. No commits/pushes. Next candidates: BarbLog Barbarian HP 270->280 (native 716), Ghost movement/reveal,
  hut spear offsets, remaining Goblinstein gap, Miner freeze/retarget, IceGolemite Python<->Rust mismatch (pre-existing).

# Batch 2 (sub-agent bot-lead-calib-batch2-r1): progress (resumable)

Started 2026-10-14T06:46Z. Edits only in the 05 worktree; NOTHING runs on 05. Compute on 127x03 (04 at ~94 procs, 08 >96).
Job dir (05 = scripts, 03 = trees/runs): /mpac/sdicks02/jobs/clasher/bot-calib2-r1/
- snap.sh NAME [HOST]: rsync worktree (src bot engine-rs tests gamedata/decks/hitboxes + es_common) to 03 trees/NAME; prints engine md5.
- harness.sh TREE OUT [W] (on 03): 577-fixture harness from the isolated tree -> runs/OUT.  build.sh TREE: Rust .so into the tree
  (CARGO_TARGET_DIR jobs/.../bot-calib2-r1/cargo-target).  parity_all.sh TREE NAME [W]: rs_parity 577 -> runs/parity-NAME.jsonl.
- tools/pdbg.py (lockstep Py/Rust per-entity state dump), tools/pywatch.py (stack on attribute change).
- Baseline cal1 = batch-1 final: harness reproduces bot-calib-verify (04) in 0/577 differing fixtures; Rust build == so-cal (3a4ed1ea).

## Log
- Task 1 (Rust parity): the 4 new divergences are two pre-existing Rust gaps exposed by changed trajectories:
  (a) Princess/Firecracker "extra projectile": a distance-discarded hit (attacker pushed >1.5 tiles past reach) left the Rust
      cooldown at ~0 (then floor 0.3 = first) while Python _complete_attack_clock_cycle(discarded=True) installs the full
      interval (unless LoadFirstHit). Fix lib.rs cancel branch + stats.discard_keeps_load (differential.py).
  (b) "43-damage hit" = Inferno Tower, not Firecracker: lock change to an in-range target after the old target died while
      stunned. Python _note_combat_target resets (retarget_time 0.8) for any non-crown cooldown weapon; Rust only for Troops.
      Fix: Rust retarget clause also covers non-crown Buildings.
  Tree p2 fixes all 6 (incl. HEAD's 1141 Firecracker). Full 577 parity for p2 running (runs/parity-p2.jsonl).
- Batch 2 c6 BarbLog Barbarian HP 270->280 (6 non-EV paths, gamedata only): harness runs/c6-barbhp running.
- Research helpers (Opus, T3 delegate_task, read-only on worktree, own trees r-ghost/r-huts/r-swarm on 03, <=8 procs each):
  ghost, huts(+spear offsets, furnace, Goblinstein), swarm. Brief: jobs/.../bot-calib2-r1/RESEARCH-BRIEF.md.
- 06:53Z Task 1 DONE. Tree p3 (= c6 engine + Rust fixes a,b + differential.py IceGolem alias):
  **572/577** full digest parity (HEAD 429, batch-1 427). The IceGolemite class (139) was a harness artifact: fixtures name
  the card 'IceGolemite' but differential.config only exported the death area for the C56 alias 'IceGolem' (the planner's
  CARDS use 'IceGolem', so the planner was never affected). Remaining 5 (Princess 0714, Projectile 0795, Tesla 1020, Ghost
  1157 target-during-knockback, RoyalHogs 1226) are identical with HEAD engine + alias fix (tree head-ig) => pre-existing.
- c6 BarbLog HP: ACCEPT strict both views: train ≤¼ 62.26->62.53, HP 71.98->73.69 (BarbLog HP exact 0->73.3); live ACCEPT.
  test tests/test_calibration_batch2.py (fails on cal1, passes on c6). bot/players/runtime.py: PIN_SETS r1/r2 +
  CLASHER_BOT_RUNTIME_PINS (r2 native pin placeholder until the final build).
- 07:18Z Own survey (tools/shot_survey.py + shot_match.py, train): native projectile launches (4M-range object ids with
  card_id) vs ours, per card. First shot of each burst is exact (within the native sampling window) for 65-72% of
  Archers/Minions/GoblinGang/Blowdart/Princess/Musketeer/BabyDragon, no systematic offset => ranged-unit divergence is
  cascade, no single timing rule. Log/BarbLog/RoyalDelivery offsets are representation (ours holds the rolling log /
  delivery object from the deploy tick; first motion/recruit spawn tick match). Firecracker shot-2 after retarget sometimes
  ~5-10 ticks later natively (not a clean rule; not changed).
- Eval tree (isolated) 03 /mpac/sdicks02/jobs/clasher/bot-calib2-eval/tree (bot/ + reports/explore/x4s from the worktree);
  hl.sh RUNTIME ENGINE OUT W. r1-rsim (K4S-st vs R3a,v1 x300): 600/600 games, command_sha256 identical to the original
  bot-search-rsim-st run on all 600 (R3a 0.723, v1 0.890). r1-ours running.
- 07:36Z r1-ours: 600/600, sha identical to bot-search-bc on all 600 (R3a 0.720, v1 0.860).
- Interim runtime int1 (batch1 + c6 + Rust fixes; NOT the final r2): stage_runtime.sh int1 (05) + make_runtime.sh int1
  /mpac/sdicks02/jobs/clasher/bot-calib2-eval/rt-int1 (03): r1 copy + 12-file diff (base md5 == r1 checked), native
  64676589 (== tree p3 build). Eval-tree runtime.py r2 pin set to 64676589 for the interim (worktree keeps placeholder).
  hl2.sh ROOT PINS ENGINE OUT W. int1-rsim running (30 workers; 03 shared with another agent's 46-proc headline job).
  NOTE detach.sh prints a stale receipt if the file exists: rm the receipt before relaunching.
- 08:05Z r1 native recipe found: engine-rs + reports/explore/e1/stage_native.py (adds NativeScripts.rollout_e1, needed by
  K4S) + features extension-module,gil-release, --locked, no RUSTFLAGS: build_e1.sh reproduces 44874fd6 byte-for-byte from
  r1/engine-rs. make_runtime.sh now uses it. (First int1 build without E1 failed every game: no rollout_e1.)
  int1 native = bd847fd0 (eval-tree pin updated). int1-rsim DONE: r2int−r1 R3a −0.017 [−0.070,+0.033], v1 +0.007
  [−0.037,+0.050], both −0.005 [−0.038,+0.028]; identical games 50/600; CPU/game 49.5->61.0 (R3a; load differs).
  int1-ours launched (40 workers).
- 08:27Z ACCEPTED so far (worktree): c6 BarbLog HP; c7 Ghost (helper; independent rerun == helper run 0/577 diff);
  c8 side-1 back-row bound (swarm helper); c10-ac = c8 + huts (a) spear-goblin aim + (c) Goblinstein doctor damage 36->53.
  REJECTED: huts (b) FirespiritHut 1500 forward spawn (standard overall ≤¼ −0.24, HP −0.55 vs c9a; reverted).
  Train no-tower ≤¼: cal1 62.26 -> c6 62.53 -> c7 66.06 -> c8 66.61 -> c10-ac 68.00 (HP 71.98 -> 76.90).
  Rust: Ghost port (helper draft), back-edge port, spear-goblin aim port (spawn.rs State facing/target, spawn_snapshot.py),
  Inferno building acquisition preload keyed on last_target (fixes 0804 re-break). Parity c8 571 (0804 broke); c10r2 running.
  Barbarian 691->716 updated in 5 more tests (test_enabled_*, test_torch_simple_*); 4 failures there are pre-existing (cal1).
- 08:45Z Parity c10r2 (all Rust ports): 572/577, classes identical to p3 (5 pre-existing). E1 runtime build of the same
  source (rt-c10 native 51e6f700) == plain build on 64/64 validation fixtures (same first mismatch/ticks).
  int1-ours DONE: R3a +0.047 [−0.003,+0.100], v1 −0.013 [−0.060,+0.033], both +0.017 [−0.018,+0.053].
  rt-c10 (candidate r2 = c10 engine; eval pin 51e6f700): c10-rsim DONE: R3a −0.023 [−0.077,+0.027], v1 −0.010
  [−0.053,+0.033], both −0.017 [−0.050,+0.017]. Running: c10-ours; r1-rsim-x (extra cases 300-899, power).
  Round-2 research helpers launched: towers, cards (baseline runs/c10-ac).
- 09:46Z c10-ours DONE: R3a +0.040 [−0.010,+0.093], v1 +0.017 [−0.033,+0.063], both +0.028 [−0.005,+0.063].
  Extension cases 300-899 in RoyaleSim (r1-rsim-x, c10-rsim-x, 1200 games each): both −0.010 [−0.034,+0.014].
  Pooled 0-899 (1800 paired games): R3a −0.008 [−0.040,+0.022], v1 −0.017 [−0.043,+0.009], both −0.012 [−0.033,+0.007].
  Planner latency: RoyaleSim CPU per 1000 ticks r1 12.14 vs c10 11.61 (planner not slower). Our engine: Python sim
  ~25% slower with c10 (Ghost now A*-routes); cpu_seconds there includes the game engine.
  engine-rs/test_stage4_spawners.py: 4 subtests asserted pre-batch-1 hut timings (failed since batch 1, missed then);
  updated to the measured rules (births 39/139/239; wake fires due wave; idle clock capped) -> pass.
- 09:55Z Round-2 cards helper: A Rascals summonDeployDelay 100 (strict ACCEPT), B Firecracker recoil = ordinary clock +
  reset_hit_on_movement (ACCEPT final rule on top of A). Applied -> c11-cards; independent rerun == helper cards-ab (0/577).
  Train ≤¼ 68.00 -> 69.97, HP 76.90 -> 78.59. Rust: projectiles.rs recoil push_reset=true.
  Parity c11 571 (new fixture 1147 in the pre-existing Tesla class). Root cause (also of HEAD's 1020): Python Tesla hide clock
  runs at the movement scale (slow_multiplier, movement buff); Rust hide_tick used attack_work. Fixed (c11r2): both pass.
  Full c11r2 parity pending: 03 has 107 procs of another agent's headline jobs (bot-headline-stD-*); 04 106, 08 101 -> waiting.
- 11:13Z Round-2 towers helper: (a) WallBreakers 137->110, (b) Miner emergence on arrival tick, (d) projectile-spawn full
  deploy tick, (c) Poison crown 22: all ACCEPTED re-gated on c11 sequentially (order a,b,d,c; c before d failed strict
  HP by −0.00003 pp from one fixture, after d it changes no unit tick). FINAL engine = c12-spawn (worktree):
  train ≤¼ 72.26 / HP 80.51; validation 66.37 -> 74.48 (paired +7.21 [+4.44,+10.08]); all 577 72.48 / 80.56.
  Runtime r2 BUILT: /mpac/sdicks02/repos/clasher-bot-runtime/r2 (03), native c50cb066 (E1 recipe), sources == tree c12r.
  runtime.py r2 pin = c50cb066. (A first make_runtime attempt copied r1->r2 without the diff because staging aborted on a
  stray lib.rs.orig and the script didn't stop; that r2 was deleted before use, the script now checks the manifest.)
  Tests: 822 passed; failures only the 4 pre-existing; Poison 21->22, BarbLog/RoyalDelivery spawn-tick deploy tests
  updated. engine-rs: 36 passed. Running: r2-rsim (0-899), c12r parity.
- 12:12Z DONE. Final parity (tree c12r == r2 sources): 574/577 (HEAD 429), classes ⊂ HEAD (Projectile 0795, Ghost 1157,
  RoyalHogs 1226). KEY TEST (R2-AB.md): RoyaleSim r2−r1 both −0.005 [−0.038,+0.028] on HEADLINE cases 0-299; −0.010
  [−0.031,+0.010] on 1800 games (0-899); ours +0.028 [−0.008,+0.065]. Equal-load latency r2/r1 +4.6% CPU/1000 ticks.
  r2 marked read-only (chmod -R a-w). No commits/pushes. Helpers (5 Opus research tasks) all finished; nothing running.
