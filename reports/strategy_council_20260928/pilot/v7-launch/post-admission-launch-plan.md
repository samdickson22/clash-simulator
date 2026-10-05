# Council pilot: launch plan for Tier A v7 (admitted; ready to launch, not executed)

Prepared 2026-09-30 around 19:00 UTC (noon local). `m0-tier-a-fresh-v7` **passed**: `report.json` has status `passed` (sha `a09e16f3…`), and the ledger issued `m0/readiness/tier-a-fresh-v7/admission.json` (sha `aeb4a2ff…`). `readiness_admission.py verify` returns `m0-tier-a-fresh-v7 scalar_public_policy_only`. This kit retargets `../v6-launch/`. The v4, v5 and v6 kits stay unchanged as records.

While preparing this I ran no training, used no emulator or adb, wrote nothing to the ledger (every read used `mode=ro`), and edited no snapshot code. Every step ran under `nice -n 15` with `OMP_NUM_THREADS=2`. Paths are relative to `reports/strategy_council_20260928/` unless absolute. `$V7` is `pilot/v7-launch`.

## 0. What changed since the v6 kit

### 0.1 Source differences, native-final-v6 → native-final-v7

**v7 = v6 + fixed `src/clasher/entities.py` and `src/clasher/battle.py`.** Both `snapshot.json` manifests list the same 760 files: nothing added, nothing removed, 2 changed. The attempt's own diff (`m0/readiness/tier-a-fresh-v7/snapshot-diff-vs-v6/manifest-diff.json`) says the same.

| File | v6 sha | v7 sha | Change |
| --- | --- | --- | --- |
| `src/clasher/battle.py` | `f43fe498…` | `58aaf0cd…` | The deploy anchor's x-side follows the *requested* position, not the searched one (v6 episode-10, job-00321, Ice Golem). |
| `src/clasher/entities.py` | `93b0ea31…` | `e0e673c9…` | Crown Towers keep their hit when retargeting in range mid-windup (v6 episode-12, job-00399). A troop that stops in range of a building keeps its unconsumed route through a freeze and resumes it when pushed out of range (v6 episode-24, job-00781). |

**This is the first kit since v5 that changes code on the pilot path.** Both files are simulation modules, so the warm-start corpus and PPO rollouts run on the corrected simulator. Both are admitted `src/clasher` pins, which means the pilot runs on exactly the bytes Tier A v7 tested. **Unchanged vs v6:** game data (`daa58b28…`), `uv.lock` (`dc6ff5e2…`), the strategy (`2be09f05…`), `input_files`, the interpreter and dependency environment, the four orchestration scripts, `council_pilot.py`, `council_warmstart.py` and `train_recurrent.py`. A verify check asserts the last group. The model, trainer and warm-start code did not change, so checkpoint and corpus sizes are unchanged.

### 0.2 Declaration differences, v6 → v7

These fields differ: `attempt_id`; the two `source_pins` digests above (the paths also move to `native-final-v7`); `input_pins` (new native configs, root bank, criteria and calibration receipt); `root_bank_sha256`; `converter_manifest_sha256` / `pre_protocol`; and the fresh episodes (`m260928910-*`). The pin count is still **358: 351 `src/clasher` modules + 7 readiness scripts**, and `technical_rerun_policy` is still `once_before_result`. The admission receipt carries no `technical_reruns` (count 0). The full ledger check, which enforces equality with the ledger's rerun record, passes.

### 0.3 Pins and admission

The pin file is regenerated from the v7 declaration: exactly the 351 `src/clasher` pins. It equals every `*.py` under the snapshot's `src/clasher` and the `src/clasher` subset of `required_source_pins()`. Compared with the v6 kit's pin file (after moving the paths), only `battle.py` and `entities.py` differ. The sidecar is regenerated from v7's `snapshot.json` (`288d3e1c…`). Unlike the v6 sidecar, it records the admission digest, because the admission existed when it was written.

The real admission check passes for all three configs: `verify_v7_launch.py --require-admission --config …` ends with `require_pilot_admission (full ledger check)` returning `m0-tier-a-fresh-v7`. That is the pilot's own path (`council_pilot.require_pilot_admission` → the snapshot's `require_admission`).

### 0.4 Kit changes vs v6

The scripts, stages, exit codes, seeds, config field changes and `MIN_FREE_GB` default (20) are the same, with paths moved from v6 to v7. Beyond that:

- `make_pins.py` asserts that the v6 → v7 delta is exactly `battle.py` + `entities.py`, that every other pin equals the v6 kit's pin file, and that the orchestration scripts are unchanged. It writes `admission_sha256` into the sidecar and records the delta under `source_delta_vs_native_final_v6`.
- `verify_v7_launch.py` has **57 static checks** (v6: 54). The delta check is rewritten for the 2-file delta. The "pilot-path modules unchanged" check now excludes `entities.py`, which intentionally changed. Four checks are new:
  - the changed modules carry the v7 digests in `snapshot.json`, the pin file and the declaration;
  - the pin file equals the v6 kit's pin file except for the two modules;
  - the sidecar records the v6 → v7 delta;
  - the sidecar's admission digest equals `admission.json`.

  `--protocol` adds 3 checks, and `--require-admission --config` adds 13.

The v3–v6 findings still hold: `num_envs ≤ 8`, `actor_workers ≤ 4`, `torch_threads ≤ 4`, device cpu or mps; one coordinator per output dir, with both arms of a seed sharing its ledger; `run_council_pilot.py --freeze-source` is still unusable because it adds unadmitted council scripts; main is not used (its game data is still `3d99987c…`).

## 1. Artifacts in `$V7`

| File | Purpose |
| --- | --- |
| `source-pins-native-final-v7.json` (read-only, sha `1049ae64…`) | The 351 admitted `src/clasher` modules, with absolute snapshot paths and declaration digests. |
| `orchestration-pins-native-final-v7.json` (read-only, sha `e5aefe3a…`) | The sidecar. It binds the 4 orchestration scripts and `readiness_admission.py` by snapshot path and hash. It also records the digests of `snapshot.json`, the declaration (`19a1d65b…`), the freeze receipt, the pin file and the admission (`aeb4a2ff…`), plus `technical_rerun_policy` and the v6 → v7 delta. |
| `make_pins.py`, `make_configs.py` | Write-once generators (`open("x")`). |
| `verify_v7_launch.py` | 57 static checks, plus 3 protocol checks and 13 admission checks. The last admission check is the real `require_pilot_admission`. |
| `configs/council-pilot-v7-seed{2901,2902,2903}.toml` (read-only; sha `7ce1ac6a…`, `40437254…`, `5cacc7b6…`) | One per seed; each covers both arms. |
| `launch.sh SEED ARM [--dry-run] [--through STAGE]` | Stages: verify, then preflight, then smoke (seed 2901 only), then nominal. |
| `smoke_check.py` | Automatic correctness gate after the smoke. It checks launch receipts against the v7 pin file. |
| `disk-plan.md` | Space estimates and ranked cleanup candidates (list only), updated for v7. |
| `logs/`, `preflight/`, `locks/`, `runs/s<seed>/` | Launch logs and receipts, preflight records, the per-seed lock, and the output dirs. The output dirs do not exist yet. |

Verification at preparation time (19:00 UTC):

- `verify_v7_launch.py --protocol --require-admission --config …seed{2901,2902,2903}.toml`: **73/73 passed for each seed** (57 static + 3 protocol + 13 admission). The frozen `pilot/evaluation-protocol.json` (`4a16b0b6…`) equals `build_protocol(config)` for all three configs.
- `bash -n launch.sh` passed.
- **`launch.sh 2901 scripted --dry-run` exited 0.** It passed static verification (57/57), `readiness_admission.py verify` (`m0-tier-a-fresh-v7 scalar_public_policy_only`) and `verify_v7_launch.py --require-admission` (70/70, including `require_pilot_admission`). It then logged `admission ok sha256=aeb4a2ff…`, wrote a `dry_run: true` launch receipt, printed the planned preflight, smoke and nominal commands, and stopped with `stopping after stage 1 (dry_run=1 through=nominal)`. The artifacts are `logs/dry-run-s2901-scripted-20260930T185735Z.log`, `logs/verify-s2901-scripted-20260930T185735Z.json` and `logs/launch-receipt-s2901-scripted-20260930T185735Z.json`.

No preflight record, lock or run dir was created, and no training ran.

## 2. Config fields changed from `configs/council-pilot-local.toml`

The base file (sha `b7b12ab9…`, the same as for the v6 kit) is untouched. Every generated config differs only in these fields, and `verify_v7_launch.py` enforces that the set is exact:

| Field | Base | v7 value |
| --- | --- | --- |
| header comment | "Unadmitted local pilot…" | 3-line v7 provenance comment |
| `source_root` | `/Users/sam/Desktop/code/clasher` | `…/m0/runtime-snapshots/native-final-v7` |
| `gamedata_path` | `…/m0/training-package/inputs/gamedata.json` | `…/native-final-v7/gamedata.json` (same digest, `daa58b28…`) |
| `source_pins_path` | `…/pilot/source-pins.json` (absent) | `…/pilot/v7-launch/source-pins-native-final-v7.json` |
| `nominal_admission_path` | `…/pilot/admissions/nominal.json` (absent) | `…/m0/readiness/tier-a-fresh-v7/admission.json` (canonical ledger path; a copy would fail) |
| `output_dir` | `…/pilot/runs` | `…/pilot/v7-launch/runs/s2901`, `s2902`, `s2903` |
| `num_envs` | `4` | `8` (admitted maximum) |

The reasons for each field are the same as in `../v6-launch/post-admission-launch-plan.md` §2. `actor_workers=2`, `torch_threads=2`, `sequence_batch_size=2` and `device="cpu"` stay as they are: 4 cores per run.

## 3. Resources at preparation time (19:00 UTC)

- **Disk:** 39 GiB free on `/System/Volumes/Data` (91% used). That is above the 35 GiB `MIN_FREE_GB` floor for the first launch (4 GiB margin) and above the 25 GiB floor for later seeds. The default floor is 20. Expect about 33–36 GiB after seed 2901's warm start. The full 5M pilot for three seeds still needs one approved cleanup (see `disk-plan.md`).
- **Memory:** 24 GiB RAM with 72% free. Swap is 6.4 of 7.2 GB used, left over from Tier A. macOS grows swap on the same APFS container, which counts against disk.
- **CPU:** 12 cores, load about 2–3. One emulator (`clasher_reference_api35`, pid 22127, about 1.5 GB RSS, about 50% of one core) is still running for level probes. `launch.sh` does not block on it: its precondition only refuses while `run_readiness_v2` or `collect_readiness_prefix` is alive, and neither is. With the emulator up, seed 2901 alone (4 cores, plus the warm-start fit) fits. Three concurrent seeds (12 cores) plus the emulator would oversubscribe slightly, so start seed 2903 after the level probes finish, or accept the slowdown.

## 4. Launch sequence

**Preconditions (coordinator):** admission verified (done); no Tier A runner alive (true now); free space ≥ 35 GiB for the first launch (39 GiB now); nobody runs `uv sync` or `pip` in main's `.venv` (the snapshot's `.venv` is a symlink to it; each launch receipt records torch 2.10.0, numpy 2.3.5, Python 3.12.13 and `uv.lock` `dc6ff5e2…`).

```sh
V7=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/v7-launch
# 0. Verification only (safe any time)
bash $V7/launch.sh 2901 scripted --dry-run
# 1. Seed 2901: warm start, then the scripted smoke (100k) with smoke_check, then stop.
nohup caffeinate -i env MIN_FREE_GB=35 bash $V7/launch.sh 2901 scripted --through smoke > /dev/null 2>&1 < /dev/null &
# 2. After the smoke check passes (logs/smoke-check-s2901-scripted-*.json "passed"): scripted nominal to 1M,
#    then the scratch arm (smoke, then nominal). The per-seed lock forces the arms to run in sequence.
nohup caffeinate -i bash -c "MIN_FREE_GB=35 bash $V7/launch.sh 2901 scripted && MIN_FREE_GB=35 bash $V7/launch.sh 2901 scratch" > /dev/null 2>&1 < /dev/null &
# 3. After seed 2901's smoke check has passed and its warm-start fit has ended (RAM, merge peak):
nohup caffeinate -i bash -c "MIN_FREE_GB=25 bash $V7/launch.sh 2902 scripted && MIN_FREE_GB=25 bash $V7/launch.sh 2902 scratch" > /dev/null 2>&1 < /dev/null &
# 4. After seed 2902's warm-start fit has ended (and preferably after the level-probe emulator has stopped):
nohup caffeinate -i bash -c "MIN_FREE_GB=25 bash $V7/launch.sh 2903 scripted && MIN_FREE_GB=25 bash $V7/launch.sh 2903 scratch" > /dev/null 2>&1 < /dev/null &
```

Step 2 re-runs stage 1. Stage 2 skips because a passed preflight record exists for the same config sha. Stage 3 skips because the 100k milestone and a passed smoke check exist. Then it continues with nominal. To run seed 2901 in a single step, use the step-2 command without step 1.

What `launch.sh SEED ARM` does (unchanged from v6, paths moved to v7). cwd is the snapshot root, `CLASHER_ROOT` is the snapshot, `PYTHONPATH` is snapshot `src:scripts`, the coordinator runs with `-B` and `OMP_NUM_THREADS=2`, and logs go to `$V7/logs/`.

1. **verify.** The config must be read-only. Then static verification, a refusal if `admission.json` is absent, `readiness_admission.py verify`, and `verify_v7_launch.py --require-admission --config CFG`, which runs the full `require_pilot_admission`. Any failure exits 3. Then it writes the launch receipt.
2. **preflight.** `preflight_council_pilot.py --num-envs 8 --actor-workers 2`: a no-update run of the real trainer argv in a temp dir. It must report bit-identical weights and `real_output_dir_created: false`. Failure exits 4.
3. **smoke** (seed 2901, each arm). `run_council_pilot.py --phase smoke --execute`: the seed's warm start on first use (about 499k public-script opportunities at level 11, a one-epoch exact fit and a matched control), then 100,000 decisions, then `smoke_check.py`. Seeds 2902 and 2903 refuse to continue until a seed-2901 smoke check has passed. Failure exits 5 (a runner failure exits 6).
4. **nominal.** `run_council_pilot.py --phase nominal --execute`: the arm to 1,000,000 decisions, then the automatic diagnostic matrix. It is for humans only: no early stop and no strength claim. A runner failure exits 6.

Before starting seed 2902, record from seed 2901: peak RSS during the fit, the `corpus.npz` size, and `du` of `initialization/` during the merge. Use them to replace the estimates in `disk-plan.md`.

## 5. After 1M: mixed-league phase, time and budget

Unchanged from `../v6-launch/post-admission-launch-plan.md` §4–§5, with everything bound to v7:

- The level extension must be issued from `$ATT/admission.json` = `m0/readiness/tier-a-fresh-v7/admission.json` (`readiness_admission.py --ledger $LEDGER extend-levels --base-admission … --level-evidence … --output pilot/admissions/levels-10-12.json`).
- Probe configs must be regenerated from `native-final-v7`.
- The mixed-league run is `run_council_pilot.py --config $V7/configs/council-pilot-v7-seed$S.toml --phase mixed-league --seed $S --execute`.
- The recipe claim uses `--seed-report $V7/runs/s<S>/seed-<S>/$ARM/strength-report.json` for the three seeds and writes `pilot/$ARM-recipe-strength-v7.json`.

Estimated time: 3–5.5 h warm start per seed, 11–19 h per arm to 1M plus 1.6–2.7 h of diagnostics, and about 6–9.5 days wall clock for the full 5M pilot. **The coordinator must enforce a combined cap of 4,608 core-hours by hand**, because each of the three ledgers allows that much on its own. The projected total is 1,600–2,500 core-hours.

## 6. Still blocked or at risk

1. **No level-extension receipt yet.** The pilot halts at the 1M diagnostic until one is issued from the v7 admission.
2. **Disk.** 39 GiB is enough for the 1M phase of all three seeds. The full 5M pilot with one merge peak needs one approved cleanup from `disk-plan.md`.
3. **Pin-scope decision.** It is recorded in the sidecar, not in the ledger (the same as v4–v6).
4. **Shared `.venv` and absolute paths.** `tier-a-fresh-v7` artifacts and `native-final-v7/` are re-hashed before every job. They must not move during the pilot.
5. **Stale lock.** If `launch.sh` is killed with `-9`, remove `$V7/locks/seed-<S>.lock` by hand after confirming that no coordinator for that seed is alive.
6. **Do not mix kits.** The v6 kit's configs point at the v6 admission and snapshot. v6 was superseded by v7 and must not be launched.
7. **Evaluation can fail by design.** All 9 slices must be `noninferiority_supported`.
