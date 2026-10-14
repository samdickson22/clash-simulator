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
