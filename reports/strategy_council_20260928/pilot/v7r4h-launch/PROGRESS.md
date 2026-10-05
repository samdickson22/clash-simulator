# v7r4h-launch build log (PPO from the human-imitation checkpoint)

Decision: user-approved 2026-10-02 ~24:00Z. 3 seeds (2901/2902/2903), init = human-prior-p16/checkpoints/human-bc-natural-seed2903.pt
(sha256 49be1480...b482), KL anchor 0.05 to it, critic warm-up 60, v7r2 recipe otherwise (gae 0.95), phases nominal -> nominal-league.
BUILD + VERIFY ONLY. DO NOT LAUNCH.

## Done
- 2026-10-02: read AGENTS/CLAUDE, v7r3/v7r2c kits, council_pilot.py, trainer, runner, preflight. Workspace training-only modules == pilot-runtime-v4 at start.

- Code done (workspace): council_pilot.py (human_prior_* fields, anchor 0.05 literal, is_human_prior, validate_council_human_prior,
  anchor/pool/trainer-arg enforcement), train_recurrent.py (validator branch + resume carry-forward of the record),
  scripts/run_council_pilot.py (human-prior init, human-prior-start eval dir, 2M/3M/4M milestone-evaluation), scripts/preflight_council_pilot.py.
- tests/test_council_human_prior.py written; with v7r3 recipe + admission scope: 53 passed, 3 skipped (kit not yet built).

- pytest suite: 389 passed, 5 skipped, exit 0 -> logs/pytest-before-pilot-runtime-v5.log (sha 31d0e58d...)
- pilot-runtime-v5 built: manifest sha256 0dd402e73abace56878c757491c1b8c9f27dc7cce38b7787b91381682ccb093b
  (342 ADMISSION_BOUND byte-identical, independently re-checked; 4 training-only changed; 2 scripts changed)
- sidecar orchestration-pins-pilot-runtime-v5.json (0c714b45...), configs written read-only:
  s2901 5f77f780..., s2902 8f64e0ea..., s2903 46ef9139...

- static verify --protocol: 132/132 passed (logs/verify-static-protocol-20261003T005150Z.log)

- dry runs: 2901/2902/2903 exit 0 (verify 144/145/146 checks; warm starts rebound; validate_council_human_prior passed with the real admission)

- no-update preflights 64/8 (real human checkpoint, read only): 2901/2902/2903 passed (74/51/24 s; critic-warmup + ppo paths,
  anchor KL 0 at start, weights unchanged, no checkpoint written) -> preflight/seed*-scripted-2026100301*.json
- BUILD COMPLETE 2026-10-03 01:08Z. NOT LAUNCHED.

## Running PIDs
(none; all processes started by this build have exited)

- Kit scripts written: make_configs.py, launch.sh (refuses scratch: tested exit 2), orchestrate.sh (MAX_PARALLEL/STAGGER_S/SEEDS, no caffeinate), progress.sh, early_check.py, rebind_warmstarts.py.

## Next (user decision)
Launch (recommended: 2 concurrent, third when one chain exits; stagger 10 min):
  cd /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/v7r4h-launch && \
    MAX_PARALLEL=2 STAGGER_S=600 nohup bash orchestrate.sh > logs/orchestrator.out 2>&1 < /dev/null &
Monitor: bash progress.sh ; logs/orchestrator.log ; logs/early-check-s*-*.json
Memory at build time (v7r2c league + 5 oracle-qual workers running): 24 GB total, ~51% reclaimable, swap 0.39 GB, disk 35 GiB free.
v7r2c footprint measured 17 GB logical (~11 GB physical). Estimate: +1 run swap ~0-2 GB, +2 runs ~5-10 GB, +3 runs ~15-25 GB (disk risk).

## Commands
RT=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/runtime-snapshots/pilot-runtime-v5
K=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/v7r4h-launch
verify:   cd $RT && env CLASHER_ROOT=$RT PYTHONPATH=$RT/src:$RT/scripts PYTHONDONTWRITEBYTECODE=1 $RT/.venv/bin/python -B $K/verify_v7r4h_launch.py --protocol
dry run:  bash $K/launch.sh SEED scripted --dry-run
preflight: bash $K/launch.sh SEED scripted --through preflight   (NOT a launch; stops after stage 2)
