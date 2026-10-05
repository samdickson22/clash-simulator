#!/usr/bin/env python3
"""Verify the v6 pilot pin file, sidecar and configs against the snapshot,
the m0-tier-a-fresh-v6 declaration and (optionally) the admission receipt.

Run with the snapshot interpreter and import path (launch.sh does this):
  cd $SNAP && env CLASHER_ROOT=$SNAP PYTHONPATH=$SNAP/src PYTHONDONTWRITEBYTECODE=1 \
      $SNAP/.venv/bin/python -B verify_v6_launch.py [--protocol] [--require-admission --config CFG]

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
SNAP = (RC / "m0/runtime-snapshots/native-final-v6").resolve()
PREV_SNAP = RC / "m0/runtime-snapshots/native-final-v5"
EXPECTED_ADDED = [
    "scripts/build_level_extension_evidence.py",
    "scripts/collect_level_extension_probes.py",
    "scripts/collect_tier_b_prefix.py",
    "scripts/level_extension_common.py",
    "scripts/rehearse_level_extension_offline.py",
    "scripts/run_level_extension_scalar_study.py",
    "scripts/tier_b_readiness.py",
    "src/clasher/rl/readiness_tier_b.py",
    "src/clasher/rl/readiness_tier_b_ledger.py",
    "src/clasher/rl/readiness_tier_b_policy.py",
    "src/clasher/rl/readiness_tier_b_probes.py",
]
EXPECTED_CHANGED = [
    "scripts/read_native_public_levels.py",
    "scripts/readiness_admission.py",
    "scripts/run_readiness_v2.py",
    "src/clasher/rl/native_probe_transport.py",
    "src/clasher/rl/readiness_capture_ownership.py",
    "src/clasher/rl/readiness_execution.py",
    "src/clasher/rl/readiness_job_selection.py",
    "src/clasher/rl/readiness_prefix.py",
    "src/clasher/rl/training_readiness_v2.py",
]
EXPECTED_DELTA = sorted(EXPECTED_ADDED + EXPECTED_CHANGED)
TIER_B_SRC = [n for n in EXPECTED_ADDED if n.startswith("src/")]
PIN_COUNT = 351  # 347 v5 modules + the 4 new readiness_tier_b*.py
DECL_PIN_COUNT = PIN_COUNT + 7
ATT = RC / "m0/readiness/tier-a-fresh-v6"
LEDGER = RC / "readiness-v2.sqlite"
V6 = RC / "pilot/v6-launch"
PINS = V6 / "source-pins-native-final-v6.json"
SIDECAR = V6 / "orchestration-pins-native-final-v6.json"
BASE_CONFIG = ROOT / "configs/council-pilot-local.toml"
CONFIGS = {s: V6 / "configs" / f"council-pilot-v6-seed{s}.toml" for s in (2901, 2902, 2903)}
ADMISSION = ATT / "admission.json"
ATTEMPT = "m0-tier-a-fresh-v6"
GAMEDATA_SHA = "daa58b28cf4e45d753e83ca69a76794285b63704e62363ee58e617af3a30ecc3"
STRATEGY_SHA = "2be09f05cfda1a76a2536593df363afde8112377afa70bec55b9489a564da17f"
ALLOWED_CONFIG_CHANGES = {
    "source_root",
    "gamedata_path",
    "source_pins_path",
    "nominal_admission_path",
    "output_dir",
    "num_envs",
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

    check("clasher imported from snapshot", Path(clasher.__file__).resolve().is_relative_to(SNAP), clasher.__file__)
    declaration = json.loads((ATT / "declaration.json").read_text())
    check("declaration attempt id", declaration["attempt_id"] == ATTEMPT)
    check("declaration technical_rerun_policy = once_before_result", declaration.get("technical_rerun_policy") == "once_before_result", declaration.get("technical_rerun_policy"))
    decl_pins = resolved(declaration["source_pins"])
    src = SNAP / "src/clasher"
    decl_src = {k: v for k, v in decl_pins.items() if Path(k).is_relative_to(src)}
    decl_other = sorted(k for k in decl_pins if not Path(k).is_relative_to(src))
    check(f"declaration pins = {PIN_COUNT} src/clasher + 7 readiness scripts", len(decl_src) == PIN_COUNT and len(decl_other) == 7, f"{len(decl_src)}+{len(decl_other)}")

    # Ledger copy of the declaration (read-only) must equal declaration.json.
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
        check("ledger has the v6 declaration", False, "not declared")

    # Pin file.
    pins = json.loads(PINS.read_text())
    pins_r = resolved(pins)
    on_disk = {str(p.resolve()) for p in src.rglob("*.py")}
    check(f"pin file count {PIN_COUNT}", len(pins) == PIN_COUNT, len(pins))
    check("pin file == admitted src/clasher subset of declaration", pins_r == decl_src)
    check("pin file keys == every *.py under snapshot src/clasher", set(pins_r) == on_disk, f"extra_on_disk={sorted(on_disk - set(pins_r))[:5]}")
    mismatched = [k for k, v in pins_r.items() if sha(Path(k)) != v]
    check("pin file digests == snapshot bytes", not mismatched, mismatched[:5] or None)
    manifest = json.loads((SNAP / "snapshot.json").read_text())
    files = manifest["source_files"]
    manifest_bad = [k for k, v in pins_r.items() if files.get(str(Path(k).relative_to(SNAP))) != v]
    check("pin file digests == snapshot.json source_files", not manifest_bad, manifest_bad[:5] or None)
    tier_b = sorted(str(Path(k).relative_to(SNAP)) for k in pins_r if Path(k).name.startswith("readiness_tier_b"))
    check("new v6 readiness_tier_b*.py modules are pinned (pin file and declaration)", tier_b == TIER_B_SRC
          and all(str((SNAP / n).resolve()) in decl_src for n in TIER_B_SRC), tier_b)

    # What _verify_declaration checks inside require_admission.
    from clasher.rl.readiness_capture_ownership import required_source_pins, verify_pins

    required = required_source_pins()
    check("snapshot required_source_pins() all declared with same digest", all(decl_pins.get(k) == v for k, v in resolved(required).items()), len(required))
    check("required_source_pins() src/clasher subset == pin file (incl. readiness_tier_b*)",
          {k: v for k, v in resolved(required).items() if Path(k).is_relative_to(src)} == pins_r and len(required) == DECL_PIN_COUNT, len(required))
    guarded("declaration source/input pins verify on disk", lambda: (verify_pins(declaration["source_pins"]), verify_pins(declaration["input_pins"]), check("declaration source/input pins verify on disk", True))[-1])
    check("snapshot gamedata == declaration workspace/gamedata digest", sha(SNAP / "gamedata.json") == declaration["workspace_gamedata_sha256"] == declaration["gamedata_sha256"] == GAMEDATA_SHA)

    # Sidecar.
    side = json.loads(SIDECAR.read_text())
    check("sidecar snapshot.json digest", side["snapshot_manifest_sha256"] == sha(SNAP / "snapshot.json"))
    check("sidecar declaration digest", side["declaration_sha256"] == sha(ATT / "declaration.json"))
    check("sidecar freeze-receipt digest", side["freeze_receipt_sha256"] == sha(ATT / "freeze-receipt.json"))
    check("sidecar pin-file digest", side["source_pins_sha256"] == sha(PINS) and side["source_pins_count"] == PIN_COUNT)
    for group in ("scripts", "verification_tools"):
        for name, entry in side[group].items():
            path = Path(entry["path"])
            check(f"sidecar {name} == disk == snapshot.json", path.resolve() == (SNAP / name).resolve() and sha(path) == entry["sha256"] == files[name])
    check("sidecar covers the four orchestration scripts", set(side["scripts"]) == set(ORCHESTRATION))
    previous = json.loads((PREV_SNAP / "snapshot.json").read_text())["source_files"]
    delta = sorted(n for n in files if previous.get(n) != files[n]) + sorted(set(previous) - set(files))
    check("source difference vs native-final-v5 == 11 added + 9 changed readiness/transport files", delta == EXPECTED_DELTA and not set(previous) - set(files), delta if delta != EXPECTED_DELTA else len(delta))
    check("sidecar records the v5 -> v6 delta", sorted(side.get("source_delta_vs_native_final_v5", {})) == EXPECTED_DELTA
          and all(side["source_delta_vs_native_final_v5"][n] == {"native_final_v5_sha256": previous.get(n), "native_final_v6_sha256": files[n]} for n in EXPECTED_DELTA))
    check("pilot-path modules unchanged vs native-final-v5 (orchestration, council_*, entities, train_recurrent)",
          all(previous[n] == files[n] for n in (*ORCHESTRATION, "src/clasher/rl/council_pilot.py", "src/clasher/rl/council_warmstart.py", "src/clasher/entities.py", "src/clasher/rl/train_recurrent.py")))
    check("sidecar technical_rerun_policy", side.get("technical_rerun_policy") == declaration.get("technical_rerun_policy"))

    # Receipt-format compatibility: the snapshot AdmissionReceipt (strict, extra=forbid)
    # must accept a receipt carrying technical_reruns, empty or not, and treat an
    # explicit [] as equal to the ledger record (which omits the empty field).
    def receipt_format():
        from clasher.rl.readiness_capture_ownership import AdmissionReceipt

        h = "0" * 64
        base = AdmissionReceipt(
            attempt_id=ATTEMPT, ledger_path=str(LEDGER), source_root=str(SNAP), design_sha256=h,
            root_seal_sha256=h, protocol_sha256=h, report_path="/r.json", report_sha256=h,
            calibration_receipt_path="/c.json", calibration_receipt_sha256=h,
            source_pins=declaration["source_pins"], input_pins=declaration["input_pins"],
            gamedata_sha256=declaration["gamedata_sha256"], catalog_sha256=declaration["catalog_sha256"],
            workspace_gamedata_sha256=declaration["workspace_gamedata_sha256"])
        raw = json.loads(base.model_dump_json())
        entry = {"family_id": "f", "condition": "c", "candidate_role": "wait", "engine": "reference",
                 "original_nonce": "a", "rerun_nonce": "b", "original_output_path": "/a", "rerun_output_path": "/b",
                 "reason": "runner_killed_without_outcome", "failure_type": None, "evidence_sha256": h, "completed": True}
        empty = AdmissionReceipt.model_validate_json(json.dumps({**raw, "technical_reruns": []}))
        one = AdmissionReceipt.model_validate_json(json.dumps({**raw, "technical_reruns": [entry]}))
        return ("technical_reruns" not in raw and empty == base and len(one.technical_reruns) == 1
                and AdmissionReceipt.model_validate_json(one.model_dump_json()) == one)

    ok = guarded("snapshot AdmissionReceipt accepts technical_reruns ([] and 1 record)", receipt_format)
    if ok is not None:
        check("snapshot AdmissionReceipt accepts technical_reruns ([] and 1 record)", ok)
    unadmitted = [n for n in ORCHESTRATION if str((SNAP / n).resolve()) in decl_pins]
    check("orchestration scripts are outside the admitted pins (why the sidecar exists)", not unadmitted, unadmitted or None)

    # Configs.
    from clasher.rl.council_pilot import CouncilPilotConfig, load_pilot_config, load_source_pins

    base = tomllib.loads(BASE_CONFIG.read_text())
    max_envs = next(m.le for m in CouncilPilotConfig.model_fields["num_envs"].metadata if hasattr(m, "le"))
    outputs = set()
    for seed, path in CONFIGS.items():
        raw = tomllib.loads(path.read_text())
        changed = {k for k in set(base) | set(raw) if base.get(k) != raw.get(k)}
        check(f"seed {seed}: fields changed vs base == allowed set", changed == ALLOWED_CONFIG_CHANGES, sorted(changed))
        config = guarded(f"seed {seed}: load_pilot_config", lambda path=path: load_pilot_config(path))
        if config is None:
            continue
        check(f"seed {seed}: source_root = snapshot", Path(config.source_root).resolve() == SNAP)
        check(f"seed {seed}: gamedata_path = snapshot gamedata.json", Path(config.gamedata_path).resolve() == SNAP / "gamedata.json")
        check(f"seed {seed}: nominal_admission_path = v6 admission.json", Path(config.nominal_admission_path) == ADMISSION)
        check(f"seed {seed}: num_envs = admitted maximum", config.num_envs == max_envs == 8, f"{config.num_envs}/{max_envs}")
        check(f"seed {seed}: config file read-only", not (path.stat().st_mode & 0o222))
        outputs.add(config.output_dir)
        pilot_pins = guarded(f"seed {seed}: load_source_pins", lambda config=config: load_source_pins(config))
        if pilot_pins is None:
            continue
        # Mirror of require_admission's expected_source_pins loop
        # (readiness_capture_ownership.py lines 1293-1306). The stand-in receipt
        # is what evaluate_attempt will issue from the snapshot: source_root =
        # Path(readiness_capture_ownership.__file__).parents[3] (= snapshot) and
        # source_pins = the ledger declaration's source_pins.
        import clasher.rl.readiness_capture_ownership as rco

        receipt_root = Path(rco.__file__).resolve().parents[3]
        admitted = resolved((stored or declaration)["source_pins"])
        failures = []
        for filename, digest in pilot_pins.items():
            relative = Path(filename).resolve().relative_to(Path(config.source_root).resolve())
            original = str((receipt_root / relative).resolve())
            if admitted.get(original) != digest:
                failures.append(filename)
        check(f"seed {seed}: require_admission pin loop passes (stand-in receipt)", receipt_root == SNAP and not failures, failures[:5] or None)
        if run_protocol:
            from clasher.rl.council_evaluation import build_protocol, load_protocol

            same = guarded(f"seed {seed}: evaluation protocol", lambda config=config: load_protocol(Path(config.evaluation_protocol_path)) == build_protocol(config))
            if same is not None:
                check(f"seed {seed}: frozen evaluation protocol == build_protocol(config)", same, sha(Path(config.evaluation_protocol_path))[:12])
    check("three distinct output dirs", len(outputs) == 3)
    check("info: output dir existence (preflight fails if it creates a missing real output dir)", True, {o: Path(o).exists() for o in sorted(outputs)})


def admission_checks(config_path: Path | None) -> None:
    if not check("admission.json exists", ADMISSION.is_file(), str(ADMISSION)):
        return
    declaration = json.loads((ATT / "declaration.json").read_text())
    receipt = json.loads(ADMISSION.read_text())
    check("admission attempt id", receipt.get("attempt_id") == ATTEMPT, receipt.get("attempt_id"))
    check("admission source_root = snapshot", Path(receipt.get("source_root", "/")).resolve() == SNAP, receipt.get("source_root"))
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
            return check(f"require_pilot_admission (full ledger check) for {config_path.name}", r.attempt_id == ATTEMPT, r.attempt_id)

        guarded(f"require_pilot_admission (full ledger check) for {config_path.name}", full)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", action="store_true", help="also rebuild the evaluation protocol per config")
    parser.add_argument("--require-admission", action="store_true")
    parser.add_argument("--config", type=Path, help="config for the full require_pilot_admission check")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    static_checks(args.protocol)
    if args.require_admission:
        admission_checks(args.config)
    ok = all(c["ok"] for c in checks)
    summary = {
        "schema": "council-pilot-v6-launch-verification-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if ok else "failed",
        "admission_required": args.require_admission,
        "admission_present": ADMISSION.is_file(),
        "admission_sha256": sha(ADMISSION) if ADMISSION.is_file() else None,
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
