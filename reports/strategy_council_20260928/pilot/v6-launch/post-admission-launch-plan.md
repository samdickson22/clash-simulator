# Council pilot: post-admission launch plan for Tier A v6 (prepared, not executed)

Prepared 2026-09-30 around 02:15 UTC (2026-09-29 evening local), while `m0-tier-a-fresh-v6` was running on the emulators. The read-only ledger showed the v6 declaration, 32 captures, the root seal, 848 branch claims (840 with results), 0 technical reruns, and no admission. This kit retargets `../v5-launch/`, which stays unchanged as a record (as does `../v4-launch/`).

While preparing this I ran no training, used no emulator or adb, wrote nothing to the ledger (every read used `mode=ro`), and edited no snapshot code. Every step ran under `nice -n 15` with `OMP_NUM_THREADS=2`. Paths are relative to `reports/strategy_council_20260928/` unless absolute. `$V6` is `pilot/v6-launch`.

## 0. What changed since the v5 kit

### 0.1 Source differences, native-final-v5 → native-final-v6

From the two `snapshot.json` manifests: v5 lists 749 files and v6 lists 760. Nothing was removed, 11 files were added and 9 changed. The sidecar records all 20 under `source_delta_vs_native_final_v5`, and `verify_v6_launch.py` checks the exact list on every run.

**Added (11):**
- `src/clasher/rl/readiness_tier_b.py`, `readiness_tier_b_ledger.py`, `readiness_tier_b_policy.py`, `readiness_tier_b_probes.py`: the Tier B learned-policy transfer records and ledger.
- `scripts/tier_b_readiness.py`, `scripts/collect_tier_b_prefix.py`: Tier B drivers.
- `scripts/build_level_extension_evidence.py`, `collect_level_extension_probes.py`, `run_level_extension_scalar_study.py`, `rehearse_level_extension_offline.py`, `level_extension_common.py`: the level-extension tooling that the v5 kit listed as missing.

**Changed (9), all readiness or transport code:** `rl/readiness_capture_ownership.py` (technical reruns; `AdmissionReceipt.technical_reruns`), `rl/training_readiness_v2.py` (`TechnicalRerunSummary`; `Report.technical_reruns`), `rl/readiness_execution.py`, `rl/readiness_job_selection.py`, `rl/readiness_prefix.py`, `rl/native_probe_transport.py`, `scripts/readiness_admission.py` (`--technical-rerun-policy`), `scripts/run_readiness_v2.py`, `scripts/read_native_public_levels.py`.

**Unchanged vs v5:** game data (`daa58b28…`), `uv.lock` (`dc6ff5e2…`), the strategy (`2be09f05…`), the native attestation (`864227bf…`), `input_files`, the interpreter and dependency environment, `entities.py`, and every module on the pilot path. That includes the four orchestration scripts, `council_pilot.py`, `council_warmstart.py` and `train_recurrent.py`, and a verify check asserts it. No pilot module imports the new Tier B or level-extension modules. One provenance note: v6's `snapshot.json` `source_root` is main (`/Users/sam/Desktop/code/clasher`), not a `-staging` dir as in v5. The snapshot bytes still equal the manifest.

### 0.2 Declaration differences, v5 → v6

These fields differ: `attempt_id`, the snapshot paths in `source_pins` and `input_pins` (plus the changed digests above), `root_bank_sha256`, `converter_manifest_sha256` / `pre_protocol.config_sha256`, the fresh episodes, and a new field **`technical_rerun_policy: "once_before_result"`**. The declaration now has **358 pins: 351 `src/clasher` modules + 7 readiness scripts** (v5: 347 + 7). The 7 readiness scripts are the same names as in v5.

### 0.3 Pin logic with the new modules (still passes without code changes)

`required_source_pins()` (checked by `_verify_declaration` inside `require_admission`) is `rglob("*.py")` over the snapshot's `src/clasher` plus 7 fixed script names. The four new `readiness_tier_b*.py` modules are therefore required, and they are declared: 358 required, all declared with the same digest. The pilot pin file is regenerated from the v6 declaration as exactly the 351 `src/clasher` pins. That equals every `*.py` under the snapshot's `src/clasher`, and it equals the `src/clasher` subset of `required_source_pins()`. The new Tier B and level-extension *scripts* are neither required nor in the pin file, which matches v5's treatment of non-readiness scripts. `verify_v6_launch.py` mirrors the `expected_source_pins` loop in `require_admission` against a stand-in receipt (`source_root` = snapshot, pins = the ledger's declaration). It passes with 0 mismatches for all three configs.

### 0.4 Admission receipt format with technical reruns: accepted

I read the pilot's path: `require_pilot_admission` (`council_pilot.py:216`) calls the v6 `require_admission`, which parses the file with `AdmissionReceipt.model_validate_json`, and then checks strategy, contract, levels and scope. Every pilot consumer goes through this path: `run_council_pilot.py`, `council_warmstart.py`, `train_recurrent.py` and `readiness_admission.py verify`. Nothing else parses the receipt. Preflight and the receipts only hash it.

- The v6 `AdmissionReceipt` declares `technical_reruns: tuple[TechnicalRerunSummary, ...] = ()`. Its serializer omits the field when it is empty, so a no-rerun receipt is byte-identical to a v5-style receipt.
- Tested with the v6 snapshot interpreter, synthetic receipts only: a receipt without the field, with `"technical_reruns": []`, and with one record all parse. The explicit `[]` compares equal to the ledger record that omits the field, so the `stored != receipt` check passes. JSON round-trips are stable. The level-extension path (`model_dump` → `model_validate`, strict) also accepts all three.
- A non-empty list must equal the ledger's `branch_reruns` summaries, and each rerun is re-verified by `_verify_technical_rerun`, which requires the declaration's `once_before_result`. That is the intended audit, not a format problem.
- **It would be rejected only by pre-v6 code.** In the v5 snapshot, `Record` is `extra="forbid", strict=True`, and `AdmissionReceipt` has no such field, so it fails with `technical_reruns: Extra inputs are not permitted [type=extra_forbidden]`. That applies even to `[]`. This kit runs everything from `native-final-v6`, so this cannot happen here. **No fix is needed.** The minimal safeguard is the one the kit already has: never point a v6 receipt at v5 (or older) code, and don't reuse the v5 kit with it. `verify_v6_launch.py` makes this a static check ("snapshot AdmissionReceipt accepts technical_reruns"), and with admission it logs the rerun count.

### 0.5 Main is still not used

At 02:15 UTC all 760 v6 files matched main byte for byte. But main's `gamedata.json` is still `3d99987c…` (`_verify_declaration` requires `daa58b28…`), and main is still being edited. The coordinator's decision stands: run from `native-final-v6`.

### 0.6 Kit changes vs v5

The scripts, stages, exit codes, seeds and config field changes are the same, with paths moved from v5 to v6. Beyond that:

- `make_pins.py` expects 351 pins. It asserts that the pinned `readiness_tier_b*` modules are exactly the 4 new ones, that the v5 → v6 delta is exactly the 11 + 9 files above, and that the orchestration scripts are unchanged. It also records `technical_rerun_policy` in the sidecar.
- `verify_v6_launch.py` has 54 static checks (v5: 48), with the counts changed to 351/358 and the delta checks rewritten. The 6 new ones:
  - declaration `technical_rerun_policy`;
  - the ledger copy of the declaration matches `declaration.json` on the rerun policy too;
  - the new tier_b modules are pinned;
  - the `required_source_pins()` `src/clasher` subset equals the pin file;
  - the pilot-path modules are unchanged vs v5;
  - the sidecar rerun policy, plus the receipt-format probe.

  With `--require-admission` it adds one informational check on the `technical_reruns` count.

The v3/v4/v5 findings still hold: `num_envs ≤ 8`, `actor_workers ≤ 4`, `torch_threads ≤ 4`, device cpu or mps; one coordinator per output dir, with both arms of a seed sharing its ledger; `run_council_pilot.py --freeze-source` is still unusable because it adds unadmitted council scripts.

## 1. Artifacts in `$V6`

| File | Purpose |
| --- | --- |
| `source-pins-native-final-v6.json` (read-only, sha `6c05064f…`) | The 351 admitted `src/clasher` modules with absolute snapshot paths and declaration digests. |
| `orchestration-pins-native-final-v6.json` (read-only, sha `fde33542…`) | The sidecar: the 4 orchestration scripts + `readiness_admission.py` bound by snapshot path and hash, the digests of `snapshot.json` (`e3de1df6…`), the declaration, the freeze receipt and the pin file, `technical_rerun_policy`, and the v5 → v6 delta. |
| `make_pins.py`, `make_configs.py` | Write-once generators (`open("x")`). |
| `verify_v6_launch.py` | 54 static checks, plus 3 protocol checks with `--protocol` and 12–13 admission checks with `--require-admission [--config]`. The last of those is the real, full `require_pilot_admission`. |
| `configs/council-pilot-v6-seed{2901,2902,2903}.toml` (read-only; sha `545cd0db…`, `8db99013…`, `3f9cb863…`) | One per seed; each covers both arms. |
| `launch.sh SEED ARM [--dry-run] [--through STAGE]` | Stages: verify, then preflight, then smoke (seed 2901 only), then nominal. |
| `smoke_check.py` | Automatic correctness gate after the smoke. |
| `disk-plan.md` | Space estimates and ranked cleanup candidates (list only). |
| `logs/`, `preflight/`, `locks/`, `runs/s<seed>/` | Launch logs and receipts, preflight records, the per-seed lock, and the output dirs. The output dirs do not exist yet. |

Verification at preparation time:

- `verify_v6_launch.py --protocol` passed 57/57 (54 static + 3 protocol). The frozen `pilot/evaluation-protocol.json` (`4a16b0b6…`) equals `build_protocol(config)` for all three configs.
- `verify_v6_launch.py --require-admission --config …seed2901.toml` passed 54/55. The one failure is `admission.json exists`, and the admission-dependent checks are skipped until it does.
- `bash -n launch.sh` passed.
- `launch.sh 2901 scripted --dry-run` passed the static stage (54/54), then exited 3 with `REFUSED: …/tier-a-fresh-v6/admission.json does not exist` (`logs/dry-run-s2901-scripted-20260930T021743Z.log`).

No launch receipt, preflight record, lock or run dir was created.

## 2. Config fields changed from `configs/council-pilot-local.toml`

The base file (sha `b7b12ab9…`) is untouched. Every generated config differs only in these fields, and `verify_v6_launch.py` enforces that the set is exact:

| Field | Base | v6 value | Why |
| --- | --- | --- | --- |
| header comment | "Unadmitted local pilot…" | 3-line v6 provenance comment | Comment only. |
| `source_root` | `/Users/sam/Desktop/code/clasher` | `…/m0/runtime-snapshots/native-final-v6` | Coordinator decision. It selects `<root>/.venv/bin/python` and `PYTHONPATH=<root>/src`, and satisfies the warm start's `__file__` root check. |
| `gamedata_path` | `…/m0/training-package/inputs/gamedata.json` | `…/native-final-v6/gamedata.json` | Its parent becomes the job cwd and `CLASHER_ROOT`. The trainer requires `clasher.paths.gamedata_path()` to equal it. The digest is unchanged (`daa58b28…`). |
| `source_pins_path` | `…/pilot/source-pins.json` (absent) | `…/pilot/v6-launch/source-pins-native-final-v6.json` | See §0.1. |
| `nominal_admission_path` | `…/pilot/admissions/nominal.json` (absent) | `…/m0/readiness/tier-a-fresh-v6/admission.json` (absent until admitted) | The ledger stores the canonical receipt path, so a copy fails with "not issued by the readiness evaluator". |
| `output_dir` | `…/pilot/runs` | `…/pilot/v6-launch/runs/s2901`, `s2902`, `s2903` | One coordinator per seed. |
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
- Nobody runs `uv sync` or `pip` in main's `.venv` (the snapshot's `.venv` is a symlink to it). Each launch receipt records the torch and numpy versions and the `uv.lock` sha (`dc6ff5e2…`, the same as v4 and v5).

```sh
V6=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/v6-launch
# 1. Verification only (safe any time; refuses without admission)
bash $V6/launch.sh 2901 scripted --dry-run
# 2. Seed 2901: warm start, then the scripted smoke, then the scripted nominal run to 1M.
#    After that, the scratch arm (smoke, then nominal). The per-seed lock forces the arms to run in sequence.
nohup caffeinate -i bash -c "MIN_FREE_GB=35 bash $V6/launch.sh 2901 scripted && bash $V6/launch.sh 2901 scratch" > /dev/null 2>&1 < /dev/null &
# 3. After seed 2901's smoke check passes and its warm-start fit has ended (RAM, merge peak):
nohup caffeinate -i bash -c "MIN_FREE_GB=25 bash $V6/launch.sh 2902 scripted && bash $V6/launch.sh 2902 scratch" > /dev/null 2>&1 < /dev/null &
# 4. After seed 2902's warm-start fit has ended:
nohup caffeinate -i bash -c "MIN_FREE_GB=25 bash $V6/launch.sh 2903 scripted && bash $V6/launch.sh 2903 scratch" > /dev/null 2>&1 < /dev/null &
```

What `launch.sh SEED ARM` does. It sets cwd to the snapshot root, `CLASHER_ROOT` to the snapshot, `PYTHONPATH` to snapshot `src:scripts`, and uses `-B` with `OMP_NUM_THREADS=2` for the coordinator; children get `torch_threads` from `pilot_environment`. Logs go to `$V6/logs/launch-s<seed>-<arm>-<stamp>.log`.

1. **verify.** The config must be read-only. Then:
   - `verify_v6_launch.py` (pins, sidecar, configs);
   - **refuse if `admission.json` is absent** (exit 3);
   - `readiness_admission.py --ledger … verify --admission …`;
   - `verify_v6_launch.py --require-admission --config CFG`, which checks the receipt fields (attempt, `source_root` = snapshot, 358 pins equal to the declaration, game data, strategy, `levels=[11]`, nominal scope, report passed; `technical_reruns` count logged) and then runs the full `require_pilot_admission`. Any failure exits 3.

   After that it writes `launch-receipt-*.json`, which records the digests of the config, admission, pins, sidecar and scripts, plus the torch and numpy versions and `uv.lock`. `--dry-run` or `--through verify` stops here and prints the planned commands.
2. **preflight.** This runs `preflight_council_pilot.py --config CFG --seed S --arm A --num-envs 8 --actor-workers 2 --output-json $V6/preflight/seed<S>-<A>-<stamp>.json`: the no-update run of the real trainer argv in a temp dir. It must report bit-identical weights and `real_output_dir_created: false`. The stage is skipped if a passed record exists for the same config sha. Failure exits 4.
3. **smoke (seed 2901 only, each arm).** This runs `run_council_pilot.py --phase smoke --seed 2901 --arm A --execute`. On first use it performs the seed's warm start: about 499k public-script opportunities at level 11, a one-epoch exact fit, and a matched control. It then trains 100,000 decisions, and the nominal phase resumes from that 100k checkpoint. Both arms of seed 2901 get a smoke, so their lineages have the same shape. `smoke_check.py` requires:
   - every budget job `completed`;
   - warm-start hashes matching the files;
   - `validation_accuracy > control_validation_accuracy`;
   - corpus ≤ 500k;
   - `policy_decisions_000100000.pt` with `council_recipe` = (arm, 20 or 0, 0.02) and the config sha;
   - `rejected_actions=0` and no NaN or inf in the update lines;
   - non-empty `training-monitor.jsonl`;
   - launch receipts whose pins equal the v6 pin file.

   Seeds 2902 and 2903 skip the smoke but refuse to continue until some seed-2901 smoke check has passed. Failure exits 5.
4. **nominal.** This runs `run_council_pilot.py --phase nominal --seed S --arm A --execute`: the warm start if it is missing, then the arm to 1,000,000 decisions, then the automatic diagnostic matrix. The matrix plays 3 styles × 32 development-holdout games plus 3 × 32 Hog 2.6 games, at nominal level, for both the initializer and the 1M checkpoint. The diagnostic is for humans only. There is no automatic early stop and no strength claim. Stop manually only for correctness failures such as a crash, NaN or rejected commands.

Before starting seed 2902, record from seed 2901: peak RSS during the fit, the `corpus.npz` size, and `du` of `initialization/` during the merge. Use them to replace the estimates in `disk-plan.md`.

## 4. After 1M: mixed-league phase (needs the level-extension receipt)

This is unchanged from the v3 plan §6, except that everything is bound to v6:

- The extension must be issued with `readiness_admission.py --ledger $LEDGER extend-levels --base-admission $ATT/admission.json --level-evidence <LevelExtensionReceipt> --output pilot/admissions/levels-10-12.json`.
- It must have `levels ⊇ {10,11,12}` and `level_sampling_scope == "independent_cards"`.
- Regenerate the probe configs from the v6 snapshot: `prepare_readiness_level_extension.py --gamedata $SNAP/gamedata.json --base-admission $ATT/admission.json --native-attestation <file matching 864227bf…>`.
- **New in v6:** the snapshot now contains the probe executor (`collect_level_extension_probes.py`), the scalar study runner (`run_level_extension_scalar_study.py`), the evidence declarer/assembler (`build_level_extension_evidence.py`), an offline rehearsal (`rehearse_level_extension_offline.py`) and `level_extension_common.py`. They are not on the pilot path, and I did not run them. Producing the receipt still needs native probe runs (emulators), so until it exists the pilot halts at the 1M diagnostic.

Per seed, once the receipt exists: `run_council_pilot.py --config $V6/configs/council-pilot-v6-seed$S.toml --phase mixed-league --seed $S --execute`. Use the same snapshot env as `launch.sh`, one coordinator per seed, and both arms. This phase runs to 5M, then the final evaluation (1,416 games per seed and arm), then `strength-report.json`. Recipe claim per arm:

```sh
evaluate_council_pilot.py --protocol pilot/evaluation-protocol.json --arm $ARM \
  --seed-report $V6/runs/s2901/seed-2901/$ARM/strength-report.json \
  --seed-report $V6/runs/s2902/seed-2902/$ARM/strength-report.json \
  --seed-report $V6/runs/s2903/seed-2903/$ARM/strength-report.json \
  --output pilot/$ARM-recipe-strength-v6.json
```

A claim needs at least 2 of 3 seeds qualified. The best possible status is `replicated_strength_tier_b_pending`, and promotion is never automatic. v6 adds Tier B tooling (`src/clasher/rl/readiness_tier_b*.py`, `scripts/tier_b_readiness.py`, `scripts/collect_tier_b_prefix.py`; runbook `m0/tier-b/RUNBOOK`). It is not on the pilot path. Tier B needs the native reference AVD and APKs, so keep them.

## 5. Time, cost and budget

Unchanged from the v3 plan §3, with an uncertainty of ±40%. Each run manages about 17–26 learner decisions/s and is bound by the learner. With 3 staggered coordinators:

- warm start: 3–5.5 h per seed;
- 1M per arm: 11–19 h, plus 1.6–2.7 h of diagnostic evaluation;
- 1M → 5M per arm: 48–77 h, plus 6–10 h of final evaluation;
- wall clock: about 6–9.5 days, plus any wait for the level receipt.

The three ledgers each allow 4,608 core-hours, so **the coordinator must enforce a combined 4,608 core-hour cap by hand**. The projected total is 1,600–2,500 core-hours.

## 6. Still blocked or at risk

1. **No admission yet.** At preparation time (2026-09-30 02:15 UTC) the read-only ledger showed v6 with 32 captures, the root seal, 848 branch claims (840 with results), 0 technical reruns and no admission. `launch.sh` refuses until the ledger-issued `admission.json` verifies.
2. **Disk.** 38 GiB free at 02:15 UTC (v5 kit: 51 GiB; v4 kit: 14 GiB). That covers 1M × 3 seeds and the 35 GiB first-launch floor with little margin. The Tier A v6 attempt dir is 3.0 GB and will grow a little more as the last branches land. The full 5M pilot with one merge peak needs one approved cleanup from `disk-plan.md`.
3. **No level-extension receipt yet.** The tooling now exists in the snapshot (see §4), but it needs native probe runs, so the pilot halts at 1M until the receipt is issued.
4. **The pin-scope decision is recorded in the sidecar, not in the ledger.** The orchestration scripts are hash-bound through `snapshot.json`, not through the admission. The alternative would be a new attempt whose declaration pins them.
5. **Shared `.venv` and absolute paths.** The `tier-a-fresh-v6` artifacts are re-hashed before every job, so they must not move during the pilot.
6. **Stale lock.** If `launch.sh` is killed with `-9`, remove `$V6/locks/seed-<S>.lock` by hand after confirming that no coordinator for that seed is alive. `LocalPilotBudget`'s own `flock` still protects the output dir.
7. **Evaluation can fail by design.** All 9 slices must be `noninferiority_supported`.
