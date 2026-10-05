#!/usr/bin/env python3
"""Write the v5 pilot source-pin file and the orchestration sidecar (write-once).

Coordinator decision (2026-09-29): the pilot source-pin file holds exactly the
admitted ``src/clasher`` modules from the m0-tier-a-fresh-v5 declaration's
``source_pins``. The orchestration scripts are not in that declaration, so a
sidecar binds them by snapshot path and hash from native-final-v5/snapshot.json.

native-final-v5 = native-final-v4 + a fixed src/clasher/entities.py; the sidecar
records that one-file source delta (from the two snapshot.json manifests).

Reads only. Creates two files with open("x"); refuses to overwrite.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

RC = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928")
SNAP = RC / "m0/runtime-snapshots/native-final-v5"
PREV_SNAP = RC / "m0/runtime-snapshots/native-final-v4"
ATT = RC / "m0/readiness/tier-a-fresh-v5"
OUT = RC / "pilot/v5-launch"
PINS = OUT / "source-pins-native-final-v5.json"
SIDECAR = OUT / "orchestration-pins-native-final-v5.json"
ORCHESTRATION = (
    "scripts/run_council_pilot.py",
    "scripts/run_council_warmstart.py",
    "scripts/evaluate_council_pilot.py",
    "scripts/preflight_council_pilot.py",
)
# Used by launch.sh for the ledger verify step only; not part of the pilot run.
VERIFICATION_TOOLS = ("scripts/readiness_admission.py",)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    declaration = json.loads((ATT / "declaration.json").read_text())
    assert declaration["attempt_id"] == "m0-tier-a-fresh-v5"
    src = (SNAP / "src/clasher").resolve()
    pins = {
        key: digest
        for key, digest in sorted(declaration["source_pins"].items())
        if Path(key).resolve().is_relative_to(src)
    }
    on_disk = {str(p.resolve()) for p in src.rglob("*.py")}
    assert {str(Path(k).resolve()) for k in pins} == on_disk, "pin set != snapshot src/clasher"
    assert len(pins) == 347, len(pins)
    assert all(sha(Path(k)) == v for k, v in pins.items()), "snapshot bytes != declaration"
    with PINS.open("x") as stream:
        json.dump(pins, stream, indent=2)
        stream.write("\n")

    manifest = json.loads((SNAP / "snapshot.json").read_text())["source_files"]

    def bind(names):
        out = {}
        for name in names:
            digest = sha(SNAP / name)
            assert manifest[name] == digest, name
            out[name] = {"path": str(SNAP / name), "sha256": digest}
        return out

    previous = json.loads((PREV_SNAP / "snapshot.json").read_text())["source_files"]
    assert set(previous) == set(manifest), "v4/v5 snapshot file sets differ"
    delta = {name: {"native_final_v4_sha256": previous[name], "native_final_v5_sha256": manifest[name]}
             for name in sorted(manifest) if previous[name] != manifest[name]}
    assert list(delta) == ["src/clasher/entities.py"], list(delta)

    sidecar = {
        "schema": "council-pilot-orchestration-pins-v1",
        "attempt_id": "m0-tier-a-fresh-v5",
        "reason": (
            "The orchestration scripts are outside the m0-tier-a-fresh-v5 admitted "
            "source_pins (347 src/clasher modules + 7 readiness scripts). The pilot "
            "pin file holds exactly the admitted src/clasher subset; these scripts "
            "are bound by snapshot path and hash from native-final-v5/snapshot.json."
        ),
        "coordinator_decision": "2026-09-29: pin scope = admitted src/clasher modules; scripts via this sidecar",
        "snapshot_root": str(SNAP),
        "snapshot_manifest_sha256": sha(SNAP / "snapshot.json"),
        "declaration_path": str(ATT / "declaration.json"),
        "declaration_sha256": sha(ATT / "declaration.json"),
        "freeze_receipt_sha256": sha(ATT / "freeze-receipt.json"),
        "source_pins_path": str(PINS),
        "source_pins_sha256": sha(PINS),
        "source_pins_count": len(pins),
        "admission_path": str(ATT / "admission.json"),
        "admission_sha256": None,
        "admission_note": "admission.json did not exist when this sidecar was written; launch.sh records its digest in each launch receipt",
        "source_delta_vs_native_final_v4": delta,
        "scripts": bind(ORCHESTRATION),
        "verification_tools": bind(VERIFICATION_TOOLS),
    }
    with SIDECAR.open("x") as stream:
        json.dump(sidecar, stream, indent=2)
        stream.write("\n")
    print(PINS, sidecar["source_pins_sha256"])
    print(SIDECAR, sha(SIDECAR))


if __name__ == "__main__":
    main()
