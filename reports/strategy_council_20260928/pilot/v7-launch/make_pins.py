#!/usr/bin/env python3
"""Write the v7 pilot source-pin file and the orchestration sidecar (write-once).

Coordinator decision (2026-09-29, carried over from the v6 kit): the pilot
source-pin file holds exactly the admitted ``src/clasher`` modules from the
m0-tier-a-fresh-v7 declaration's ``source_pins``. The orchestration scripts are
not in that declaration, so a sidecar binds them by snapshot path and hash from
native-final-v7/snapshot.json.

native-final-v7 vs native-final-v6 (from the two snapshot.json manifests):
0 added, 0 removed, 2 changed files: src/clasher/entities.py and
src/clasher/battle.py (the tier-a-fresh-v6 divergence fixes). Both are
simulation modules on the pilot path and both are admitted src/clasher pins,
so the pin count stays 351. The sidecar records the delta.

Reads only. Creates two files with open("x"); refuses to overwrite.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

RC = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928")
SNAP = RC / "m0/runtime-snapshots/native-final-v7"
PREV_SNAP = RC / "m0/runtime-snapshots/native-final-v6"
ATT = RC / "m0/readiness/tier-a-fresh-v7"
OUT = RC / "pilot/v7-launch"
PINS = OUT / "source-pins-native-final-v7.json"
SIDECAR = OUT / "orchestration-pins-native-final-v7.json"
ATTEMPT = "m0-tier-a-fresh-v7"
PIN_COUNT = 351
ORCHESTRATION = (
    "scripts/run_council_pilot.py",
    "scripts/run_council_warmstart.py",
    "scripts/evaluate_council_pilot.py",
    "scripts/preflight_council_pilot.py",
)
# Used by launch.sh for the ledger verify step only; not part of the pilot run.
VERIFICATION_TOOLS = ("scripts/readiness_admission.py",)
EXPECTED_ADDED: list[str] = []
EXPECTED_CHANGED = [
    "src/clasher/battle.py",
    "src/clasher/entities.py",
]

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    declaration = json.loads((ATT / "declaration.json").read_text())
    assert declaration["attempt_id"] == ATTEMPT
    src = (SNAP / "src/clasher").resolve()
    pins = {
        key: digest
        for key, digest in sorted(declaration["source_pins"].items())
        if Path(key).resolve().is_relative_to(src)
    }
    on_disk = {str(p.resolve()) for p in src.rglob("*.py")}
    assert {str(Path(k).resolve()) for k in pins} == on_disk, "pin set != snapshot src/clasher"
    assert len(pins) == PIN_COUNT, len(pins)
    assert all(sha(Path(k)) == v for k, v in pins.items()), "snapshot bytes != declaration"
    changed_pinned = sorted(str(p.relative_to(SNAP.resolve())) for p in map(Path, pins) if p.name in ("battle.py", "entities.py") and p.parent == src)
    assert changed_pinned == EXPECTED_CHANGED, changed_pinned
    # Every other pin equals the v6 kit's pin file (path-retargeted).
    v6_pins = json.loads((RC / "pilot/v6-launch/source-pins-native-final-v6.json").read_text())
    v6_pins = {k.replace("/native-final-v6/", "/native-final-v7/"): v for k, v in v6_pins.items()}
    assert set(v6_pins) == set(pins), "pin key set differs from v6 kit"
    differs = sorted(str(Path(k).relative_to(SNAP)) for k in pins if pins[k] != v6_pins[k])
    assert differs == EXPECTED_CHANGED, differs
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
    assert not set(previous) - set(manifest), "v7 dropped files present in v6"
    added = sorted(set(manifest) - set(previous))
    changed = sorted(n for n in previous if previous[n] != manifest[n])
    assert added == EXPECTED_ADDED, added
    assert changed == EXPECTED_CHANGED, changed
    delta = {
        name: {"native_final_v6_sha256": previous.get(name), "native_final_v7_sha256": manifest[name]}
        for name in sorted(added + changed)
    }
    assert all(previous[n] == manifest[n] for n in ORCHESTRATION), "orchestration changed vs v6"

    sidecar = {
        "schema": "council-pilot-orchestration-pins-v1",
        "attempt_id": ATTEMPT,
        "reason": (
            "The orchestration scripts are outside the m0-tier-a-fresh-v7 admitted "
            "source_pins (351 src/clasher modules + 7 readiness scripts). The pilot "
            "pin file holds exactly the admitted src/clasher subset; these scripts "
            "are bound by snapshot path and hash from native-final-v7/snapshot.json."
        ),
        "coordinator_decision": "2026-09-29 (carried over to v7): pin scope = admitted src/clasher modules; scripts via this sidecar",
        "snapshot_root": str(SNAP),
        "snapshot_manifest_sha256": sha(SNAP / "snapshot.json"),
        "declaration_path": str(ATT / "declaration.json"),
        "declaration_sha256": sha(ATT / "declaration.json"),
        "freeze_receipt_sha256": sha(ATT / "freeze-receipt.json"),
        "technical_rerun_policy": declaration.get("technical_rerun_policy", "none"),
        "source_pins_path": str(PINS),
        "source_pins_sha256": sha(PINS),
        "source_pins_count": len(pins),
        "admission_path": str(ATT / "admission.json"),
        "admission_sha256": sha(ATT / "admission.json"),
        "admission_note": "admission.json was issued (ledger-verified) before this sidecar was written; launch.sh also records its digest in each launch receipt",
        "source_delta_vs_native_final_v6": delta,
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
