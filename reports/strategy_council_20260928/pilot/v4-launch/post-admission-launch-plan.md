# Council pilot: post-admission launch plan for Tier A v4 (prepared, not executed)

Prepared 2026-09-29 around 08:10 UTC, while `m0-tier-a-fresh-v4` was running. The ledger showed 164 of 1,024 branch results; branches were launched around 07:47 UTC. This plan updates `../post-admission-launch-plan.md`, which was written for v3 and is kept unchanged as a record. v3 cannot pass (`../../m0/readiness/tier-a-fresh-v3/operational-failure.json`).

While preparing this I ran no training, used no emulator or adb, wrote nothing to the ledger (every read used `mode=ro`), and edited no snapshot code. Paths are relative to `reports/strategy_council_20260928/` unless absolute. `$V4` is `pilot/v4-launch`.

## 0. What changed since the v3 plan

1. **The pins pass without code changes.** I checked how `require_pilot_admission` validates pins. `load_source_pins` resolves each key against `source_root` and re-hashes it. `require_admission` then maps each file to `receipt.source_root / relative` and requires the same digest in `receipt.source_pins`. `evaluate_attempt` issues `source_root = Path(readiness_capture_ownership.__file__).parents[3]`, which is the snapshot root because the declared evaluate command runs from the snapshot. It copies `source_pins` from the declaration. The v4 declaration has 354 pins: all **347** `src/clasher` modules (v3 had 346; `rl/native_rich_delta.py` was added) plus 7 readiness scripts. The pilot pin file is exactly those 347 modules. `verify_v4_launch.py` mirrors the loop in `require_admission` against a receipt stand-in built from the ledger's copy of the declaration, and it passes with 0 mismatches for all three configs. `run_council_pilot.py --freeze-source` is still unusable: its output adds three council scripts that are not admitted.
2. **The orchestration scripts are bound by a sidecar**, `$V4/orchestration-pins-native-final-v4.json`, as the coordinator decided. It covers `run_council_pilot.py`, `run_council_warmstart.py`, `evaluate_council_pilot.py` and `preflight_council_pilot.py`, plus `readiness_admission.py` as a verification tool. Each entry records the snapshot path and hash, which equal `snapshot.json` `source_files`. The sidecar also records the digests of the declaration, freeze receipt, `snapshot.json` and pin file. The admission digest is recorded later, in each launch receipt.
3. **Main source equals the snapshot today** (749/749 files are byte-identical). Main is still not usable: its `gamedata.json` is `3d99987c…`, while `_verify_declaration` requires the workspace game data to be `daa58b28…`. Main is also still being edited. The coordinator's decision stands: run from `native-final-v4`.
4. **v4 changes simulation code on the pilot path.** It adds the King first-target lock (`entities.py`, `torch_sim/combat.py`) and changes the projection margin and native-speed modules. The pilot runs on exactly the admitted bytes, so no pilot feature is lost.
5. The following v3 findings still hold:
   - `num_envs ≤ 8`, `actor_workers ≤ 4`, `torch_threads ≤ 4`, device cpu or mps.
   - One coordinator per output dir. The two arms of a seed share a ledger, because `validate_council_initial_policy` requires the initializer's `BudgetSnapshot.ledger_path` to be the run's own ledger.
   - The mixed-level receipt tooling is still missing. The snapshot has only `prepare_readiness_level_extension.py` and the verifier. The draft probe manifest is still `draft_missing_nominal_admission` and bound to `3d99987c…`.
   - Tier B is still unimplemented.

## 1. Artifacts in `$V4`

| File | Purpose |
| --- | --- |
| `source-pins-native-final-v4.json` (read-only, sha `9496e007…`) | The 347 admitted `src/clasher` modules with absolute snapshot paths and declaration digests. |
| `orchestration-pins-native-final-v4.json` (read-only, sha `3fe3f5e1…`) | The sidecar described in §0.2. |
| `make_pins.py`, `make_configs.py` | Write-once generators for the two pin files and the three configs (`open("x")`). |
| `verify_v4_launch.py` | 46 static checks, plus 3 protocol checks with `--protocol` and 11–12 admission checks with `--require-admission [--config]`. The last of those is the real, full `require_pilot_admission`. |
| `configs/council-pilot-v4-seed{2901,2902,2903}.toml` (read-only) | One per seed; each covers both arms. |
| `launch.sh SEED ARM [--dry-run] [--through STAGE]` | Stages: verify, then preflight, then smoke (seed 2901 only), then nominal. |
| `smoke_check.py` | Automatic correctness gate after the smoke. |
| `disk-plan.md` | Space estimates and ranked cleanup candidates (list only). |
| `logs/`, `preflight/`, `locks/`, `runs/s<seed>/` | Launch logs and receipts, preflight records, the per-seed lock, and the output dirs. The output dirs do not exist yet. |

Verification at preparation time: `verify_v4_launch.py --protocol` passed 49/49. The frozen `pilot/evaluation-protocol.json` (`4a16b0b6…`) equals `build_protocol(config)` for all three configs. `bash -n launch.sh` passed on system bash 3.2.57. `launch.sh 2901 scripted --dry-run` passed the static stage and then exited 3 with `REFUSED: …/tier-a-fresh-v4/admission.json does not exist` (`logs/dry-run-s2901-scripted-20260929T080655Z.log`). A hand-written admission with correct pins and fields was rejected by `require_admission`, with missing ledger/seal fields. It also failed `verify_v4_launch`'s report check.

## 2. Config fields changed from `configs/council-pilot-local.toml`

The base file (sha `b7b12ab9…`) is untouched. Every generated config differs only in these fields, and `verify_v4_launch.py` enforces that the set is exact:

| Field | Base | v4 value | Why |
| --- | --- | --- | --- |
| header comment | "Unadmitted local pilot…" | 3-line v4 provenance comment | Comment only. |
| `source_root` | `/Users/sam/Desktop/code/clasher` | `…/m0/runtime-snapshots/native-final-v4` | Coordinator decision. It selects `<root>/.venv/bin/python` and `PYTHONPATH=<root>/src`, and satisfies the warm start's `__file__` root check. |
| `gamedata_path` | `…/m0/training-package/inputs/gamedata.json` | `…/native-final-v4/gamedata.json` | Its parent becomes the job cwd and `CLASHER_ROOT`. The trainer requires `clasher.paths.gamedata_path()` to equal it. The digest is unchanged (`daa58b28…`). |
| `source_pins_path` | `…/pilot/source-pins.json` (absent) | `…/pilot/v4-launch/source-pins-native-final-v4.json` | See §0.1. |
| `nominal_admission_path` | `…/pilot/admissions/nominal.json` (absent) | `…/m0/readiness/tier-a-fresh-v4/admission.json` (absent until admitted) | The ledger stores the canonical receipt path, so a copy fails with "not issued by the readiness evaluator". |
| `output_dir` | `…/pilot/runs` | `…/pilot/v4-launch/runs/s2901`, `s2902`, `s2903` | One coordinator per seed. |
| `num_envs` | `4` | `8` | This is the admitted maximum (`le=8`). All milestones are divisible by 8, and critic warm-up becomes 20,480 decisions. |

These stay unchanged:

- `actor_workers=2`, `torch_threads=2`, `sequence_batch_size=2`, `device="cpu"`: 4 cores per run.
- `mixed_level_admission_path` (`pilot/admissions/levels-10-12.json`).
- The deck, deployment, strategy and protocol paths. The frozen protocol binds the `m0/data/roles_v2` paths.
- All `Literal` recipe fields.

## 3. Launch sequence (after `admission.json` exists)

**Preconditions (coordinator):**

- `report.json` has passed and `admission.json` has been issued.
- No `run_readiness_v2` or `collect_readiness_prefix` process is running. `launch.sh` refuses otherwise.
- The emulators are shut down cleanly and swap has come down.
- Free space is ≥ 35 GiB for the first launch (see `disk-plan.md`).
- Nobody runs `uv sync` or `pip` in main's `.venv` (the snapshot's `.venv` is a symlink to it). Each launch receipt records the torch and numpy versions and the `uv.lock` sha (`dc6ff5e2…`).

```sh
V4=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/v4-launch
# 1. Verification only (safe any time; refuses without admission)
bash $V4/launch.sh 2901 scripted --dry-run
# 2. Seed 2901: warm start, then the scripted smoke, then the scripted nominal run to 1M.
#    After that, the scratch arm (smoke, then nominal). The per-seed lock forces the arms to run in sequence.
nohup caffeinate -i bash -c "MIN_FREE_GB=35 bash $V4/launch.sh 2901 scripted && bash $V4/launch.sh 2901 scratch" > /dev/null 2>&1 < /dev/null &
# 3. After seed 2901's smoke check passes and its warm-start fit has ended (RAM, merge peak):
nohup caffeinate -i bash -c "MIN_FREE_GB=25 bash $V4/launch.sh 2902 scripted && bash $V4/launch.sh 2902 scratch" > /dev/null 2>&1 < /dev/null &
# 4. After seed 2902's warm-start fit has ended:
nohup caffeinate -i bash -c "MIN_FREE_GB=25 bash $V4/launch.sh 2903 scripted && bash $V4/launch.sh 2903 scratch" > /dev/null 2>&1 < /dev/null &
```

What `launch.sh SEED ARM` does. It sets cwd to the snapshot root, `CLASHER_ROOT` to the snapshot, `PYTHONPATH` to snapshot `src:scripts`, and uses `-B` with `OMP_NUM_THREADS=2` for the coordinator; children get `torch_threads` from `pilot_environment`. Logs go to `$V4/logs/launch-s<seed>-<arm>-<stamp>.log`.

1. **verify.** The config must be read-only. Then:
   - `verify_v4_launch.py` (pins, sidecar, configs);
   - **refuse if `admission.json` is absent** (exit 3);
   - `readiness_admission.py --ledger … verify --admission …`;
   - `verify_v4_launch.py --require-admission --config CFG`, which checks the receipt fields (attempt, `source_root` = snapshot, 354 pins equal to the declaration, game data, strategy, `levels=[11]`, nominal scope, report passed) and then runs the full `require_pilot_admission`. Any failure exits 3.

   After that it writes `launch-receipt-*.json`, which records the digests of the config, admission, pins, sidecar and scripts, plus the torch and numpy versions and `uv.lock`. `--dry-run` or `--through verify` stops here and prints the planned commands.
2. **preflight.** This runs `preflight_council_pilot.py --config CFG --seed S --arm A --num-envs 8 --actor-workers 2 --output-json $V4/preflight/seed<S>-<A>-<stamp>.json`: the no-update run of the real trainer argv in a temp dir. It must report bit-identical weights and `real_output_dir_created: false`. The stage is skipped if a passed record exists for the same config sha. Failure exits 4.
3. **smoke (seed 2901 only, each arm).** This runs `run_council_pilot.py --phase smoke --seed 2901 --arm A --execute`. On first use it performs the seed's warm start: about 499k public-script opportunities at level 11, a one-epoch exact fit, and a matched control. It then trains 100,000 decisions, and the nominal phase resumes from that 100k checkpoint. Both arms of seed 2901 get a smoke, so their lineages have the same shape. `smoke_check.py` requires:
   - every budget job `completed`;
   - warm-start hashes matching the files;
   - `validation_accuracy > control_validation_accuracy`;
   - corpus ≤ 500k;
   - `policy_decisions_000100000.pt` with `council_recipe` = (arm, 20 or 0, 0.02) and the config sha;
   - `rejected_actions=0` and no NaN or inf in the update lines;
   - non-empty `training-monitor.jsonl`;
   - launch receipts whose pins equal the v4 pin file.

   Seeds 2902 and 2903 skip the smoke but refuse to continue until some seed-2901 smoke check has passed. Failure exits 5.
4. **nominal.** This runs `run_council_pilot.py --phase nominal --seed S --arm A --execute`: the warm start if it is missing, then the arm to 1,000,000 decisions, then the automatic diagnostic matrix. The matrix plays 3 styles × 32 development-holdout games plus 3 × 32 Hog 2.6 games, at nominal level, for both the initializer and the 1M checkpoint. The diagnostic is for humans only. There is no automatic early stop and no strength claim. Stop manually only for correctness failures such as a crash, NaN or rejected commands.

Before starting seed 2902, record from seed 2901: peak RSS during the fit, the `corpus.npz` size, and `du` of `initialization/` during the merge. Use them to replace the estimates in `disk-plan.md`.

## 4. After 1M: mixed-league phase (needs the level-extension receipt)

This is unchanged from the v3 plan §6, except that everything is bound to v4:

- The extension must be issued with `readiness_admission.py --ledger $LEDGER extend-levels --base-admission $ATT/admission.json --level-evidence <LevelExtensionReceipt> --output pilot/admissions/levels-10-12.json`.
- It must have `levels ⊇ {10,11,12}` and `level_sampling_scope == "independent_cards"`.
- Regenerate the probe configs from the v4 snapshot: `prepare_readiness_level_extension.py --gamedata $SNAP/gamedata.json --base-admission $ATT/admission.json --native-attestation <file matching 864227bf…>`.
- The probe executor, the scalar independent-card study runner and the evidence assembler still do not exist. Without the receipt, the pilot halts at the 1M diagnostic.

Per seed, once the receipt exists: `run_council_pilot.py --config $V4/configs/council-pilot-v4-seed$S.toml --phase mixed-league --seed $S --execute`. Use the same snapshot env as `launch.sh`, one coordinator per seed, and both arms. This phase runs to 5M, then the final evaluation (1,416 games per seed and arm), then `strength-report.json`. Recipe claim per arm:

```sh
evaluate_council_pilot.py --protocol pilot/evaluation-protocol.json --arm $ARM \
  --seed-report $V4/runs/s2901/seed-2901/$ARM/strength-report.json \
  --seed-report $V4/runs/s2902/seed-2902/$ARM/strength-report.json \
  --seed-report $V4/runs/s2903/seed-2903/$ARM/strength-report.json \
  --output pilot/$ARM-recipe-strength-v4.json
```

A claim needs at least 2 of 3 seeds qualified. The best possible status is `replicated_strength_tier_b_pending`, and promotion is never automatic. Tier B prerequisites are unchanged (v3 plan §8). Tier B needs the native reference AVD and APKs, so keep them.

## 5. Time, cost and budget

Unchanged from the v3 plan §3, with an uncertainty of ±40%. Each run manages about 17–26 learner decisions/s and is bound by the learner. With 3 staggered coordinators:

- warm start: 3–5.5 h per seed;
- 1M per arm: 11–19 h, plus 1.6–2.7 h of diagnostic evaluation;
- 1M → 5M per arm: 48–77 h, plus 6–10 h of final evaluation;
- wall clock: about 6–9.5 days, plus any wait for the level receipt.

The three ledgers each allow 4,608 core-hours, so **the coordinator must enforce a combined 4,608 core-hour cap by hand**. The projected total is 1,600–2,500 core-hours.

## 6. Still blocked or at risk

1. **No admission yet.** v4 is at 164 of 1,024 branch results. `launch.sh` refuses until the ledger-issued `admission.json` verifies.
2. **Disk.** 14 GiB free now. About 30–34 GiB should be free after the emulators stop and swap returns, which covers 1M × 3 seeds. The full 5M pilot with one merge peak needs one approved cleanup from `disk-plan.md`.
3. **The level-extension tooling is missing**, so the pilot halts at 1M.
4. **The pin-scope decision is recorded in the sidecar, not in the ledger.** The orchestration scripts are hash-bound through `snapshot.json`, not through the admission. The alternative would be a new attempt whose declaration pins them.
5. **Shared `.venv` and absolute paths.** The `tier-a-fresh-v4` artifacts are re-hashed before every job, so they must not move during the pilot.
6. **Stale lock.** If `launch.sh` is killed with `-9`, remove `$V4/locks/seed-<S>.lock` by hand after confirming that no coordinator for that seed is alive. `LocalPilotBudget`'s own `flock` still protects the output dir.
7. **Evaluation can fail by design.** All 9 slices must be `noninferiority_supported`.
