# Oracle planner qualification: running log

Task: qualify `FixedDepthThompsonOracle` as a PLAYER on the admitted simulator and measure cost.
No fitting, no labels, no distillation. Only evaluation games.

Rules: never git reset/clean/stash/commit; never edit runtime-snapshots/ or pilot kits; kill only
own PIDs; at most 5 workers under `nice -n 10`; watch `sysctl vm.swapusage` (back off > ~14 GB).

Runtime: `reports/strategy_council_20260928/m0/runtime-snapshots/pilot-runtime-v4` (has pilot-runtime.json).

## Files (all in this directory)

- `oq_lib.py`: harness. `play_game(ctx, spec)` mirrors `clasher.rl.eval.evaluate` (paired seats,
  matchup_seed = seed + (game//2)*1009, seat = game%2, decks via `_sample_paired_ordered_decks`,
  public-script opponent on the council public packet, decision interval 5, max ticks 6001).
  `RolloutLeafOracle` = my subclass with the Supercell-style no-more-deploys leaf.
- `oq_check_harness.py`: replays pilot diagnostic games of the seed-2903 1M checkpoint through the
  harness; 6/6 games reproduce the pilot `.games.json` exactly (outcome, ticks, tower HP). PASS.
- `oq_cost.py` -> `cost/cost.json` (engine ticks/s, clone cost, planner seconds per decision).
- `batches.json`: player configs + batches (cells, game ranges). Cell seeds = pilot diagnostic seeds.
- `oq_run.py <batch> [<batch>...]`: resumable worker. Per-game JSON in `games/<player>/<id>.json`,
  O_EXCL claim files (`.claim`, hold the PID; claims of dead PIDs are taken over). `touch STOP` in
  this directory makes workers exit after their current game.
- `oq_probe.py <player> <role> <style> <game> <max_tick>`: prints the actions of a short game.
- `oq_report.py` (to write): aggregates games/ into tables.

## Exact launch command (one process = one worker; at most 5)

```
OQ=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/oracle-qualification
RT=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/runtime-snapshots/pilot-runtime-v4
cd $RT && CLASHER_ROOT=$RT PYTHONPATH=$RT/src:$RT/scripts:$OQ PYTHONDONTWRITEBYTECODE=1 \
  nohup nice -n 10 $RT/.venv/bin/python -B $OQ/oq_run.py <batch> [<batch>...] \
  > $OQ/logs/worker-$(date +%H%M%S)-$RANDOM.log 2>&1 &
```

Restarting is safe: finished games are skipped, dead claims are reclaimed.

## Log

- 2026-10-01 13:08 session 1: read CLAUDE.md, AGENTS.md, environments/AGENTS.md, amendment,
  strategy.md oracle section, ml-research-20261001.md. Runtime v4 confirmed. Planner source in the
  snapshot is byte-identical to src/clasher/rl/oracle_planner.py in the working tree.
- 13:12 harness parity check PASS (6/6 pilot games reproduced exactly).
- 13:14 cost benchmark started (PID 51064, `oq_cost.py`, log logs/cost.log). Early numbers: clone
  ~0.95 ms; engine ~3050 ticks/s no deploys, ~1520 ticks/s with random deploys; default planner
  1.33 s/decision; legacy 0.54; greedy1 0.17; rollout d1 s32 leaf200 2.2 s.
- 13:19 launched 4 workers: PIDs 55731 (controls pilot), 55740, 55754, 55763 (pilot controls).
  Observation: a spamming planner is only "playable" ~60-150 decisions per game, so games are
  minutes, not tens of minutes.

- 13:56 cost benchmark finished (cost/cost.json). Supercell-like d50 x 0.5 s: 0.45 s per simulation.
- 14:04 controls done: noop 0/192, random96 4/192 (games/noop, games/random96; 32 per cell, 6 cells).
- 14:05 root-bandit diagnostic (oq_diag.py -> cost/diag.json): stock default returns an UNVISITED
  action in 45% of root decisions; leaf value spread over arms 0.005.
- 14:12 pilot done (12 games each, holdout, games 0-3 of each style): default 0/12, greedy1 0/12,
  legacy 5/12, roll_raw 7/12, roll_ctr 5/12. (1M checkpoint on the same 12 games: 6/12.)
- Finding: the engine legal mask is a superset of the learner's public action mask (about 7-10% of
  planner/random placements are outside it, all accepted by the engine). Screen players therefore
  use `mask_public: true` (root candidates = engine-legal AND public mask).
- 14:09 PRE-REGISTERED SCREEN: players legacy_pm and roll_pm. 64-game screen per deck role =
  pilot-cell games 0-21 vs balanced, 0-21 vs pressure, 0-19 vs defense (paired seats, pilot
  diagnostic seeds). Pass = pooled match score >= 0.55 AND matchup-bootstrap 95% lower bound > 0.5.
  Also reported: the same vs the strongest script alone (defense: fewest wins for every pilot
  policy), and paired difference vs the seed-2903 1M checkpoint on identical matchups/seats.
  Games 22-31 (batches ext_h, ext_g) complete the pilot's 32-per-cell cells and are reported
  separately as the 96-game extension.
- 14:09 launched 5 workers PIDs 87121 87130 87134 87138 87141 with batches
  `screen_h pilot2 screen_g ext_h ext_g default_h` (in that priority order).

- 14:20 pilot games vs the defense script: rollout planners reach 0-0 at tick 6001 and lose the
  tower-HP tiebreak; they deal ~100-700 damage in 5 minutes. Cause: no model of the opponent's
  response after the root move. Added `ScriptRolloutPlanner` in oq_lib.py (player kind `srp`; NOT the
  repo planner: one-step lookahead, both seats continue with the balanced public script for 160
  ticks, one deterministic rollout per candidate). Killed my worker 87141 to free a slot, probed
  srp (works, ~65 cpu-s per 900 ticks), relaunched as PID 89701 with `srp_pilot` first.

- 14:58 interim: legacy_pm 4/34, roll_pm 11/32 on the holdout screen; srp 7/7 in its pilot. Added
  batches srp_screen_h / srp_screen_g (srp, 22 games per cell). Killed my workers 87121 87130 87134
  87138 and relaunched as 3094 3103 3106 3114 with order
  `screen_h srp_screen_h screen_g srp_screen_g default_h pilot2 ext_h ext_g`.

- 15:15 srp pilot 9/9 so far. Reprioritised: killed my workers 3094 3103 3106 3114, relaunched as
  9540 9547 9550 9562 with order
  `screen_h srp_screen_h srp_screen_g legacy_g vs_ckpt roll_g default_h pilot2 ext_h ext_g`
  (legacy_g / roll_g = hog26 screen split per player; vs_ckpt = srp and roll_pm vs the seed-2903 1M
  checkpoint, 32 games, cell `holdout:policy`, seed 31009413). Expect ~6 h for everything; ext_* is
  optional and may be dropped.

- 15:58 holdout screen done: legacy_pm 7/64 (0.109), roll_pm 26/64 (0.406). Both FAIL.
- 16:08 srp 16/17 so far. Killed my worker 89701 (was alone on pilot2) and relaunched it as 21xxx
  (see pgrep) with the same order as the other four, so pilot2 runs last.

- 16:40 srp 40/41 on holdout. `oq_run.py` now accepts "+a,b,c" (interleave batches round-robin by
  game index). Killed my workers 9540 9547 9550 9562 26748; relaunched 40160 40166 40170 40173
  40177 with `srp_screen_h +srp_screen_g,legacy_g,roll_g,vs_ckpt,default_h pilot2 ext_h ext_g`.
  Round two advances all cells together, so it can be cut at any even game index with
  `touch STOP` (workers finish their current game and exit; remove STOP before relaunching).
  Target: stop round two around 19:30-20:00 whatever index it has reached, then write README.

- 17:16 srp holdout 64-game screen: 60-0-4 (0.938, bootstrap [0.86, 1.00]). PASS.
- 17:20 added srp_small (6 random + 2 script candidates, horizon 100) on 8 games per holdout cell.
- 17:38 round two is slow (~4 core-min per game, machine load 12-28). Targets for ~20:00: hog26 36
  games per player (game index < 12), srp vs checkpoint 24 games (batch vs_ckpt_srp, one worker),
  roll_pm vs checkpoint ~12, default +12-24. Killed my worker 40173, relaunched with vs_ckpt_srp first.
  Then `touch STOP`, wait for workers to exit, rerun oq_diag.py, write README.

- (session 2) 2026-10-02 23:10Z: session had been killed and the Mac slept 10-02 02:36Z-23:03Z.
  Workers 40160 40166 40170 52902 60986 survived. State at 23:10Z: srp vs checkpoint 23-0-1 (24
  games, done); srp hog26 43/48; legacy_pm hog26 1/48; roll_pm hog26 2/47; roll_pm vs ckpt 15/16;
  default holdout 1/47. Killed my worker 52902 (was on `default`); running purity check
  `oq_check_purity.py srp roll_pm` (shadow planning must leave the game identical to noop) as its
  replacement process, log logs/purity.log. Then relaunch a fifth worker.

- 23:20Z purity check PASS (srp and roll_pm plan at every playable decision then play no-op: game
  identical to the noop control, 828 ticks, same tower HP). So forking/script calls on forks do not
  perturb the real game or the opponent's observations.
- 23:20Z srp vs checkpoint = 23-0-1, but roll_pm (fails vs scripts) also beat the checkpoint 15-0-1:
  the checkpoint is a weak discriminator. Added out-of-family opponent `sb-<name>` =
  clasher.rl.strategy_bots.StrategyBot (pilot training opponent family, different code from the
  public script). Batches: sb_cheap (noop, random96, ckpt2903 = the 1M checkpoint as the PLAYER),
  sb_srp, sb_roll; cells holdout:sb-balanced (seed 41009413), holdout:sb-bridge-pressure (42009413),
  24 games each.
- 23:22Z STOP-ed all workers gracefully, relaunched 5: PIDs 15433 15441 15444 15447 15450 with
  `sb_cheap +srp_screen_g,sb_srp +sb_roll,vs_ckpt +legacy_g,roll_g,default_h`.

- 23:40Z StrategyBot is weak: on holdout, random96 10/24 and 8/24, the 1M checkpoint 20/24 and
  19/24 against sb-balanced / sb-bridge-pressure; not discriminating. Decisive test instead:
  `srp_xm` = srp whose rollouts model the OPPONENT with StrategyBot balanced (own seat still the
  balanced public script), played against the public scripts (batch srp_xm_h, 64-game screen
  cells). Purity of the new code path not separately checked (same fork/swap mechanism).
- 23:50Z graceful STOP + relaunch: PIDs 20975 20978 20981 20984 20987 with
  `+srp_screen_g,srp_xm_h +sb_srp,vs_ckpt +legacy_g,roll_g,sb_roll,default_h`.

- 00:10Z srp_xm 23-0-3 after 26 games (opponent modelled by StrategyBot still wins). ~1 game/min.
  Plan: when srp_xm_h (66) and srp hog26 (66) are complete, STOP workers, run oq_diag.py, fill README
  TBDs (python3 oq_tables.py; oq_report.py --screen), final report.

- 2026-10-03 ~01:30Z: srp_xm screen 54-0-10 (0.844 [0.73, 0.94]) PASS; srp hog26 58-0-6 (0.906).
  STOP-ed all workers gracefully (none running now). Reran oq_diag.py (merge mode; tree sizes in
  cost/diag.json). Added analysis_caps.json (drops incomplete seat pairs; default capped at game 14,
  srp sb-balanced at 8, roll_pm_h400 excluded). README.md written in full; tables.md generated.
  TASK COMPLETE. Nothing running.

## PRE-REGISTRATION: independent 256-game confirmation of srp_xm (written 2026-10-03 ~01:55Z, before any game)

Requested by the coordinator (2026-10-03). Nothing below may change after the first game.

- Player: `srp_xm_c256` = exact copy of `srp_xm` (ScriptRolloutPlanner; candidate set = script top-4 +
  no-op + 16 random engine-legal-AND-public-mask placements; both continuation seats every 10 ticks
  for 160 ticks; own seat = balanced public script, OPPONENT MODEL = StrategyBot balanced; leaf =
  defense-v2 potential + elixir term, terminal +-2; plan every 2nd decision). Config JSON
  {"horizon": 160, "kind": "srp", "mask_public": true, "opponent_model": "sb-balanced",
  "plan_every": 2, "rollout_interval": 10, "samples": 16, "script_top": 4, "style": "balanced"},
  sha256 5fb7d394c0a0d70fdef28c275faa2bb590620184d38df6d976783efecef53227. oq_lib.py sha256
  8f2c5f2558c016262f65cb19f7ccd2c2d963669399cbcbd7c5430c46c4566851; oq_report.py sha256
  840a40d48f7f275a3409fefda51fb3fd7c1917469f24c495059b410da5a3b413. PRIVILEGED (true state).
- Opponents: the reacting scripted pool = public scripts balanced, pressure, defense (as in the
  pilot diagnostics); strongest scripted baseline = defense (fewest wins for every pilot policy).
- Decks: candidate from roles_v2/development.json (holdout), opponent from roles_v2/training.json;
  secondary cells: candidate Hog 2.6. Level 11 nominal, decision interval 5, max ticks 6001.
- Paired seats: game g -> matchup g//2 (matchup_seed = base + (g//2)*1009), seat g%2, same decks in
  both seats (eval's `_sample_paired_ordered_decks`).
- FRESH base seeds (no overlap with any matchup_seed/seed in 2,148 games files under reports/,
  1,171 distinct seeds, max 42,020,512; checked 2026-10-03):
  holdout:balanced 70000019 (games 0-85), holdout:pressure 71000022 (0-85), holdout:defense
  72000025 (0-83) = 256 games; hog26:balanced 73000028 (0-21), hog26:pressure 74000031 (0-21),
  hog26:defense 75000034 (0-19) = 64 games (secondary, only if time allows, reported separately).
- Batches: conf_hb, conf_hp, conf_hd (holdout), conf_gb, conf_gp, conf_gd (hog26); reference
  ref_* = the seed-2903 1M checkpoint (stochastic, as in pilot evals) on the same games.
- PRIMARY analysis (holdout, 256 games): pooled match score (win 1, draw 0.5, loss 0); 95% CI =
  percentile bootstrap over matchups (both seats of a matchup resampled together), 10,000
  resamples, RNG seed 20261001 (oq_report.boot). PASS requires BOTH
  (a) pooled score >= 0.55 and CI lower bound > 0.50, and
  (b) defense cell (84 games) score >= 0.55 and CI lower bound > 0.50.
  Otherwise FAIL.
- Secondary/descriptive: per-style scores, Wilson win-rate intervals, crown difference; paired
  difference vs the 1M checkpoint on identical games (bootstrap over matchups); hog26 cells with
  the same statistics (no pass/fail claim attached).
- Stopping: games run to completion; no stopping or exclusion based on outcomes. If the run must be
  cut for time, the analysis uses, per cell, games 0..2k-1 for the largest k with all those games
  complete in every holdout cell (complete seat pairs only), and the report says so.
- Self-review done before the games: oq_selfcheck_srp.py (6 checks) PASS; findings in README §5.5.
- Execution: at most 2 workers, `nice -n 15`; stop adding work if swap > ~12 GB.
- Analysis code `oq_confirm.py` (implements exactly the rules above; written before the first srp_xm_c256
  game, while only reference checkpoint games existed), sha256 649d60757ba8e47d53938b2dde0535fe3c8808d97eefb39b31ee29db06114d82.

- 2026-10-03 ~02:00Z: srp self-check PASS (oq_selfcheck_srp.py). Confirmation launched: PIDs 80111
  80114 (nice 15), order `+ref_hb,ref_hp,ref_hd +conf_hb,conf_hp,conf_hd +ref_gb,ref_gp,ref_gd
  +conf_gb,conf_gp,conf_gd`. Expected ~23.5 core-hours for holdout (12-20 h wall), hog26 +6.
  Final: `python3 oq_report.py srp_xm_c256 ckpt2903` (the ckpt2903 rows for seeds 7x000xxx are
  the reference), then update README section 10 and send the report.

## Done

- harness + parity check; cost benchmark; controls (192 games each); 12-game pilot; diagnostic

## Running (PIDs)

- 80111 80114: confirmation workers (see log entry ~02:00Z), logs/worker-c256-*.log
- swap guard `oq_swapguard.sh` (touches STOP if swap > 12 GB; log logs/swapguard.log; relaunch with the same command after removing STOP)

## Next

- Nothing required. Optional: 256-game srp/srp_xm confirmation (about 25 core-hours), roll_pm_s128 /
  roll_pm_h400 budgets (batch pilot2), srp_xm on hog26.

## Notes for the README (so a restarted session need not re-derive them)

Planner facts (oracle_planner.py, 284 lines; identical in snapshot v4 and working tree):
- `select_actions(battle)` builds a fresh dict tree every call (no reuse between decisions). 48
  simulations; each: `battle.clone()` then 10 plies; each ply: node = tree[state_key]; each seat
  Thompson-samples one action (Beta(1,1) prior per arm) from <=96 candidates = no-op + 95 uniform
  random legal (slot,tile) ids (`sample_action_subset`); joint action applied in random order, then
  `decision_interval_ticks` engine steps. Leaf = `reward_win_prob_p0` = sigmoid(2.5 * potential)
  (objective-v1 = crowns/tower-HP terms only), or 1/0/0.5 if the game ended. Backup: every node on
  the path gets alpha += p, beta += 1-p for seat 0 and the complement for seat 1.
- Final choice: default (`stable_root_candidates=False`) draws a FRESH candidate subset and returns
  the max posterior mean, so unvisited arms (mean 0.5) are eligible; measured: 45% of root
  decisions return an action that was never simulated. With `stable_root_candidates=True` the root
  set is fixed and only visited arms are eligible (`greedy_visited_action`).
- Opponent: same bandit, true hidden state (hand, elixir, cycle); the fork also copies the engine
  RNG (`random.Random`), so simulations see the real future random draws.
- State key: tick, time, phase flags, both elixirs (x10), six tower HPs, sorted tuple of up to 96
  live entities (kind, owner, x*2, y*2, hp fraction*20). No hand/cycle. Non-root nodes are almost
  never revisited (rerun `oq_diag.py` for mean_tree_nodes / mean_nonroot_nodes_revisited).
- Fork: `BattleState.clone()` = copy.deepcopy with the card catalog shared through the memo;
  0.95 ms mean (0.55-1.9 ms) at 7-16 live entities.
- With the eval interval 5 (as imitation.py passes config.decision_interval) the default looks
  ahead 10 x 5 ticks = 2.5 s. Supercell: 50 x 0.5 s = 25 s, iterations 4*max|A| (<= 1028), 64
  positions per legal card + Wait + unaffordable cards as wait-until-affordable (|A| <= 257),
  leaf = no-more-deploys rollout until only towers remain then the terminal reward, tree reused
  between steps, final action = highest mean.
- `imitation._collect_oracle_shard` calls the planner at EVERY decision (both seats' labels from
  one call), and `select_actions` returns only argmax actions, not candidate values, so
  `kl_regularized_candidate_target` / Q-regression would need root statistics exposed.
- Pilot policy stats for the DAgger cost estimate: seed-2903 1M checkpoint has ~812 decisions per
  game, ~49% of them playable (noop rate 0.957, noop-when-playable 0.914).
- srp caveat: its rollouts model the opponent with the balanced public script, i.e. the same script
  family it is evaluated against; the checkpoint-opponent games (batch vs_ckpt) are the check.

## CONFIRMATION RESULT (coordinator, 2026-10-03T21:09:33Z)
- Primary holdout set complete (256/256). Pre-registered oq_confirm.py (sha 649d6075..., unchanged) crashed in the
  DESCRIPTIVE "ckpt_alone" line (KeyError 'sb-balanced': ckpt2903 games include StrategyBot-opponent games outside
  CELLS). Ran oq_confirm_fix1.py = identical except that line skips opponents not in CELLS (diff: one condition);
  the verdict logic is untouched. Output confirm256.json.
- PASS: pooled 222-0-34, score 0.867 [0.820, 0.910]; defense 0.845 [0.762, 0.917]; balanced 0.919, pressure 0.837.
  Paired vs seed-2903 1M checkpoint on identical games: 0.379 -> +0.488 [+0.410, +0.566].
  Cost 107 calls/game, 3.34 core-s/call, 367 core-s/game. Privileged (true state) — a teacher, not a fair player.
- hog26 secondary still running (30/64 analysed so far: 0.633 [0.40, 0.87]; balanced cell 1/10 — weak spot).
