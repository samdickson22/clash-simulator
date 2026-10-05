# Council pilot v7r1: launch plan

Prepared 2026-09-30 (21:45 UTC). This kit is the v7 kit (`../v7-launch/`, left untouched) moved onto the pilot runtime `m0/runtime-snapshots/pilot-runtime-v1`. The manifest is `pilot-runtime.json`, sha `b6433179…`. The runtime is native-final-v7 plus 3 changed training-only modules: `council_pilot.py`, `parallel_rollout.py` and `train_recurrent.py`. It uses the throughput layout recommended in `../throughput/README.md`. User decision: all three seeds run on CPU. No training has run.

## Artifacts

| File | Purpose |
| --- | --- |
| `configs/council-pilot-v7r1-seed{2901,2902,2903}.toml` (read-only; sha `1453321a…`, `71122fa9…`, `1dc9e75c…`) | One config per seed; each covers both arms. |
| `orchestration-pins-pilot-runtime-v1.json` (read-only, sha `d71d140b…`) | Sidecar. It binds the 4 orchestration scripts at runtime paths and `readiness_admission.py` at the admitted root. It also records digests for the runtime manifest, native-final-v7 `snapshot.json`, the declaration, the freeze receipt, the scope decision (`ea3bfc19…`), the admission (`aeb4a2ff…`) and the pilot freeze (`529b801e…`, 351 modules), plus the 3-module delta. |
| `make_configs.py`, `make_sidecar.py` | Write-once generators. |
| `verify_v7r1_launch.py` | Static checks, plus `--protocol` and `--require-admission --config`. The central check is the real `verify_pilot_source_scope(runtime, native-final-v7)`, which finds 342 bound modules, 9 training-only modules and 3 changed. A negative control confirms it refuses a changed `battle.py` pin. The final admission check is the full `require_pilot_admission`, which runs the unchanged ledger check in the admitted runtime. The admission's `source_root` stays native-final-v7. |
| `launch.sh`, `smoke_check.py` | Same stages as v7. cwd is the runtime root, and `CLASHER_ROOT` and `PYTHONPATH` point at runtime `src:scripts`. `readiness_admission.py verify` runs from native-final-v7 with a temporary numba cache, because from the pilot runtime the ledger check refuses by design. The preflight uses the config's own 64/8 layout. The smoke milestone is `policy_decisions_000098304.pt`. |

## Config fields changed from `configs/council-pilot-local.toml`

The kit also changes the fields v7 already changed: `source_root`, `gamedata_path` and `source_pins_path` now point at pilot-runtime-v1 (`gamedata.json`, `pilot-source-pins.json`), `nominal_admission_path` points at the v7 admission, and `output_dir` is `runs/s<seed>`. The throughput settings are `num_envs = 64`, `actor_workers = 8`, `torch_threads = 4`, `smoke_decisions = 98304`, plus explicit `rollout_inference = "worker"` and `inference_device = "cpu"`. `device = "cpu"` and `sequence_batch_size = 2` are unchanged. The verifier enforces this exact set.

## Verification (21:37–21:41 UTC)

- `verify_v7r1_launch.py --protocol --require-admission --config` passed **91/91 for each seed** (`logs/verify-full-s*-20260930T213652Z.json`). The frozen evaluation protocol `4a16b0b6…` equals `build_protocol(config)`.
- **`launch.sh 2901 scripted --dry-run` exited 0.** Static checks passed 74/74, the admitted-root ledger verify passed (`m0-tier-a-fresh-v7 scalar_public_policy_only`), and `--require-admission` passed 88/88. The run then wrote a launch receipt and printed the plan. Artifacts: `logs/dry-run-s2901-scripted-20260930T213749Z.log`, `logs/verify-s2901-scripted-*.json`, `logs/launch-receipt-s2901-scripted-*.json`.
- **No-update trainer preflight** at 64 envs and 8 workers, from the runtime, **passed for all 6 (seed, arm) pairs** in 7–9 s each. Weights were bit-identical, no optimizer step ran, no checkpoint was written, `rejected_actions` was 0, and no real output dir was created. The records are in `preflight/`, so launch stage 2 skips.

## CPU: 3 seeds × (8 workers + 4 torch threads) on 12 cores

Nominally this is 36 threads on 8P+4E cores, 3× oversubscribed. In practice collection (8 actor processes) and the update (4 learner threads) alternate. One run alone averages 4.1 busy cores, so three runs average about 12, which saturates the machine without heavy thrashing. The benchmark ran exactly this layout concurrently and measured 29.4–29.7 dec/s per run, **88.5 aggregate**, against 72.8 for the old 3 × 4-core layout. The contention cost is therefore already in the measurement, and the config stays as it is. `torch_threads = 3` was not benchmarked. The coordinator process keeps `OMP_NUM_THREADS=2`; trainers get 4 from `pilot_environment`.

**Caveats for the coordinator:**

- **Core-hour accounting.** Each training job charges its declared 12 cores times wall-clock time, so the three ledgers together charge about 36 cores on a 12-core machine. Projected charges per seed: about 94 h × 12 ≈ 1,130 for training, plus warm start and evaluation at 4 cores, about 1,200–1,250 in total. The combined total is **about 3,600–3,750 core-hours** against the combined 4,608 cap that must be enforced by hand. The margin is about 20%, and timing estimates are ±25%. The 1M nominal phase uses about 300 per seed.
- **Memory.** In the 3 × CPU benchmark, swap rose to about 10.8 GB. Swap is currently 6.7 of 8.2 GB used, and it grows on the data volume.
- **Checkpoints.** At 64 envs the scripted smoke is entirely critic warm-up (20 updates = 163,840 decisions), and periodic checkpoints come every 1.64M decisions. That means fewer checkpoints and less disk use than v7.

## Launch sequence

Disk now: 40 GiB free. Preconditions are unchanged from v7: no `uv sync` or `pip` in the shared `.venv`, and never move `native-final-v7/`, `pilot-runtime-v1/` or `tier-a-fresh-v7/`.

```sh
K=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/v7r1-launch
# 1. Seed 2901: warm start, then the 98,304-decision scripted smoke and smoke_check, then stop.
nohup caffeinate -i env MIN_FREE_GB=35 bash $K/launch.sh 2901 scripted --through smoke > /dev/null 2>&1 < /dev/null &
# 2. After logs/smoke-check-s2901-scripted-*.json says "passed": scripted nominal to 1M, then scratch (smoke, then nominal).
nohup caffeinate -i bash -c "MIN_FREE_GB=35 bash $K/launch.sh 2901 scripted && MIN_FREE_GB=35 bash $K/launch.sh 2901 scratch" > /dev/null 2>&1 < /dev/null &
# 3. Seed 2902: after step 1 passed, so that seed 2901's warm-start fit has ended (RAM and merge peak).
nohup caffeinate -i bash -c "MIN_FREE_GB=25 bash $K/launch.sh 2902 scripted && MIN_FREE_GB=25 bash $K/launch.sh 2902 scratch" > /dev/null 2>&1 < /dev/null &
# 4. Seed 2903: after seed 2902's warm-start fit has ended, that is once
#    $K/runs/s2902/seed-2902/initialization/scripted-demonstrations/result.json exists
#    and no run_council_warmstart.py process for 2902 is alive.
nohup caffeinate -i bash -c "MIN_FREE_GB=25 bash $K/launch.sh 2903 scripted && MIN_FREE_GB=25 bash $K/launch.sh 2903 scratch" > /dev/null 2>&1 < /dev/null &
```

Before step 3, record seed 2901's fit peak RSS, the size of `corpus.npz`, and `du` of `initialization/` during the merge (see `disk-plan.md`). After 1M, the mixed-league phase is the same as in v7 §5, run with the v7r1 configs. It still needs `pilot/admissions/levels-10-12.json` issued from the v7 admission.

If `launch.sh` is killed with `-9`, remove `$K/locks/seed-<S>.lock` by hand after confirming that no coordinator for that seed is alive. Do not mix kits: the v4–v7 kits run from other roots.
