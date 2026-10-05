#!/usr/bin/env python3
"""Verify the v7r2c continuation kit: pilot runtime, source scope, sidecar, the
config, the continuation declaration, warm-start reuse and (optionally) the
m0-tier-a-fresh-v7 admission.

v7r2c continues v7r2 seed 2903 scripted from its one-million-decision
checkpoint on pilot-runtime-v4 under the unchanged v7r2 recipe (gae 0.95, no
anchor, entropy factorized-v2, scripted-only initial opponents, 64/8/4,
target_kl 0.02, lr 1e-4) with critic_warmup_updates 0 and phase_order
nominal -> nominal-league. The admission stays bound to native-final-v7 and is
accepted through verify_pilot_source_scope and require_pilot_admission.

Continuation checks: the declared checkpoint exists with the declared digest
(also recorded in v7r2-launch/stopped-for-recipe-fix.json), the declared source
config digest equals v7r2-launch/configs/council-pilot-v7r2-seed2903.toml on
disk and the checkpoint's own council_config_sha256, its decision count is
1,000,000 and it came from the scripted arm; the real training_command for
seed 2903 scripted initializes from it (weights only, warm-up 0, no anchor, no
level switch) and validate_council_trainer_args accepts it, while every other
scripted run of this config is refused (zero warm-up outside the
continuation). Once seed 2903's v7r1 warm start is rebound, the pool the runner
publishes (warm start + continuation checkpoint) is built in a scratch dir and
the continuation passes validate_council_continuation with the real admission.
The runner must keep the continuation start's evaluation cells in
diagnostic-evaluation/continuation-start/ (the start and this run's own 1M
milestone share the file stem policy_decisions_001000000; pilot-runtime-v3's
runner would have refused the second candidate, which is why this kit uses v4).

Run with the runtime interpreter and import path (launch.sh does this):
  cd $RT && env CLASHER_ROOT=$RT PYTHONPATH=$RT/src:$RT/scripts PYTHONDONTWRITEBYTECODE=1 \
      $RT/.venv/bin/python -B verify_v7r2c_launch.py [--protocol] [--require-rebind] [--require-admission --config CFG]

Read-only: opens the readiness ledger with mode=ro and writes nothing unless
--output is given (then it writes that one JSON file, refusing to overwrite).
Exit status 0 only if every check passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/Users/sam/Desktop/code/clasher")
RC = ROOT / "reports/strategy_council_20260928"
RUNTIME = (RC / "m0/runtime-snapshots/pilot-runtime-v4").resolve()
ADMITTED = (RC / "m0/runtime-snapshots/native-final-v7").resolve()
MANIFEST = RUNTIME / "pilot-runtime.json"
RUNTIME_MANIFEST_SHA = "0a499629ddac52803c665ef56e301228283418da75f677ebe70845d2368de1f5"
PINS = RUNTIME / "pilot-source-pins.json"
DECISION = RC / "pilot/admission-scope-decision.json"
DECISION_ID = "council-pilot-admission-scope-v1"
ATT = RC / "m0/readiness/tier-a-fresh-v7"
LEDGER = RC / "readiness-v2.sqlite"
KIT = RC / "pilot/v7r2c-launch"
V7R2 = RC / "pilot/v7r2-launch"
CONTINUATION_SEED = 2903
CONTINUATION_CHECKPOINT = V7R2 / "runs/s2903/seed-2903/scripted/policy_decisions_001000000.pt"
CONTINUATION_CHECKPOINT_SHA = "c7aae667e45073bfab442b9d36a4b2c45bca7321df442d8ebfac419e191dc522"
CONTINUATION_SOURCE_CONFIG = V7R2 / "configs/council-pilot-v7r2-seed2903.toml"
CONTINUATION_SOURCE_CONFIG_SHA = "472041eded91815c304b09eab08f9f0fb803ce1e1dd09bdeff053c1d47a79236"
SIDECAR = KIT / "orchestration-pins-pilot-runtime-v4.json"
V7R1_RUNS = RC / "pilot/v7r1-launch/runs"
BASE_CONFIG = ROOT / "configs/council-pilot-local.toml"
CONFIGS = {CONTINUATION_SEED: KIT / "configs" / f"council-pilot-v7r2c-seed{CONTINUATION_SEED}.toml"}
ADMISSION = ATT / "admission.json"
ADMISSION_SHA = "aeb4a2ff06c81f6c09e14b89c996b404479dc806ed7eca4cc90b167bbd49e757"
ATTEMPT = "m0-tier-a-fresh-v7"
GAMEDATA_SHA = "daa58b28cf4e45d753e83ca69a76794285b63704e62363ee58e617af3a30ecc3"
STRATEGY_SHA = "2be09f05cfda1a76a2536593df363afde8112377afa70bec55b9489a564da17f"
PIN_COUNT = 351
BOUND_COUNT = 342
DECL_PIN_COUNT = PIN_COUNT + 7
EXPECTED_CHANGED = [
    "src/clasher/rl/council_monitor.py",
    "src/clasher/rl/council_pilot.py",
    "src/clasher/rl/parallel_rollout.py",
    "src/clasher/rl/train_recurrent.py",
]
CHANGED_SCRIPTS = ["scripts/preflight_council_pilot.py", "scripts/run_council_pilot.py"]
RECIPE = {
    "entropy_coef": 0.0,
    "action_type_entropy_coef": 0.0,
    "location_entropy_coef": 0.0,
    "conditional_slot_entropy_coef": 0.003,
    "initial_opponent_policies": ("scripted",),
    "gae_lambda": 0.95,
    "critic_warmup_updates": 0,
    "anchor_policy_kl_coef": 0.0,
    "phase_order": ("nominal", "nominal-league"),
    "target_kl": 0.02,
    "learning_rate": 0.0001,
    "continuation_seed": CONTINUATION_SEED,
    "continuation_checkpoint_path": str(CONTINUATION_CHECKPOINT),
    "continuation_checkpoint_sha256": CONTINUATION_CHECKPOINT_SHA,
    "continuation_source_config_sha256": CONTINUATION_SOURCE_CONFIG_SHA,
    "continuation_source_decisions": 1_000_000,
}
ALLOWED_CONFIG_CHANGES = {
    "source_root",
    "gamedata_path",
    "source_pins_path",
    "nominal_admission_path",
    "output_dir",
    "num_envs",
    "actor_workers",
    "torch_threads",
    "smoke_decisions",
    "rollout_inference",
    "inference_device",
    "entropy_coef",
    "action_type_entropy_coef",
    "location_entropy_coef",
    "conditional_slot_entropy_coef",
    "initial_opponent_policies",
    "critic_warmup_updates",
    "phase_order",
    "continuation_seed",
    "continuation_checkpoint_path",
    "continuation_checkpoint_sha256",
    "continuation_source_config_sha256",
    "continuation_source_decisions",
}
# Recommended layout from pilot/throughput/README.md (user decision: all seeds on CPU).
THROUGHPUT = {
    "num_envs": 64,
    "actor_workers": 8,
    "actor_threads": 1,
    "torch_threads": 4,
    "device": "cpu",
    "rollout_inference": "worker",
    "inference_device": "cpu",
    "smoke_decisions": 98304,
    "sequence_batch_size": 2,
}
ORCHESTRATION = (
    "scripts/run_council_pilot.py",
    "scripts/run_council_warmstart.py",
    "scripts/evaluate_council_pilot.py",
    "scripts/preflight_council_pilot.py",
)

checks: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(name: str, ok: bool, detail=None) -> bool:
    checks.append({"check": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + ("" if detail is None else f"  [{detail}]"), flush=True)
    return bool(ok)


def guarded(name: str, fn):
    try:
        return fn()
    except Exception as error:  # noqa: BLE001 - reported as a failed check
        check(name, False, f"{type(error).__name__}: {error}")
        return None


def resolved(mapping: dict[str, str]) -> dict[str, str]:
    return {str(Path(k).resolve()): v for k, v in mapping.items()}


def static_checks(run_protocol: bool) -> None:
    import clasher

    check("clasher imported from pilot runtime", Path(clasher.__file__).resolve().is_relative_to(RUNTIME), clasher.__file__)

    # Runtime manifest.
    manifest = json.loads(MANIFEST.read_text())
    check("pilot-runtime.json digest", sha(MANIFEST) == RUNTIME_MANIFEST_SHA, sha(MANIFEST)[:12])
    check("runtime manifest roots (runtime, base = native-final-v7)",
          Path(manifest["snapshot_root"]).resolve() == RUNTIME and Path(manifest["base_snapshot"]).resolve() == ADMITTED)
    check("runtime manifest base snapshot.json digest", manifest["base_snapshot_manifest_sha256"] == sha(ADMITTED / "snapshot.json"))
    check("runtime manifest admission / decision / pin-file digests",
          manifest["admission_sha256"] == sha(ADMISSION) == ADMISSION_SHA
          and manifest["decision_sha256"] == sha(DECISION) and manifest["decision_id"] == DECISION_ID
          and manifest["pilot_source_pins_sha256"] == sha(PINS)
          and Path(manifest["pilot_source_pins_path"]).resolve() == PINS)
    check("runtime manifest counts 342 bound / 9 training-only / 4 changed",
          manifest["counts"] == {"ADMISSION_BOUND": BOUND_COUNT, "TRAINING_ONLY": 9, "TRAINING_ONLY_changed": 4}, manifest["counts"])

    # Declaration and ledger copy.
    declaration = json.loads((ATT / "declaration.json").read_text())
    check("declaration attempt id", declaration["attempt_id"] == ATTEMPT)
    check("declaration technical_rerun_policy = once_before_result", declaration.get("technical_rerun_policy") == "once_before_result", declaration.get("technical_rerun_policy"))
    decl_pins = resolved(declaration["source_pins"])
    admitted_src = ADMITTED / "src/clasher"
    decl_src = {Path(k).relative_to(ADMITTED).as_posix(): v for k, v in decl_pins.items() if Path(k).is_relative_to(admitted_src)}
    check(f"declaration pins = {PIN_COUNT} src/clasher + 7 readiness scripts, rooted at native-final-v7",
          len(decl_src) == PIN_COUNT and len(decl_pins) == DECL_PIN_COUNT and all(Path(k).is_relative_to(ADMITTED) for k in decl_pins),
          f"{len(decl_src)}+{len(decl_pins) - len(decl_src)}")

    def ledger_declaration():
        with sqlite3.connect(LEDGER.resolve(strict=True).as_uri() + "?mode=ro", uri=True) as db:
            db.execute("PRAGMA query_only=ON")
            row = db.execute("SELECT record FROM attempts WHERE attempt_id=?", (ATTEMPT,)).fetchone()
        return None if row is None else json.loads(row[0])

    stored = guarded("ledger declaration readable", ledger_declaration)
    if stored is not None:
        same = all(stored.get(k) == declaration.get(k) for k in ("source_pins", "input_pins", "gamedata_sha256", "workspace_gamedata_sha256", "native_attestation_sha256", "technical_rerun_policy"))
        check("ledger declaration equals declaration.json (pins, inputs, gamedata, attestation, rerun policy)", same)
    else:
        check("ledger has the v7 declaration", False, "not declared")
    from clasher.rl.readiness_capture_ownership import verify_pins

    guarded("declaration source/input pins verify on disk (native-final-v7)",
            lambda: (verify_pins(declaration["source_pins"]), verify_pins(declaration["input_pins"]),
                     check("declaration source/input pins verify on disk (native-final-v7)", True))[-1])

    # Pilot freeze.
    pins = json.loads(PINS.read_text())
    pins_r = resolved(pins)
    runtime_src = RUNTIME / "src/clasher"
    on_disk = {str(p.resolve()) for p in runtime_src.rglob("*.py")}
    check(f"pilot freeze pin count {PIN_COUNT}", len(pins) == PIN_COUNT, len(pins))
    check("pilot freeze keys == every *.py under runtime src/clasher", set(pins_r) == on_disk, sorted(on_disk ^ set(pins_r))[:5] or None)
    mismatched = [k for k, v in pins_r.items() if sha(Path(k)) != v]
    check("pilot freeze digests == runtime bytes", not mismatched, mismatched[:5] or None)
    pins_rel = {Path(k).relative_to(RUNTIME).as_posix(): v for k, v in pins_r.items()}
    check("pilot freeze digests == pilot-runtime.json files",
          {n: e["sha256"] for n, e in manifest["files"].items()} == pins_rel)
    check("pilot freeze module set == admitted src/clasher module set", set(pins_rel) == set(decl_src))

    # Whole-tree difference vs the admitted snapshot.
    base_files = json.loads((ADMITTED / "snapshot.json").read_text())["source_files"]
    differs = sorted(n for n, d in base_files.items() if not (RUNTIME / n).is_file() or sha(RUNTIME / n) != d)
    check("runtime vs native-final-v7 snapshot.json: only the 4 training-only modules + 2 orchestration scripts differ",
          differs == sorted(EXPECTED_CHANGED + CHANGED_SCRIPTS), differs)
    runtime_scripts = {p.relative_to(RUNTIME).as_posix() for p in (RUNTIME / "scripts").rglob("*.py")}
    extra = sorted(runtime_scripts - set(base_files))
    check("runtime scripts/*.py all in the admitted manifest", not extra, extra[:5] or None)
    check("runtime scripts == pilot-runtime.json scripts_and_project_files",
          all(sha(RUNTIME / n) == d for n, d in manifest["scripts_and_project_files"].items()))
    check("only run_council_pilot.py / preflight_council_pilot.py differ from the admitted scripts (recorded in the manifest)",
          manifest["scripts_unchanged_from_base"] is False
          and sorted(manifest["scripts_changed_from_base"]) == CHANGED_SCRIPTS
          and all(e["base_sha256"] == base_files[n] and e["sha256"] == sha(RUNTIME / n)
                  for n, e in manifest["scripts_changed_from_base"].items()))
    check("changed orchestration scripts are outside the admission pins",
          not [n for n in CHANGED_SCRIPTS if str((ADMITTED / n).resolve()) in decl_pins])
    check("runtime input files (gamedata, roles, decks) == pilot-runtime.json",
          all(sha(RUNTIME / n) == d for n, d in manifest["input_files"].items()))
    check("runtime gamedata == declaration workspace/gamedata digest",
          sha(RUNTIME / "gamedata.json") == sha(ADMITTED / "gamedata.json") == declaration["workspace_gamedata_sha256"] == declaration["gamedata_sha256"] == GAMEDATA_SHA)

    # Scope decision consistency with the code enforcing it.
    from clasher.rl import council_pilot as cp

    decision = json.loads(DECISION.read_text())
    check("decision training_only == PILOT_TRAINING_ONLY_MODULES (runtime code)",
          decision["decision_id"] == cp.PILOT_SCOPE_DECISION_ID == DECISION_ID
          and tuple(decision["training_only"]) == cp.PILOT_TRAINING_ONLY_MODULES)
    check("decision bound_symbol_roots == PILOT_BOUND_SYMBOLS (runtime code)",
          {k: sorted(v) for k, v in decision["bound_symbol_roots"].items()} == {k: sorted(v) for k, v in cp.PILOT_BOUND_SYMBOLS.items()})
    check("decision names the v7 admission", decision["admission"]["sha256"] == ADMISSION_SHA
          and Path(decision["admission"]["source_root"]).resolve() == ADMITTED)

    # The real scope verifier, against the declaration pins (== admission pins, checked below).
    def scope():
        report = cp.verify_pilot_source_scope(
            pilot_root=RUNTIME, admitted_root=ADMITTED,
            admitted_pins=dict(declaration["source_pins"]), pilot_pins=pins_r)
        ok = (len(report["admission_bound"]) == BOUND_COUNT and len(report["training_only"]) == 9
              and report["training_only_changed"] == EXPECTED_CHANGED
              and all(pins_rel[n] == d == decl_src[n] for n, d in report["admission_bound"].items())
              and set(report["bound_symbols_checked"]) == set(EXPECTED_CHANGED))
        return check("verify_pilot_source_scope(runtime, native-final-v7) passes: 342 bound, 9 training-only, 4 changed", ok,
                     {n: len(v) for n, v in report["bound_symbols_checked"].items()})

    guarded("verify_pilot_source_scope(runtime, native-final-v7) passes: 342 bound, 9 training-only, 4 changed", scope)

    def negative_control():
        tampered = dict(pins_r)
        key = str((RUNTIME / "src/clasher/battle.py").resolve())
        tampered[key] = "0" * 64
        try:
            cp.verify_pilot_source_scope(pilot_root=RUNTIME, admitted_root=ADMITTED,
                                         admitted_pins=dict(declaration["source_pins"]), pilot_pins=tampered)
        except ValueError as error:
            return check("negative control: verify_pilot_source_scope refuses a changed admission-bound pin (battle.py)", True, str(error)[:80])
        return check("negative control: verify_pilot_source_scope refuses a changed admission-bound pin (battle.py)", False, "accepted")

    guarded("negative control: verify_pilot_source_scope refuses a changed admission-bound pin (battle.py)", negative_control)

    # Sidecar.
    side = json.loads(SIDECAR.read_text())
    check("sidecar read-only", not (SIDECAR.stat().st_mode & 0o222))
    check("sidecar runtime manifest digest", side["runtime_manifest_sha256"] == sha(MANIFEST) and Path(side["runtime_root"]).resolve() == RUNTIME)
    check("sidecar admitted root + snapshot.json digest", Path(side["admitted_root"]).resolve() == ADMITTED and side["admitted_manifest_sha256"] == sha(ADMITTED / "snapshot.json"))
    check("sidecar declaration / freeze-receipt digests", side["declaration_sha256"] == sha(ATT / "declaration.json") and side["freeze_receipt_sha256"] == sha(ATT / "freeze-receipt.json"))
    check("sidecar decision / admission digests", side["decision_sha256"] == sha(DECISION) and side["admission_sha256"] == (sha(ADMISSION) if ADMISSION.is_file() else None))
    check("sidecar pin-file digest", Path(side["source_pins_path"]).resolve() == PINS and side["source_pins_sha256"] == sha(PINS) and side["source_pins_count"] == PIN_COUNT)
    check("sidecar technical_rerun_policy", side.get("technical_rerun_policy") == declaration.get("technical_rerun_policy"))
    check("sidecar training-only delta == pilot-runtime.json",
          sorted(side["training_only_changed_vs_admission"]) == EXPECTED_CHANGED
          and all(v == {"admission_sha256": manifest["files"][n]["admission_sha256"], "pilot_runtime_sha256": manifest["files"][n]["sha256"]}
                  for n, v in side["training_only_changed_vs_admission"].items()))
    check("sidecar covers the four orchestration scripts", set(side["scripts"]) == set(ORCHESTRATION))
    for name, entry in side["scripts"].items():
        path = Path(entry["path"])
        if name in CHANGED_SCRIPTS:
            check(f"sidecar {name} == runtime disk == pilot-runtime.json (changed from admitted snapshot, base digest recorded)",
                  path.resolve() == (RUNTIME / name).resolve() and sha(path) == entry["sha256"] == manifest["scripts_and_project_files"][name]
                  and entry.get("changed_from_base") is True and entry.get("admitted_snapshot_sha256") == base_files[name] != entry["sha256"])
        else:
            check(f"sidecar {name} == runtime disk == admitted snapshot.json",
                  path.resolve() == (RUNTIME / name).resolve() and sha(path) == entry["sha256"] == base_files[name] == manifest["scripts_and_project_files"][name])
    for name, entry in side["verification_tools"].items():
        path = Path(entry["path"])
        check(f"sidecar tool {name} == admitted disk == snapshot.json (runs from native-final-v7)",
              path.resolve() == (ADMITTED / name).resolve() and sha(path) == entry["sha256"] == base_files[name] == sha(RUNTIME / name))
    unadmitted = [n for n in ORCHESTRATION if str((ADMITTED / n).resolve()) in decl_pins]
    check("orchestration scripts are outside the admitted pins (why the sidecar exists)", not unadmitted, unadmitted or None)

    def receipt_format():
        from clasher.rl.readiness_capture_ownership import AdmissionReceipt

        h = "0" * 64
        base = AdmissionReceipt(
            attempt_id=ATTEMPT, ledger_path=str(LEDGER), source_root=str(ADMITTED), design_sha256=h,
            root_seal_sha256=h, protocol_sha256=h, report_path="/r.json", report_sha256=h,
            calibration_receipt_path="/c.json", calibration_receipt_sha256=h,
            source_pins=declaration["source_pins"], input_pins=declaration["input_pins"],
            gamedata_sha256=declaration["gamedata_sha256"], catalog_sha256=declaration["catalog_sha256"],
            workspace_gamedata_sha256=declaration["workspace_gamedata_sha256"])
        raw = json.loads(base.model_dump_json())
        empty = AdmissionReceipt.model_validate_json(json.dumps({**raw, "technical_reruns": []}))
        return "technical_reruns" not in raw and empty == base

    ok = guarded("runtime AdmissionReceipt accepts technical_reruns []", receipt_format)
    if ok is not None:
        check("runtime AdmissionReceipt accepts technical_reruns []", ok)

    # Configs.
    from clasher.rl.council_pilot import load_pilot_config, load_source_pins

    base = tomllib.loads(BASE_CONFIG.read_text())
    outputs = set()
    for seed, path in CONFIGS.items():
        raw = tomllib.loads(path.read_text())
        changed = {k for k in set(base) | set(raw) if base.get(k) != raw.get(k)}
        check(f"seed {seed}: fields changed vs base == allowed set", changed == ALLOWED_CONFIG_CHANGES, sorted(changed ^ ALLOWED_CONFIG_CHANGES) or None)
        config = guarded(f"seed {seed}: load_pilot_config", lambda path=path: load_pilot_config(path))
        if config is None:
            continue
        check(f"seed {seed}: source_root = pilot runtime", Path(config.source_root).resolve() == RUNTIME)
        check(f"seed {seed}: gamedata_path = runtime gamedata.json", Path(config.gamedata_path).resolve() == RUNTIME / "gamedata.json")
        check(f"seed {seed}: source_pins_path = runtime pilot-source-pins.json", Path(config.source_pins_path).resolve() == PINS)
        check(f"seed {seed}: nominal_admission_path = v7 admission.json", Path(config.nominal_admission_path) == ADMISSION)
        layout = {k: getattr(config, k) for k in THROUGHPUT}
        check(f"seed {seed}: throughput layout 64 envs / 8 workers / 4 threads / worker inference / cpu / smoke 98304", layout == THROUGHPUT, layout)
        check(f"seed {seed}: milestones divisible by num_envs",
              all(v % config.num_envs == 0 for v in (config.smoke_decisions, config.diagnostic_decisions, config.decisions_per_seed, 1_000_000)))
        check(f"seed {seed}: output_dir inside this kit", Path(config.output_dir) == KIT / f"runs/s{seed}")
        recipe_checks(seed, path, config)
        check(f"seed {seed}: config file read-only", not (path.stat().st_mode & 0o222))
        outputs.add(config.output_dir)
        pilot_pins = guarded(f"seed {seed}: load_source_pins (digests re-hashed)", lambda config=config: load_source_pins(config))
        if pilot_pins is not None:
            check(f"seed {seed}: load_source_pins == pilot freeze", pilot_pins == pins_r)
        if run_protocol:
            from clasher.rl.council_evaluation import build_protocol, load_protocol

            same = guarded(f"seed {seed}: evaluation protocol", lambda config=config: load_protocol(Path(config.evaluation_protocol_path)) == build_protocol(config))
            if same is not None:
                check(f"seed {seed}: frozen evaluation protocol == build_protocol(config)", same, sha(Path(config.evaluation_protocol_path))[:12])
    check("one output dir (continuation seed only)", len(outputs) == 1)
    check("info: output dir existence (preflight fails if it creates a missing real output dir)", True, {o: Path(o).exists() for o in sorted(outputs)})


def _argv_values(command: list[str]) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for i, token in enumerate(command):
        if token.startswith("--"):
            nxt = command[i + 1] if i + 1 < len(command) and not command[i + 1].startswith("--") else None
            values.setdefault(token, []).append(nxt)
    return values


def recipe_checks(seed: int, path: Path, config) -> None:
    import copy
    import sys as _sys

    from clasher.rl.council_pilot import (
        anchor_checkpoint_path, anchor_policy_kl_coef_for_arm, build_council_model_config,
        critic_warmup_updates_for_arm, entropy_recipe, is_continuation, level_randomization_after,
        opponent_initialization_paths_for_seed, training_command, training_recipe,
        validate_council_trainer_args)
    from clasher.rl.structured_obs import StructuredObservationBuilder
    from clasher.rl.train_recurrent import entropy_recipe_record, parse_args

    values = {k: getattr(config, k) for k in RECIPE}
    check(f"seed {seed}: recipe fields (v7r2 recipe, warm-up 0, no anchor, nominal-league, continuation declared)",
          values == RECIPE, values)
    check(f"seed {seed}: entropy recipe factorized-v2", entropy_recipe(config) == "factorized-v2")
    recipe = training_recipe(config)
    check(f"seed {seed}: training_recipe record (continuation, no level switch)",
          recipe["gae_lambda"] == 0.95 and recipe["critic_warmup_updates"] == 0 and recipe["anchor_policy_kl_coef"] == 0.0
          and recipe["level_randomization_after"] is None and level_randomization_after(config) is None
          and recipe["continuation"] == {"seed": seed, "checkpoint": str(CONTINUATION_CHECKPOINT),
                                         "checkpoint_sha256": CONTINUATION_CHECKPOINT_SHA,
                                         "source_config_sha256": CONTINUATION_SOURCE_CONFIG_SHA,
                                         "source_decisions": 1_000_000}, recipe)
    check(f"seed {seed}: only ({seed}, scripted) is the continuation; no anchor on any arm",
          [(s, a) for s in config.seeds for a in config.arms if is_continuation(config, s, a)] == [(seed, "scripted")]
          and all(anchor_checkpoint_path(config, s, a) is None and anchor_policy_kl_coef_for_arm(config, a) == 0.0
                  for s in config.seeds for a in config.arms)
          and critic_warmup_updates_for_arm(config, "scripted") == 0)

    # Continuation declaration vs disk.
    stopped = json.loads((V7R2 / "stopped-for-recipe-fix.json").read_text())
    check("continuation checkpoint digest == declaration == v7r2 stopped record",
          CONTINUATION_CHECKPOINT.is_file() and sha(CONTINUATION_CHECKPOINT) == CONTINUATION_CHECKPOINT_SHA
          == stopped["checkpoints_1M_sha256"]["s2903"], sha(CONTINUATION_CHECKPOINT)[:12])
    check("continuation source config digest == v7r2 seed-2903 config on disk",
          sha(CONTINUATION_SOURCE_CONFIG) == CONTINUATION_SOURCE_CONFIG_SHA)
    import torch

    payload = torch.load(CONTINUATION_CHECKPOINT, map_location="cpu", weights_only=False)
    check("continuation checkpoint metadata (v7r2 config digest, 1,000,000 decisions, scripted arm, v7 admission, gamedata)",
          payload.get("council_config_sha256") == CONTINUATION_SOURCE_CONFIG_SHA
          and int(payload.get("total_transitions", -1)) == 1_000_000
          and (payload.get("council_recipe") or {}).get("arm") == "scripted"
          and payload.get("admission_sha256") == ADMISSION_SHA and payload.get("gamedata_sha256") == GAMEDATA_SHA,
          {k: payload.get(k) for k in ("total_transitions", "council_recipe", "update")})
    check("continuation checkpoint is read-only to this kit (outside the v7r2c output dir)",
          not CONTINUATION_CHECKPOINT.resolve().is_relative_to(Path(config.output_dir).resolve()))

    # Evaluation outputs are named by checkpoint stem; the continuation checkpoint and
    # this run's own 1M milestone share one (pilot-runtime-v3's runner would have
    # refused the second candidate). The v4 runner keeps the start in its own directory.
    from clasher.rl.council_pilot import evaluation_commands

    arm_dir = Path(config.output_dir) / f"seed-{seed}" / "scripted"
    eval_dir = arm_dir / "diagnostic-evaluation"

    def eval_outputs(checkpoint, output):
        return {c[c.index("--json-out") + 1] for c in evaluation_commands(config, checkpoint=checkpoint, output=output, final=False)}

    runner_source = (RUNTIME / "scripts/run_council_pilot.py").read_text()
    milestone = arm_dir / "policy_decisions_001000000.pt"
    check("runner keeps the continuation start's evaluation cells apart from the new 1M milestone's (same file stem)",
          CONTINUATION_CHECKPOINT.stem == milestone.stem
          and eval_outputs(CONTINUATION_CHECKPOINT, eval_dir) == eval_outputs(milestone, eval_dir)
          and not eval_outputs(CONTINUATION_CHECKPOINT, eval_dir / "continuation-start") & eval_outputs(milestone, eval_dir)
          and 'candidate_dir = eval_dir / "continuation-start"' in runner_source
          and "output=candidate_dir" in runner_source and "output=eval_dir" not in runner_source)

    builder = StructuredObservationBuilder(
        decks_path=config.training_decks_path, max_entities=128, card_semantics_version=4,
        public_history_slots=4, public_seen_card_slots=8, public_entity_levels=True,
        public_hand_levels=True, canonical_lane_globals=True)
    model_config = build_council_model_config(builder)
    init_dir = Path(config.output_dir) / f"seed-{seed}" / "initialization"
    for phase, total in (("nominal", "1000000"), ("nominal-league", "5000000")):
        resume = None if phase == "nominal" else Path(config.output_dir) / f"seed-{seed}" / "scripted" / "policy_v2_update_000123.pt"
        command = training_command(config, config_path=path, admission=ADMISSION, seed=seed, arm="scripted", phase=phase,
                                   pool_path=Path(config.output_dir) / f"seed-{seed}" / "scripted" / "opponents" / "pool.json",
                                   initialization=CONTINUATION_CHECKPOINT, resume=resume)
        v = _argv_values(command)
        one = lambda flag, v=v: (v.get(flag) or [None])[0]  # noqa: E731
        entropy = {f: one(f) for f in ("--entropy-coef", "--conditional-slot-entropy-coef",
                                       "--action-type-entropy-coef", "--location-entropy-coef")}
        ok = (one("--gae-lambda") == "0.95" and one("--target-kl") == "0.02" and one("--learning-rate") == "0.0001"
              and one("--total-decisions") == total and one("--num-envs") == "64" and one("--actor-workers") == "8"
              and one("--torch-threads") == "4" and one("--critic-warmup-updates") == "0"
              and "--level-randomization-after" not in v and "--anchor-checkpoint" not in v and "--anchor-policy-kl-coef" not in v
              and entropy == {"--entropy-coef": "0.0", "--conditional-slot-entropy-coef": "0.003",
                              "--action-type-entropy-coef": "0.0", "--location-entropy-coef": "0.0"}
              and set(v.get("--checkpoint-decisions", [])) == {"1000000", "2000000", "3000000", "4000000", "5000000"}
              and (one("--initialize-policy-from") == str(CONTINUATION_CHECKPOINT) and "--resume-from" not in v
                   if resume is None else one("--resume-from") == str(resume) and "--initialize-policy-from" not in v))
        check(f"seed {seed}/scripted/{phase}: trainer argv (continuation init, gae 0.95, warm-up 0, no anchor, milestones)",
              ok, None if ok else v)
        saved = _sys.argv
        try:
            _sys.argv = ["trainer", *command[4:]]
            args = parse_args()
        finally:
            _sys.argv = saved
        guarded(f"seed {seed}/scripted/{phase}: validate_council_trainer_args accepts the argv",
                lambda args=args, phase=phase: (validate_council_trainer_args(config, args, model_config, builder),
                                                check(f"seed {seed}/scripted/{phase}: validate_council_trainer_args accepts the argv", True))[-1])
        if phase == "nominal":
            record = entropy_recipe_record(args)
            check(f"seed {seed}: ppo_update joint entropy term disabled (type 0, location 0, card|play 0.003)",
                  record["joint_entropy_term_applies"] is False and record["effective_type_coef"] == 0.0
                  and record["effective_location_coef"] == 0.0 and record["conditional_slot_entropy_coef"] == 0.003, record)
            trial = copy.copy(args)
            trial.initialize_policy_from = str(init_dir / "scripted.pt")
            refused = []
            try:
                validate_council_trainer_args(config, trial, model_config, builder)
            except ValueError:
                refused.append("warm-start initializer")
            for other in [s for s in config.seeds if s != seed]:
                cmd = training_command(config, config_path=path, admission=ADMISSION, seed=other, arm="scripted",
                                       phase="nominal", pool_path=Path("/tmp/pool.json"), initialization=Path("/tmp/init.pt"))
                saved = _sys.argv
                try:
                    _sys.argv = ["trainer", *cmd[4:]]
                    other_args = parse_args()
                finally:
                    _sys.argv = saved
                try:
                    validate_council_trainer_args(config, other_args, model_config, builder)
                except ValueError:
                    refused.append(f"seed {other} scripted (zero warm-up)")
            check(f"seed {seed}: negative controls: trainer refuses another initializer and the other seeds' scripted runs",
                  len(refused) == 1 + len(config.seeds) - 1, refused)
    a, b = Path("/x/scripted.pt"), Path("/x/scripted-random-control.pt")
    check(f"seed {seed}: continuation pool = warm start + declared checkpoint",
          opponent_initialization_paths_for_seed(config, seed=seed, arm="scripted", scripted=a, scratch=b)
          == (a, CONTINUATION_CHECKPOINT))


def warmstart_checks(require_rebind: bool, launch_config: Path | None = None) -> None:
    """Seed 2903's v7r1 warm start is intact; once rebound, the continuation
    passes validate_council_continuation against the pool the runner publishes."""
    import tempfile
    import types

    import torch

    from clasher.rl.council_pilot import (
        load_pilot_config, opponent_initialization_paths_for_seed, publish_initial_pool,
        state_dict_sha256, validate_council_continuation, validate_council_initial_policy)
    from clasher.rl.structured_obs import StructuredObservationBuilder

    for seed, path in CONFIGS.items():
        source = V7R1_RUNS / f"s{seed}" / f"seed-{seed}" / "initialization"
        receipt = json.loads((source / "scripted-demonstrations" / "result.json").read_text())
        check(f"seed {seed}: v7r1 warm start intact (scripted.pt, control == their receipt)",
              sha(Path(receipt["checkpoint"])) == receipt["checkpoint_sha256"]
              and sha(Path(receipt["control_checkpoint"])) == receipt["control_checkpoint_sha256"]
              and Path(receipt["checkpoint"]).parent == source, receipt["checkpoint_sha256"][:12])
        config = load_pilot_config(path)
        target = Path(config.output_dir) / f"seed-{seed}" / "initialization"
        rebind = target / "scripted-demonstrations" / "result.json"
        if not rebind.exists():
            check(f"seed {seed}: warm start rebound into v7r2c (rebind_warmstarts.py)", not (require_rebind and (launch_config is None or launch_config.resolve() == path.resolve())), "pending")
            continue
        sys.path.insert(0, str(KIT))
        from rebind_warmstarts import verify_rebind

        report = verify_rebind(config, path, seed, source)
        failed = [n for n, ok in report["checks"].items() if not ok]
        check(f"seed {seed}: rebind hash chain v7r1 receipt -> v7r1 files -> rebind receipt -> v7r2c files, identical weights",
              not failed, failed or report["state_sha256"])
        builder = StructuredObservationBuilder(
            decks_path=config.training_decks_path, max_entities=128, card_semantics_version=4,
            public_history_slots=4, public_seen_card_slots=8, public_entity_levels=True,
            public_hand_levels=True, canonical_lane_globals=True)
        scripted, scratch = target / "scripted.pt", target / "scripted-random-control.pt"

        def run():
            with tempfile.TemporaryDirectory() as tmp:
                pool = Path(tmp) / "pool.json"
                publish_initial_pool(config, pool_path=pool, initialization_paths=opponent_initialization_paths_for_seed(
                    config, seed=seed, arm="scripted", scripted=scripted, scratch=scratch))
                entries = [e["sha256"] for e in json.loads(pool.read_text())["initial"]]
                args = types.SimpleNamespace(seed=seed, council_admission=ADMISSION, council_arm="scripted",
                                             council_opponent_pool=pool, preflight_no_update=False)
                payload = torch.load(CONTINUATION_CHECKPOINT, map_location="cpu", weights_only=False)
                record = validate_council_continuation(config, payload, initialization_path=CONTINUATION_CHECKPOINT,
                                                       args=args, builder=builder)
                warm = torch.load(scripted, map_location="cpu", weights_only=False)
                warm_record = validate_council_initial_policy(config, warm, initialization_path=scripted,
                                                              args=args, builder=builder)
            return check(f"seed {seed}/scripted: continuation passes validate_council_continuation (real admission; pool = warm start + continuation)",
                         record["sha256"] == CONTINUATION_CHECKPOINT_SHA and record["weights_only"] and record["optimizer_reset"]
                         and record["state_sha256"] == state_dict_sha256(payload["model_state_dict"])
                         and entries == [sha(scripted), CONTINUATION_CHECKPOINT_SHA]
                         and warm_record["state_sha256"] == report["state_sha256"]["scripted.pt"],
                         {"continuation_state": record["state_sha256"][:12], "pool_initial": len(entries)})

        guarded(f"seed {seed}/scripted: continuation passes validate_council_continuation", run)


def admission_checks(config_path: Path | None) -> None:
    if not check("admission.json exists", ADMISSION.is_file(), str(ADMISSION)):
        return
    declaration = json.loads((ATT / "declaration.json").read_text())
    receipt = json.loads(ADMISSION.read_text())
    check("admission digest", sha(ADMISSION) == ADMISSION_SHA, sha(ADMISSION)[:12])
    check("admission attempt id", receipt.get("attempt_id") == ATTEMPT, receipt.get("attempt_id"))
    check("admission source_root = native-final-v7 (admitted root, not the pilot runtime)", Path(receipt.get("source_root", "/")).resolve() == ADMITTED, receipt.get("source_root"))
    check(f"admission source_pins == declaration ({DECL_PIN_COUNT})", receipt.get("source_pins") == declaration["source_pins"] and len(receipt["source_pins"]) == DECL_PIN_COUNT)
    check("admission input_pins == declaration", receipt.get("input_pins") == declaration["input_pins"])
    check("admission gamedata", receipt.get("gamedata_sha256") == GAMEDATA_SHA)
    check("admission strategy", receipt.get("strategy_sha256") == STRATEGY_SHA)
    check("admission levels [11], nominal scope", receipt.get("levels") == [11] and receipt.get("level_sampling_scope") == "nominal")
    check("admission training scope", receipt.get("training_scope") == "scalar_public_policy_only")
    check("admission ledger path", Path(receipt.get("ledger_path", "/")).resolve() == LEDGER.resolve())
    reruns = receipt.get("technical_reruns", [])
    check("info: admission technical_reruns (ledger equality is enforced by require_admission)", isinstance(reruns, list),
          {"count": len(reruns), "completed": sum(bool(r.get("completed")) for r in reruns if isinstance(r, dict))})
    report = Path(receipt.get("report_path", "/nonexistent"))
    check("admission report passed and digest matches", report.is_file() and sha(report) == receipt.get("report_sha256") and json.loads(report.read_text()).get("status") == "passed")
    if config_path is not None:
        from clasher.rl.council_pilot import load_pilot_config, require_pilot_admission

        def full():
            config = load_pilot_config(config_path)
            r = require_pilot_admission(config, Path(config.nominal_admission_path), levels=(11,))
            return check(f"require_pilot_admission (scope verifier + admitted-runtime ledger check) for {config_path.name}",
                         r.attempt_id == ATTEMPT and Path(r.source_root).resolve() == ADMITTED, r.attempt_id)

        guarded(f"require_pilot_admission (scope verifier + admitted-runtime ledger check) for {config_path.name}", full)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", action="store_true", help="also rebuild the evaluation protocol per config")
    parser.add_argument("--require-admission", action="store_true")
    parser.add_argument("--require-rebind", action="store_true", help="fail unless the warm start is rebound (only the --config seed when --config is given; every seed otherwise)")
    parser.add_argument("--config", type=Path, help="config for the full require_pilot_admission check")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    static_checks(args.protocol)
    warmstart_checks(args.require_rebind, args.config)
    if args.require_admission:
        admission_checks(args.config)
    ok = all(c["ok"] for c in checks)
    summary = {
        "schema": "council-pilot-v7r2c-launch-verification-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if ok else "failed",
        "admission_required": args.require_admission,
        "admission_present": ADMISSION.is_file(),
        "admission_sha256": sha(ADMISSION) if ADMISSION.is_file() else None,
        "runtime_manifest_sha256": sha(MANIFEST),
        "source_pins_sha256": sha(PINS),
        "sidecar_sha256": sha(SIDECAR),
        "config_sha256": {str(p): sha(p) for p in CONFIGS.values()},
        "checks": checks,
    }
    if args.output is not None:
        with args.output.open("x") as stream:
            json.dump(summary, stream, indent=2)
            stream.write("\n")
    print(f"verification {summary['status']}: {sum(c['ok'] for c in checks)}/{len(checks)} checks passed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
