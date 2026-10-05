#!/usr/bin/env python3
"""Write the v7r1 orchestration sidecar (write-once).

The pilot source freeze is the runtime's own pilot-source-pins.json (351
src/clasher modules of pilot-runtime-v1; 342 admission-bound digests equal the
m0-tier-a-fresh-v7 admission, 9 training-only modules pinned by the freeze, 3
of which differ from the admission). The configs point at it directly, so no
pin file is copied into this kit.

The orchestration scripts are outside both the admission pins and the pilot
freeze. This sidecar binds them by runtime path and hash, cross-checked against
pilot-runtime.json and the admitted native-final-v7/snapshot.json (the runtime's
scripts are unchanged from the base). The ledger verification tool
readiness_admission.py is bound at the admitted root, because the unchanged
ledger check only passes when imported from the admitted runtime.

Reads only. Creates one file with open("x"); refuses to overwrite.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

RC = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928")
RUNTIME = RC / "m0/runtime-snapshots/pilot-runtime-v1"
ADMITTED = RC / "m0/runtime-snapshots/native-final-v7"
ATT = RC / "m0/readiness/tier-a-fresh-v7"
DECISION = RC / "pilot/admission-scope-decision.json"
OUT = RC / "pilot/v7r1-launch"
SIDECAR = OUT / "orchestration-pins-pilot-runtime-v1.json"
MANIFEST = RUNTIME / "pilot-runtime.json"
PINS = RUNTIME / "pilot-source-pins.json"
ATTEMPT = "m0-tier-a-fresh-v7"
RUNTIME_MANIFEST_SHA = "b6433179fd57617b7c88a11af0e5be535327590851ed3121e65986f981c2cd76"
PIN_COUNT = 351
EXPECTED_CHANGED = [
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

    def bind(root: Path, names):
        out = {}
        for name in names:
            digest = sha(root / name)
            assert base[name] == digest == manifest["scripts_and_project_files"][name], name
            out[name] = {"path": str(root / name), "sha256": digest}
        return out

    sidecar = {
        "schema": "council-pilot-orchestration-pins-v2",
        "attempt_id": ATTEMPT,
        "reason": (
            "Admission-scope decision v1: the m0-tier-a-fresh-v7 admission binds the "
            "342 admission-bound src/clasher modules; the pilot freeze "
            "(pilot-runtime-v1/pilot-source-pins.json) pins all 351 src/clasher modules "
            "including the 9 training-only ones. The orchestration scripts are outside "
            "both and are bound here by runtime path and hash."
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
