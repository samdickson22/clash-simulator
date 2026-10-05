# human-prior-p16 running log

Rules: never git reset/clean/stash/commit; never edit runtime-snapshots/ or pilot/ kits; kill only
own PIDs; <=4 workers, `nice -n 10`; total disk < 8 GiB; checkpoints carry
`"provenance": "human-prior research artifact; not a Tier A admitted pilot arm"`.

All commands run from `/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/human-prior-p16`
with `/Users/sam/Desktop/code/clasher/.venv/bin/python` (written `PY` below).

## Done
- (2026-10-01 13:10) Read AGENTS.md, environments/AGENTS.md, scan README, PLAN, amendment, ml-research,
  diagnosis-1M, scripted_demonstrations/council_warmstart/imitation/structured_obs/public_* code.
- Finding from the corpus index: 11,028 P16 perspectives in 10,766 matches, 586,747 plays;
  10,994 of the 11,028 own decks are Hog 2.6. Mean duration 241 s (~960 decision rows each).

- (13:20) Payloads fetched: 52/52 shards SHA-256 verified, 252,238 rows scanned, 10,766 matches kept
  (`data/payloads/shard-XXX.jsonl.gz`, 63 MB). Log: `logs/fetch_payloads.log`.
- (13:33) New module `src/clasher/rl/human_replay_demonstrations.py` + `tests/test_human_replay_demonstrations.py`
  (14 tests pass: `cd /Users/sam/Desktop/code/clasher && .venv/bin/python -m pytest tests/test_human_replay_demonstrations.py -q`).
- Driver helpers: `scripts/hp_bootstrap.py` (binds to frozen runtime v4, loads the new module by path),
  `scripts/reconstruct.py`.
- Findings so far (all go in README):
  * Source `princess_left/right` are positional (surviving towers listed first), NOT lanes: exactly-one-down
    is always `princess_right == 0` (2,881 of 2,881). The scan's lane-level contradiction test was wrong;
    the new module uses counts + pocket-placement lane evidence + the overtime rule (level crowns at 180 s).
  * Recorded timeline = playable ticks + 91 (1,584 matches last exactly 184.55 s); last play is never closer
    than 102 ticks to the recorded end. Rows stop at timeline - 101 ticks.
  * Elixir alignment is two-sided: slack (sim elixir - cost at recorded play) has a sharp edge at 0, never negative.
  * The pilot public mask blocks a 5x5 area around each Princess tower (float32 radius 1.0000000298 ->
    footprint 4) where the engine/game blocks 3x3. ~8% of human plays are in that ring; they are labelled
    as the nearest legal tile (distance 1) and still executed at the recorded point. Strict-cut prefix is
    recoverable via `first_projected_row`.
  * Modern Furnace is a troop placed on the back row; the engine's building Furnace rejects it -> cut.
  * Smoke shard 14: 30 perspectives, 18,036 rows, 85 bytes/row compressed, 2.5 s/perspective.

- (16:20) Reconstruction complete: 52/52 shards, 11,028 perspectives, 7,204,187 rows, 352,260 supervised
  play rows, 0 errors, 608 MB in `data/recon/`. `results/corpus_stats.json` written.
- (16:25) Sanity checks on 200 perspectives passed (`results/sanity_checks.json`): 0 illegal labels in 127,925
  supervised rows, 0 mask mismatches in 18,322 uncached rebuilds, hands/labels aligned, re-simulation byte-identical.
  (4 "failures" listed are diagonal one-tile projections, distance 1.41; checker threshold since corrected.)

## Running
- (16:26) BC fits, 2 torch threads each, resumable by rerunning the same command (state in
  `checkpoints/<name>.pt.state.pt`, per-pool log in `logs/fit-<name>.jsonl`):
  `ENV(OMP 2) nohup ... fit_bc.py --variant natural --threads 2 > <OUT>/logs/fit-natural.stdout 2>&1 &`  PID 36440
  `ENV(OMP 2) nohup ... fit_bc.py --variant wait02  --threads 2 > <OUT>/logs/fit-wait02.stdout 2>&1 &`  PID 36441
  64 pools each (256 parts / 4); expect 5-6 h.

## Next
All scripts exist and were smoke-tested on shard 14 (smoke artifacts deleted). ENV below means:
`R=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/runtime-snapshots/pilot-runtime-v4; cd $R && CLASHER_ROOT=$R PYTHONPATH=$R/src OMP_NUM_THREADS=<n> nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python <OUT>/scripts/<script>`
1. When `logs/reconstruct.log` shows all 52 shards (52 `data/recon/shard-*.done.json`):
   - ENV `corpus_stats.py` -> results/corpus_stats.json (yields, cut reasons, unknown tokens, human behaviour stats)
   - ENV `sanity_checks.py --perspectives 200` -> results/sanity_checks.json (~15 min, 1 process)
2. Fits (run both concurrently, 2 threads each, detached with nohup; rerun same command to resume):
   - ENV(OMP 2) `fit_bc.py --variant natural --threads 2`  -> checkpoints/human-bc-natural-seed2903.pt
   - ENV(OMP 2) `fit_bc.py --variant wait02 --threads 2`   -> checkpoints/human-bc-wait02-seed2903.pt
   - optional: `fit_bc.py --variant winners --initial <best>.pt --max-pools 12 --name human-bc-<best>-winners-seed2903`
3. Validation (held-out 10% of matches): ENV `validate_bc.py --checkpoint X --name N` for the BC checkpoints,
   the scripted warm start (`pilot/v7r2-launch/runs/s2903/seed-2903/initialization/scripted.pt`) and the 1M
   checkpoint (`.../scripted/policy_decisions_001000000.pt`).
4. Evaluation (no ENV needed; it sets the runtime env itself):
   `nice -n 10 .venv/bin/python scripts/run_eval.py --checkpoint X --name N --parallel 4` then
   `scripts/behaviour_stats.py --name N --drop-traces`. Seeds: 770031 + 1_000_003*(role*6+style+12).
   Names: scripted-warmstart-s2903, v7r2-1M-s2903, human-bc-natural, human-bc-wait02 (+ winners).
5. README.md with all tables; final report to coordinator.

## Pre-declared before any evaluation game (16:35)
- Evaluation: seed base 770031, slots 12-17 (formula in scripts/run_eval.py), 32 games x 3 styles x {holdout, hog26},
  every checkpoint evaluated once, all results reported (no best-of selection). Checkpoints: scripted warm start
  s2903, v7r2 1M s2903, human-bc-natural, human-bc-wait02, and the winners fine-tune.
- Winners fine-tune (filtered BC) starts from human-bc-natural (isolates the filter from the wait weighting):
  `fit_bc.py --variant winners --initial checkpoints/human-bc-natural-seed2903.pt --max-pools 16 --threads 4 --name human-bc-natural-winners-seed2903`
- (18:31) Baseline evaluations on the new seeds started (2 processes): `logs/eval-baselines.log`
  (`run_eval.py --name scripted-warmstart-s2903`, then `--name v7r2-1M-s2903`; finished cells are skipped on rerun).
  Fits at pool 29/64 at 18:30, ~400 rows/s each.
- (2026-10-02 23:10Z) Session restarted after a restart plus Mac sleep (02:36Z-23:03Z); detached jobs survived.
  Baseline evaluations complete; summarized with `behaviour_stats.py` (traces kept for now).
  Fits at pool 60/64 at 23:10Z. Coordinator: <=4 processes total (oracle workers + 2903 continuation eval also running).
- (23:20Z) Fits done. natural sha256 49be1480...b482, wait02 sha256 2139ef96...1441 (validation in logs/fit-*.stdout,
  results/fit-*.json). Started: winners fine-tune (`fit_bc.py --variant winners --initial checkpoints/human-bc-natural-seed2903.pt
  --max-pools 16 --threads 2 --name human-bc-natural-winners-seed2903`, logs/fit-winners.stdout); evaluation of natural then
  wait02 (logs/eval-bc.log, 2 processes); validation of scripted/1M/random-control on the same 200 held-out perspectives
  (logs/validate-baselines.log, 1 process). Rerun any of these commands to resume.
- (23:59Z) Evaluations natural (22/96 holdout, 18/96 hog26) and wait02 (15/96, 6/96) done; baselines on the same seeds:
  scripted 14/96 & 9/96, 1M 38/96 & 5/96. Winners fine-tune done (sha256 301fa1c4...b459); validations done.
  Running: `run_eval.py --checkpoint checkpoints/human-bc-natural-winners-seed2903.pt --name human-bc-natural-winners --parallel 4`
  (logs/eval-winners.log). Next: behaviour_stats for it, README, final report.
- (2026-10-03 00:40Z) DONE. Winners eval 13/96 holdout, 15/96 hog26. results/paired_comparisons.json written; decision
  traces and fit resume states deleted after summarizing. README.md written. Tests: 18 pass. Total dir 690 MB.
  Best checkpoint: checkpoints/human-bc-natural-seed2903.pt sha256 49be14806a7e7e6ab26621e25230d3f6f7f0be4d84aabd480cbb8097de4ab482.
  No jobs running.
