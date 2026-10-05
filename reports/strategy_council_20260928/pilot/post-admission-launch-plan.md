# Council pilot: post-admission launch plan (prepared, NOT executed)

Prepared 2026-09-28, ~20:15 PDT (03:15 UTC Sep 29), while Tier A attempt `m0-tier-a-fresh-v3` was running. This is read-only analysis. I ran no training, emulator/adb commands or benchmarks, edited no config, and created no pins. Every command below is meant for **after** `m0/readiness/tier-a-fresh-v3/admission.json` exists. Paths below are relative to `reports/strategy_council_20260928/` unless absolute.

At writing time, the native shards had finished about 17–18 of 64 jobs each in about 86 minutes, and the scalar side had 475 of 512. If that rate holds, the branches finish around 07:00–08:00 UTC Sep 29. Evaluation follows, and an admission is issued only if `report.json` passes.

## 0. Findings that change the launch recipe

1. **The pilot's own source freeze fails the admission check.** `run_council_pilot.py --freeze-source` pins every `src/clasher/**/*.py` file plus `scripts/run_council_pilot.py`, `scripts/run_council_warmstart.py` and `scripts/evaluate_council_pilot.py`. `require_admission` checks that every pinned file appears in `receipt.source_pins` with the same digest. The v3 declaration pins 353 files: all 346 `src/clasher` modules plus 7 readiness scripts. It does **not** pin the three council scripts. I simulated this read-only against the v3 snapshot. The result was 349 pilot-freeze files, and exactly those 3 scripts were unadmitted. So `--freeze-source` followed by `--execute` would raise `requested source path/role differs from admitted module`. The fix is in step 2: the pin file holds exactly the admitted `src/clasher` subset, and a sidecar records the script hashes. This needs a recorded coordinator decision.
2. **The pilot must run from the admitted snapshot, not from main.** Main's `src/clasher` differs from the admitted pins in `rl/native_frame_storage.py` and in the added file `rl/native_rich_delta.py`. Both belong to the in-progress native-speed work. Main's `gamedata.json` (`3d99987c…`) also differs from the admitted workspace game data (`daa58b28…`), which `_verify_declaration` checks through `Path(__file__).parents[3]/gamedata.json`. Every pilot-path file, including `council_*.py`, `train_recurrent.py`, `imitation.py`, `eval.py`, `entities.py`, `battle.py` and the four council scripts, is byte-identical between main and `m0/runtime-snapshots/native-final-v3`. Running from the snapshot therefore loses no pilot feature.
3. **The admitted code limits the hardware layout.** `CouncilPilotConfig` fixes `num_envs ≤ 8`, `actor_workers ≤ 4`, `torch_threads ≤ 4`, `sequence_batch_size ≤ 4` and `device ∈ {cpu, mps}`. `council_pilot.py` is an admitted pinned module. Raising the strategy's 64 environments or adding CUDA therefore means a code change, a new snapshot and a new admission. That is not part of this launch.
4. **The concurrency ceiling is three runs.** `LocalPilotBudget` holds one lock per `output_dir` and runs one child at a time. `validate_council_initial_policy` also requires the initializer's `BudgetSnapshot.ledger_path` to equal the run's own ledger, so both arms of a seed must share one coordinator. The only parallelism the code supports is **one coordinator per seed**, using three config files that differ only in `output_dir`.
5. **Tooling for the mixed-level receipt is missing.** The snapshot contains the verifier (`readiness_level_extension.verify_level_extension_receipt`) and `readiness_admission.py extend-levels`. It has no script that executes the four native level probes, runs the scalar independent-card adaptation study, or assembles the `LevelExtensionReceipt`. The existing draft probe configs (`m0/level-extension/prospective-configs/manifest.json`) have status `draft_missing_nominal_admission` and are bound to game data `3d99987c…`, not the admitted `daa58b28…`. They must be regenerated.
6. **Tier B is not implemented.** It exists only as the flag `tier_b_required=True`.

## 1. Command sequence

Shell prelude for every step. Run all steps from the snapshot root; v1 failed because it was launched from /tmp.

```sh
ROOT=/Users/sam/Desktop/code/clasher
RC=$ROOT/reports/strategy_council_20260928
SNAP=$RC/m0/runtime-snapshots/native-final-v3
ATT=$RC/m0/readiness/tier-a-fresh-v3
LEDGER=$RC/readiness-v2.sqlite
PYENV=(env CLASHER_ROOT=$SNAP PYTHONPATH=$SNAP/src PYTHONDONTWRITEBYTECODE=1)
PY=("${PYENV[@]}" $SNAP/.venv/bin/python -B)
cd $SNAP
```

### Step 0: Preconditions (coordinator)

- Tier A v3 is complete: `report.json` has status `passed` and `admission.json` exists. No `run_readiness_v2` or `collect_readiness_prefix` process is alive.
- All emulators are shut down cleanly by their owner. Then confirm that `sysctl vm.swapusage` has fallen from about 19.9 GB used and `df -h /System/Volumes/Data` shows at least 40 GiB free (see §4).
- Nobody runs `uv sync` or `pip` in main's `.venv` for the whole pilot. The snapshot `.venv` is a symlink to it. Record `$SNAP/.venv/bin/python -c "import torch,numpy;print(torch.__version__,numpy.__version__)"` and `shasum -a 256 $SNAP/uv.lock` in the launch receipt.

### Step 1: Verify admission

```sh
"${PY[@]}" $SNAP/scripts/readiness_admission.py --ledger $LEDGER verify --admission $ATT/admission.json
# expect: m0-tier-a-fresh-v3 scalar_public_policy_only
"${PY[@]}" - <<'EOF'
import json, hashlib
from pathlib import Path
att = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/readiness/tier-a-fresh-v3")
r = json.loads((att / "admission.json").read_text())
snap = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/runtime-snapshots/native-final-v3").resolve()
assert Path(r["source_root"]).resolve() == snap, r["source_root"]
assert r["levels"] == [11] and r["level_sampling_scope"] == "nominal"
assert r["gamedata_sha256"] == "daa58b28cf4e45d753e83ca69a76794285b63704e62363ee58e617af3a30ecc3"
assert r["strategy_sha256"] == "2be09f05cfda1a76a2536593df363afde8112377afa70bec55b9489a564da17f"
assert r["training_scope"] == "scalar_public_policy_only" and len(r["source_pins"]) == 353
assert json.loads(Path(r["report_path"]).read_text())["status"] == "passed"
print("admission ok", hashlib.sha256((att / "admission.json").read_bytes()).hexdigest())
EOF
```

Time the `verify` call. `require_pilot_admission` re-runs the full check, including re-hashing 1,024 branch artifacts, before every warm start, training job and evaluation command. That is about 40 calls per run.

### Step 2: Pin sources to the admitted snapshot (no `--freeze-source`)

Coordinator decision to record: the pilot pin file is exactly the admitted `src/clasher` subset of `receipt.source_pins`. The three orchestration scripts are unadmitted, so they are bound through `snapshot.json` in a sidecar. The alternative is a new Tier A attempt whose declaration pins those scripts.

```sh
"${PY[@]}" - <<'EOF'
import hashlib, json
from pathlib import Path
RC = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928")
SNAP = (RC / "m0/runtime-snapshots/native-final-v3").resolve()
adm = RC / "m0/readiness/tier-a-fresh-v3/admission.json"
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
receipt = json.loads(adm.read_text())
src = (SNAP / "src/clasher").resolve()
pins = {k: v for k, v in sorted(receipt["source_pins"].items()) if Path(k).resolve().is_relative_to(src)}
disk = {str(p.resolve()) for p in src.rglob("*.py")}
assert len(pins) == 346 and set(map(lambda k: str(Path(k).resolve()), pins)) == disk
assert all(sha(k) == v for k, v in pins.items())
with (RC / "pilot/source-pins-native-final-v3.json").open("x") as f:
    json.dump(pins, f, indent=2); f.write("\n")
manifest = json.loads((SNAP / "snapshot.json").read_text())["source_files"]
names = ["scripts/run_council_pilot.py", "scripts/run_council_warmstart.py",
         "scripts/evaluate_council_pilot.py", "scripts/preflight_council_pilot.py"]
scripts = {n: sha(SNAP / n) for n in names}
assert all(manifest[n] == h for n, h in scripts.items())
side = {"schema": "council-pilot-orchestration-pins-v1",
        "reason": "orchestration scripts are outside the v3 admitted source_pins; bound via snapshot manifest",
        "snapshot_manifest_sha256": sha(SNAP / "snapshot.json"),
        "admission_sha256": sha(adm),
        "source_pins_sha256": sha(RC / "pilot/source-pins-native-final-v3.json"),
        "scripts": {str(SNAP / n): h for n, h in scripts.items()}}
with (RC / "pilot/orchestration-pins-native-final-v3.json").open("x") as f:
    json.dump(side, f, indent=2); f.write("\n")
EOF
chmod a-w $RC/pilot/source-pins-native-final-v3.json $RC/pilot/orchestration-pins-native-final-v3.json
```

### Step 3: Write the three per-seed configs (field list in §2), then validate

Create `configs/council-pilot-v3-seed2901.toml`, `-seed2902.toml` and `-seed2903.toml` as copies of `configs/council-pilot-local.toml` with the §2 changes. Leave the existing file (SHA `b7b12ab9…`) untouched, because the preflight receipt refers to it. Make the new files read-only before the first `--execute`. Both the budget ledger and every resumed checkpoint check the config SHA, so a config can never change between the smoke, nominal and mixed-league phases.

```sh
"${PY[@]}" - <<'EOF'
from pathlib import Path
from clasher.rl.council_pilot import load_pilot_config, load_source_pins, require_pilot_admission
from clasher.rl.council_evaluation import load_protocol, build_protocol
for s in (2901, 2902, 2903):
    c = load_pilot_config(Path(f"/Users/sam/Desktop/code/clasher/configs/council-pilot-v3-seed{s}.toml"))
    assert len(load_source_pins(c)) == 346
    r = require_pilot_admission(c, Path(c.nominal_admission_path), levels=(11,))
    assert load_protocol(Path(c.evaluation_protocol_path)) == build_protocol(c)  # protocol 4edf03f2… unchanged
    print(s, r.attempt_id, r.levels, c.output_dir)
EOF
"${PY[@]}" $SNAP/scripts/run_council_pilot.py --config $ROOT/configs/council-pilot-v3-seed2901.toml --phase nominal --seed 2901   # plan print only
"${PY[@]}" $SNAP/scripts/preflight_council_pilot.py --config $ROOT/configs/council-pilot-v3-seed2901.toml \
  --seed 2901 --arm scripted --arm scratch --num-envs 8 --actor-workers 2 \
  --output-json $RC/pilot/launch-preflight-v3-20260929.json      # no-update, temp dir, ~1 min
```

The preflight must report bit-identical weights and `real_output_dir_created: false`. The existing `launch-preflight-20260928.json` ran from main, with training-package game data and 2 environments, so it does not cover this layout.

### Step 4: Scripted demonstrations, warm-start fit and correctness smoke (seed 2901 first)

The runner performs the warm start implicitly before the first arm of each seed. For each seed, `run_council_warmstart.py` collects complete public-script games at level 11, with styles balanced, pressure and defense, deck families split 80/20 by parent, and every five-tick opportunity including waits. It stops when fewer than one worst-case game (1,201 decisions) fits under **500,000 learner opportunities**, which gives about 499k opportunities, or about 650 games at the observed ~770 decisions per game. It then merges the games into `corpus.npz` and fits one epoch of exact imitation. The fit uses batch 128, sequence 128, lr 1e-4, current-weight full-prefix recurrence and a matched untrained control checkpoint. Outputs go to `<output_dir>/seed-S/initialization/{scripted.pt, scripted-random-control.pt, scripted-demonstrations/result.json}`.

```sh
mkdir -p $RC/pilot/runs-v3-s2901
nohup caffeinate -i "${PYENV[@]}" $SNAP/.venv/bin/python -B $SNAP/scripts/run_council_pilot.py \
  --config $ROOT/configs/council-pilot-v3-seed2901.toml --phase smoke --seed 2901 --arm scripted --execute \
  > $RC/pilot/runs-v3-s2901/coordinator-smoke.log 2>&1 < /dev/null &
```

This single command does three things for seed 2901: collects the demonstrations, fits the warm start, and runs a **smoke of 100,000 decisions on the scripted arm**. The smoke covers the scripted arm's 20-update critic warm-up (20 × 8 × 128 = 20,480 decisions), target-KL 0.02, per-match opponents and budget ownership. It continues the same checkpoint lineage, so the nominal run resumes from it.

Smoke acceptance (manual, correctness only):

- Every `resource-budget.json` job is `completed`.
- `result.json` hashes match the files.
- Warm-start validation accuracy is above the control's.
- The log shows `rejected_actions=0` and no NaN.
- `training-monitor.jsonl` has rows.
- `launch-*.json` source pins match the file from step 2.
- A 100k checkpoint exists with `council_recipe.critic_warmup_updates == 20`.

Before starting the other seeds, measure seed 2901's peak RSS during the fit, the `corpus.npz` size and the transient disk use of the merge (see §4).

### Step 5: Nominal PPO to the one-million-decision diagnostic, all 3 seeds × 2 arms

```sh
for S in 2901 2902 2903; do   # start 2902 after 2901's fit ends, and 2903 after 2902's (RAM)
  mkdir -p $RC/pilot/runs-v3-s$S
  nohup caffeinate -i "${PYENV[@]}" $SNAP/.venv/bin/python -B $SNAP/scripts/run_council_pilot.py \
    --config $ROOT/configs/council-pilot-v3-seed$S.toml --phase nominal --seed $S --execute \
    > $RC/pilot/runs-v3-s$S/coordinator-nominal.log 2>&1 < /dev/null &
done
```

Each coordinator runs the warm start for its seed if missing, then the **scripted arm to 1,000,000 decisions**, resuming from the smoke for seed 2901. It then runs the **scratch arm to 1,000,000 decisions** from the matched control, with no critic warm-up. Both arms play at level 11 against a per-match opponent drawn from the equal script (balanced/pressure/defense) plus initial-policy mixture.

Each arm writes the diagnostic checkpoint `seed-S/<arm>/policy_decisions_001000000.pt`. The runner then **automatically** runs the diagnostic matrix for both the initializer and the 1M checkpoint. For each, that is 3 styles × 32 development-role holdout games plus 3 × 32 Hog 2.6 games at nominal level, 192 games in all. The diagnostic seeds are disjoint from the final ones. Results go to `seed-S/<arm>/diagnostic-evaluation/`.

The diagnostic informs humans only. `evaluate_seed` grades final cells only, there is no automatic early stop, and no strength claim can come from it. Stop a run manually only for correctness failures such as crashes, NaN or rejected commands. Review `training-alarms.jsonl` and the `TRAINING_ALARM` lines. Alarms are monitoring-only, and any rollback is a manual, recorded decision.

### Step 6: Level-mix phase from 1M to 5M (needs the extension receipt)

**Required receipt.** `pilot/admissions/levels-10-12.json` must be issued by the ledger:

```sh
"${PY[@]}" $SNAP/scripts/readiness_admission.py --ledger $LEDGER extend-levels \
  --base-admission $ATT/admission.json --level-evidence <verified LevelExtensionReceipt.json> \
  --output $RC/pilot/admissions/levels-10-12.json
```

It must have `levels ⊇ {10,11,12}` and **`level_sampling_scope == "independent_cards"`**. `require_pilot_admission` rejects `uniform_cards`. Independent-card scope also requires, bound in the evidence:

- an approved `readiness-level-randomization-decision-v1` for the v3 base admission;
- a scalar independent-card adaptation study;
- four native probes (uniform cards at 10 and 12, asymmetric Kings, both seats, scaling-sensitive checks and consequential rankings), whose attestation equals the declaration's `864227bf…` and whose game data is `daa58b28…`.

Regenerate the probe configs from the snapshot with `scripts/prepare_readiness_level_extension.py --nominal-config <v3 level-11 native config> --gamedata $SNAP/gamedata.json --base-admission $ATT/admission.json --native-attestation <attestation file matching 864227bf…> --output $RC/m0/level-extension/v3-bound-configs`. The probe executor, the scalar study runner and the evidence assembler must still be written (finding 5). The probes need **one emulator**. Run them right after admission, in parallel with seed 2901's warm-start collection, before PPO saturates the CPU.

Then, per seed, after its nominal phase completes:

```sh
nohup caffeinate -i "${PYENV[@]}" $SNAP/.venv/bin/python -B $SNAP/scripts/run_council_pilot.py \
  --config $ROOT/configs/council-pilot-v3-seed$S.toml --phase mixed-league --seed $S --execute \
  > $RC/pilot/runs-v3-s$S/coordinator-mixed.log 2>&1 < /dev/null &
```

Each arm resumes from its latest checkpoint to **5,000,000 decisions** (`policy_decisions_005000000.pt`). Levels are drawn per match: half the games stay nominal and half draw card/tower levels 10–12. The 1M checkpoint and every later saved checkpoint enter the historical pool. The opponent mix becomes 25% scripts, 50% history (the initial policies stay eligible) and 25% current self-play, fixed per match. The final evaluation and `strength-report.json` follow automatically.

**If the receipt is absent at 1M,** the runner refuses the `mixed-league` phase because the admission file is missing or lacks the scope. The trainer's `level_randomization_after=1_000_000` and all council checks are pinned in admitted code. Continuing nominal-only past 1M would require a code and config change, which breaks the v3 source-pin match. **The pilot therefore halts at the 1M diagnostic.** Keep the checkpoints and diagnostic results, and resume with the same configs once the receipt is issued. Hold the CPU for the level-extension work in the meantime.

### Step 7: Evaluation (automatic per seed and arm, plus a manual recipe step)

The final block per finalist is the 5M checkpoint versus its own initializer, on identical frozen cases, with a stochastic temperature-1 decoder. It covers acceptance-role holdout games: 86 × 3 styles × {nominal, mixed} = **516 paired games**, plus a Hog 2.6 slice of 32 × 3 × 2 = 192 games. That is 1,416 games per (seed, arm) and 8,496 in total. Each cell is validated and bound through `*.complete.json`.

`evaluate_council_pilot.py` computes:

- the gain in mean match score, with a two-sided 95% cluster bootstrap (20,000 replicates, clustered by matchup seed);
- the requirements gain ≥ 0.05 with lower CI > 0, and candidate score > 0.5 against the fixed script pool;
- nine predeclared slices, each of which must reach `noninferiority_supported` (lower CI > −0.10, at least 40 games and at least 20 clusters): heldout nominal, mixed, mixed-disadvantaged, Hog 2.6 nominal and mixed, and four held-out families.

Recipe claim per arm (manual, because the seeds use separate output dirs):

```sh
for ARM in scripted scratch; do
  "${PY[@]}" $SNAP/scripts/evaluate_council_pilot.py --protocol $RC/pilot/evaluation-protocol.json --arm $ARM \
    --seed-report $RC/pilot/runs-v3-s2901/seed-2901/$ARM/strength-report.json \
    --seed-report $RC/pilot/runs-v3-s2902/seed-2902/$ARM/strength-report.json \
    --seed-report $RC/pilot/runs-v3-s2903/seed-2903/$ARM/strength-report.json \
    --output $RC/pilot/$ARM-recipe-strength-v3.json
done
```

A recipe claim needs at least 2 of 3 seeds qualified. The status is at best `replicated_strength_tier_b_pending`, and `promotion_authorized` is always false.

### Step 8: Tier B prerequisites (before promotion or continuation beyond the pilot)

- Implement the policy-conditioned block, which does not exist yet:
  - a root sampler over frozen finalist games, stratified by supported deck, phase and seat;
  - the frozen policy supplying ranked alternatives for the four candidate roles;
  - 30 representative roots, of which at least 15 are consequential non-wait (otherwise inconclusive);
  - the same regret, same-engine floor and automatic per-class bias rules;
  - every root kept in failure accounting;
  - separate targeted exploit probes, plus mixed-level transfer and exploit checks, as required by the level-extension decision.
- Put this in a **new snapshot**. It may differ from v3; the pilot checkpoints are frozen inputs to it. Fresh-bank freshness checks must cover the v7, development-v2 and v3 ledgers.
- Freeze roots and candidates before outcomes. Execute with 4 × 4 × 30 × 2 = 960 branches, about Tier A scale (roughly 5–6 h on 8 emulators). Emulators and PPO cannot share the machine efficiently, so run it after PPO finishes or while PPO is paused.

## 2. Config fields to change (not edited)

Base: `configs/council-pilot-local.toml`. Write three new files that differ only in `output_dir`.

| Field | Current | Change to | Why |
| --- | --- | --- | --- |
| `source_root` | `/Users/sam/Desktop/code/clasher` | `…/m0/runtime-snapshots/native-final-v3` | Pins must equal the admitted modules (main differs in 2 files and is being edited). It also selects the interpreter (`<root>/.venv/bin/python`), sets `PYTHONPATH=<root>/src`, and satisfies the warm start's `__file__` root check. |
| `gamedata_path` | `…/m0/training-package/inputs/gamedata.json` (stale package; same bytes) | `…/m0/runtime-snapshots/native-final-v3/gamedata.json` | Its parent becomes `CLASHER_ROOT` and the job cwd. The trainer and warm start require `clasher.paths.gamedata_path()` to equal this path. The training package is not the admitted runtime. SHA stays `daa58b28…`. |
| `nominal_admission_path` | `…/pilot/admissions/nominal.json` (does not exist) | `…/m0/readiness/tier-a-fresh-v3/admission.json` | The ledger stores the canonical receipt path. A copy fails with "not issued by the readiness evaluator". |
| `source_pins_path` | `…/pilot/source-pins.json` (does not exist) | `…/pilot/source-pins-native-final-v3.json` (step 2) | Produced by step 2 without the 3 unadmitted scripts. A new name avoids confusion with the `--freeze-source` format. |
| `output_dir` | `…/pilot/runs` | `…/pilot/runs-v3-s2901`, `…-s2902`, `…-s2903` (one per file) | One coordinator per seed is the only supported concurrency. |
| `num_envs` | `4` | `8` | Mac tuning recommendation. Milestones stay divisible. Periodic checkpoints drop from ~49 to ~24 per run, and critic warm-up becomes 20,480 decisions. |
| `actor_workers` / `torch_threads` / `sequence_batch_size` / `device` | 2 / 2 / 2 / cpu | unchanged | Charges 4 cores per run, 12 total for 3 runs. MPS benchmarked slower. |
| `mixed_level_admission_path` | `…/pilot/admissions/levels-10-12.json` | unchanged | Issue the extension with `--output` equal to exactly this path. |
| deck paths (`m0/data/roles_v2/*`), `deployment_decks_path`, `evaluation_protocol_path`, `strategy_path` | — | unchanged | The frozen protocol (`4edf03f2…`) binds these exact deck paths. Moving them to `$SNAP/roles/` (same bytes) would change the protocol cells. |

The budget ceilings stay at 4,608 CPU core-hours and 72 accelerator-hours per file (both are Literals). **Three ledgers would allow 3 × 4,608, so the coordinator must enforce a combined cap of 4,608 by hand.** The projected total is about 1,600–2,500 core-hours.

## 3. Time and cost estimates

**Measured inputs.** All were taken on this Mac mini under load average 12–13 on 12 cores (8P + 4E) from other jobs, so they are pessimistic:

- Collection, in one process with 2 threads: 41.8 (4 envs) to 44.6 (8 envs) learner decisions/s. That includes exact-prefix reconstruction at chunk start, about 25% of rollout time.
- Reconstruction cost: 2.4–2.5 ms per replayed step (batch 1).
- Synthetic forward/backward: 3.24 s per 2-sequence × 128-step minibatch.
- Average match length: about 770 learner decisions (214 games/h at 45.8 decisions/s). Average replayed prefix: about 330 steps.
- Full PPO update cost has never been measured.

**PPO update model.** With N environments there are N sequences per update, minibatch 2 and 2 epochs, so N forward/backward minibatch passes: 3.24·N s. Full-prefix reconstruction runs per minibatch per epoch: 2 × N × 330 × 2.5 ms ≈ 1.65·N s. The update therefore costs about **4.9·N s per 128·N decisions, about 38 ms per decision**. Collection costs 11–22 ms per decision (45–90 decisions/s; the high end assumes an unloaded host and 2 worker processes). The effective rate is **about 17–26 learner decisions/s per run, independent of N**. The run is learner-bound, because the update is 60–75% of wall time.

**Why 64 environments do not help here.** At 64 environments, one update is 64 × 4.9 s ≈ 5.2 min for 8,192 decisions, and collection adds 1.5–3 min. The cost per decision is unchanged, and the admitted schema forbids more than 8 anyway.

**Mac mini with emulators off, 3 concurrent seed coordinators** (about 10–15% sharing penalty; each run uses about 2–4 active cores):

| Stage | Per seed (both arms sequential) |
| --- | --- |
| Warm start: 500k collection 1–2 h, merge 0.3–0.5 h, one-epoch fit with prefix replay 1.5–3 h | 3–5.5 h (stagger seeds for RAM) |
| Smoke of 100k (seed 2901 scripted only; counts toward that lineage) | 1–1.7 h |
| Nominal 1M per arm: 11–19 h, plus diagnostic eval of 384 games at ~15–25 s/game (1.6–2.7 h) | 25–43 h |
| Mixed 4M per arm: 48–77 h, plus final eval of 1,416 games (6–10 h) | 108–174 h |
| **Wall clock** | **about 140–225 h (6–9.5 days)**, plus any wait at 1M for the level receipt |

Run everything sequentially in one coordinator and it takes about 16–24 days. **Recommendation: 3 concurrent coordinators, one per seed, started in a staggered way.** Four or more is not possible without code changes. It would also land on the E-cores and push RAM into swap. Budget-ledger charge: about 1,600–2,500 core-hours in total, and 0 accelerator-hours.

**DigitalOcean**, under the same admitted code (CPU only, ≤ 8 envs, ≤ 3 coordinators). Assumptions: one x86 vCPU is 0.5–0.6 of an M4 P-core for this Python/small-batch workload; thread scaling for the 2-sequence minibatch from 2 to 4 threads is about 1.3×; prices are as given (not verified); storage and egress are negligible.

- **48-vCPU CPU-optimized at $1.50/h.** Use 3 coordinators, each with `actor_workers=4` and `torch_threads=4` (8 vCPU each; 24 of the 48 vCPU cannot be used). Per-run speed is about 0.8–1.1× the Mac, so wall time is about the same, 140–230 h, costing **about $210–345**. There is no speedup; the only benefit is freeing the Mac for native work. A 24–32 vCPU droplet would do the same work for less. It also requires recreating the absolute `/Users/sam/Desktop/code/clasher/...` tree: the snapshot, ledger, all 1,024 branch artifacts, calibration receipt, configs and catalog. `require_admission` re-verifies those paths, and Linux torch wheels will not be bitwise-identical.
- **RTX 4000 Ada at $0.76/h.** The admitted config cannot use CUDA (`device` is limited to cpu or mps). As a CPU host with its reported ~8 vCPU (assumption; verify), you would need one droplet per seed: 3 × $0.76 × 140–230 h ≈ **$320–525** with the GPU idle. Not recommended.
- **Hypothetical, not admissible now.** A 64-env CPU learner on the 48-vCPU box (roughly 60–90 decisions/s per run, so 30M decisions in about 95–140 h, about $140–210), or a GPU learner, requires changing the pinned `council_pilot.py`. That means a new snapshot plus a new admission.

## 4. Blockers and risks

1. **No admission yet.** Tier A v3 is still running, and the pilot cannot start unless `report.json` passes. The mixed phase also needs the separate `independent_cards` extension receipt. Its tooling is missing, and the draft probe configs are bound to the wrong game data and to no base admission. Without it the pilot stops at 1M.
2. **Source-pin mismatch.** The `--freeze-source` output always fails because of the 3 unadmitted council scripts. Running from main also fails (2 modules differ, and main's workspace game data differs). This needs step 2's subset pins with an explicit coordinator decision, or a new attempt that pins the scripts.
3. **Stale config.** `source_root`, `gamedata_path` (training package), `nominal_admission_path` and `source_pins_path` must change (§2). `implementation/source_sha256.json` and `launch-preflight-20260928.json` are stale (for example, the recorded `run_council_pilot.py` digest `ad75c78c…` versus the current `bc10f171…`). Re-run the preflight on the snapshot.
4. **Disk: 16 GiB free now; about 35–40 GiB needed.**
   - PPO checkpoints are about 31–35 MB each (2.6M-param weights of ~10.4 MB plus AdamW moments of ~20.8 MB, plus metadata; not yet measured). At 8 envs that is ~24 periodic saves every 200 updates, plus 1M/5M milestone copies, so about 0.9–1 GB per run and about 6 GB for 6 runs (about 10 GB at 4 envs).
   - Warm-start corpora are about 2–5 GB per seed retained (shards plus compressed corpus; unmeasured). The merge also builds uncompressed memmap temp files in the same directory, an estimated 8–12 GB at ~16–25 KB/sample × 500k.
   - Tier A artifacts, 1.4 GB so far, keep growing.
   - Emulator swap (the VM volume uses 21 GiB) should be returned after shutdown. Beyond that, freeing space means moving old `artifacts/` or `datasets/` (36 GB each) or `checkpoints/` (4 GB), which needs Sam's approval. Do not delete anything unilaterally.
5. **Memory (24 GB).** Estimated 3–5 GB per PPO run across the learner and 2 workers, so 9–15 GB for 3 runs. `load_corpus` copies the whole corpus into RAM for the fit (estimated 8–12 GB, unmeasured), so overlapping fits across seeds would swap. Stagger the seeds and measure on seed 2901. Swap is currently 19.9 GB used; do not launch until the emulators are down.
6. **Concurrency and accounting.** One coordinator per output dir means 3 ledgers, and the combined 4,608 core-hour cap is manual. Configs must stay byte-identical across phases, because the ledger and resume both check the config SHA.
7. **Interruption cost.** Checkpoints come every 200 updates, about 205k decisions (2–3.5 h) at 8 envs. A still-live child blocks restart, and a restart resumes from the latest checkpoint.
8. **Shared dependency environment.** `$SNAP/.venv` points to main's `.venv`, which is unhashed. Any `uv sync` during the pilot silently changes torch or numpy.
9. **Evaluation can fail by design.** All 9 slices must be `noninferiority_supported`. `insufficient_coverage` or `inconclusive` means not qualified. `heldout/family/pilot-acceptance-stress` plans only 24 pair clusters, so in practice it needs a clearly positive gain on that family (roughly ≥ 0.07) to clear −0.10.
10. **Unmeasured costs.** Full PPO update throughput, the per-call cost of admission re-verification (about 40 calls per run), eval-game speed, and warm-start RAM and disk were all extrapolated from contended short benchmarks. Treat §3 as ±40%.
11. **Tier B is unimplemented,** and it competes with PPO for the CPU (emulators). No policy can be called viable or promoted before it passes.
