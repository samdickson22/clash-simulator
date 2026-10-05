#!/usr/bin/env python3
"""Write the v7r2 orchestration sidecar (write-once).

The pilot source freeze is pilot-runtime-v2's own pilot-source-pins.json (351
src/clasher modules; 342 admission-bound digests equal the m0-tier-a-fresh-v7
admission; 9 training-only modules pinned by the freeze, 4 of which differ from
the admission: council_monitor, council_pilot, parallel_rollout,
train_recurrent).

The orchestration scripts are outside both the admission pins and the pilot
freeze. This sidecar binds them by runtime path and hash, cross-checked against
pilot-runtime.json. Two of them differ from the admitted native-final-v7
snapshot (recipe fix, pilot/diagnosis-1M): run_council_pilot.py and
preflight_council_pilot.py publish the opponent pool through
council_pilot.opponent_initialization_paths (and the launch record carries the
entropy recipe); both are recorded with their base digests. The ledger
verification tool readiness_admission.py is bound at the admitted root.

Reads only. Creates one file with open("x"); refuses to overwrite.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

RC = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928")
RUNTIME = RC / "m0/runtime-snapshots/pilot-runtime-v2"
ADMITTED = RC / "m0/runtime-snapshots/native-final-v7"
ATT = RC / "m0/readiness/tier-a-fresh-v7"
DECISION = RC / "pilot/admission-scope-decision.json"
OUT = RC / "pilot/v7r2-launch"
SIDECAR = OUT / "orchestration-pins-pilot-runtime-v2.json"
MANIFEST = RUNTIME / "pilot-runtime.json"
PINS = RUNTIME / "pilot-source-pins.json"
ATTEMPT = "m0-tier-a-fresh-v7"
RUNTIME_MANIFEST_SHA = "826a3d035983c90850e828b1f3bbb715646f3d03fb2b91f729b4611ce1a8baf1"
PIN_COUNT = 351
EXPECTED_CHANGED = [
    "src/clasher/rl/council_monitor.py",
    "src/clasher/rl/council_pilot.py",
    "src/clasher/rl/parallel_rollout.py",
    "src/clasher/rl/train_recurrent.py",
]
ORCHESTRATION = (
    "scripts/run_council_pilot.py",
    "scripts/run_council_warmstart.py",
    "scripts/evaluate_council_pilot.py",
    "scripts/preflight_council_pilot.py",
)
CHANGED_SCRIPTS = ("scripts/preflight_council_pilot.py", "scripts/run_council_pilot.py")
VERIFICATION_TOOLS = ("scripts/readiness_admission.py",)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert sha(MANIFEST) == RUNTIME_MANIFEST_SHA, "pilot-runtime.json changed"
    manifest = json.loads(MANIFEST.read_text())
    base = json.loads((ADMITTED / "snapshot.json").read_text())["source_files"]
    declaration = json.loads((ATT / "declaration.json").read_text())
    assert declaration["attempt_id"] == ATTEMPT
    assert Path(manifest["base_snapshot"]).resolve() == ADMITTED.resolve()
    assert manifest["base_snapshot_manifest_sha256"] == sha(ADMITTED / "snapshot.json")
    assert manifest["pilot_source_pins_sha256"] == sha(PINS)
    assert manifest["decision_sha256"] == sha(DECISION)
    assert manifest["admission_sha256"] == sha(ATT / "admission.json")
    pins = json.loads(PINS.read_text())
    assert len(pins) == PIN_COUNT, len(pins)
    changed = sorted(n for n, e in manifest["files"].items() if e["changed_from_admission"])
    assert changed == EXPECTED_CHANGED, changed
    assert sorted(manifest["scripts_changed_from_base"]) == sorted(CHANGED_SCRIPTS)
    admitted_pins = {str(Path(k).resolve()) for k in declaration["source_pins"]}

    def bind(root: Path, names):
        out = {}
        for name in names:
            digest = sha(root / name)
            assert str((ADMITTED / name).resolve()) not in admitted_pins or root == ADMITTED, name
            if root == RUNTIME and name in CHANGED_SCRIPTS:
                assert digest == manifest["scripts_and_project_files"][name] != base[name], name
                out[name] = {"path": str(root / name), "sha256": digest,
                             "admitted_snapshot_sha256": base[name], "changed_from_base": True}
            else:
                assert base[name] == digest, name
                if root == RUNTIME:
                    assert digest == manifest["scripts_and_project_files"][name], name
                out[name] = {"path": str(root / name), "sha256": digest}
        return out

    sidecar = {
        "schema": "council-pilot-orchestration-pins-v3",
        "attempt_id": ATTEMPT,
        "reason": (
            "Admission-scope decision v1: the m0-tier-a-fresh-v7 admission binds the "
            "342 admission-bound src/clasher modules; the pilot freeze "
            "(pilot-runtime-v2/pilot-source-pins.json) pins all 351 src/clasher modules "
            "including the 9 training-only ones. The orchestration scripts are outside "
            "both and are bound here by runtime path and hash; two of them carry the "
            "v7r2 recipe fix (opponent pool publication, launch metadata)."
        ),
        "runtime_root": str(RUNTIME),
        "runtime_manifest_path": str(MANIFEST),
        "runtime_manifest_sha256": sha(MANIFEST),
        "admitted_root": str(ADMITTED),
        "admitted_manifest_sha256": sha(ADMITTED / "snapshot.json"),
        "declaration_path": str(ATT / "declaration.json"),
        "declaration_sha256": sha(ATT / "declaration.json"),
        "freeze_receipt_sha256": sha(ATT / "freeze-receipt.json"),
        "technical_rerun_policy": declaration.get("technical_rerun_policy", "none"),
        "decision_path": str(DECISION),
        "decision_sha256": sha(DECISION),
        "source_pins_path": str(PINS),
        "source_pins_sha256": sha(PINS),
        "source_pins_count": len(pins),
        "admission_path": str(ATT / "admission.json"),
        "admission_sha256": sha(ATT / "admission.json"),
        "training_only_changed_vs_admission": {
            name: {
                "admission_sha256": manifest["files"][name]["admission_sha256"],
                "pilot_runtime_sha256": manifest["files"][name]["sha256"],
            }
            for name in EXPECTED_CHANGED
        },
        "scripts": bind(RUNTIME, ORCHESTRATION),
        "verification_tools": bind(ADMITTED, VERIFICATION_TOOLS),
        "verification_tools_note": "readiness_admission.py verify runs from the admitted root (native-final-v7); from the pilot runtime the unchanged ledger check refuses by design",
    }
    with SIDECAR.open("x") as stream:
        json.dump(sidecar, stream, indent=2)
        stream.write("\n")
    SIDECAR.chmod(0o444)
    print(SIDECAR, sha(SIDECAR))


if __name__ == "__main__":
    main()
