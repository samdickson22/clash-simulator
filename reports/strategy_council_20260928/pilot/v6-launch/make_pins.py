#!/usr/bin/env python3
"""Write the v6 pilot source-pin file and the orchestration sidecar (write-once).

Coordinator decision (2026-09-29): the pilot source-pin file holds exactly the
admitted ``src/clasher`` modules from the m0-tier-a-fresh-v6 declaration's
``source_pins``. The orchestration scripts are not in that declaration, so a
sidecar binds them by snapshot path and hash from native-final-v6/snapshot.json.

native-final-v6 vs native-final-v5 (from the two snapshot.json manifests):
11 added files (4 src/clasher/rl/readiness_tier_b*.py modules + 7 scripts) and
9 changed readiness/transport files. The added src modules are picked up by
required_source_pins() (rglob of src/clasher), so they are in the declaration
and therefore in the pin file (351 = 347 + 4). The sidecar records the delta.

Reads only. Creates two files with open("x"); refuses to overwrite.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

RC = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928")
SNAP = RC / "m0/runtime-snapshots/native-final-v6"
PREV_SNAP = RC / "m0/runtime-snapshots/native-final-v5"
ATT = RC / "m0/readiness/tier-a-fresh-v6"
OUT = RC / "pilot/v6-launch"
PINS = OUT / "source-pins-native-final-v6.json"
SIDECAR = OUT / "orchestration-pins-native-final-v6.json"
ATTEMPT = "m0-tier-a-fresh-v6"
PIN_COUNT = 351
ORCHESTRATION = (
    "scripts/run_council_pilot.py",
    "scripts/run_council_warmstart.py",
    "scripts/evaluate_council_pilot.py",
    "scripts/preflight_council_pilot.py",
)
# Used by launch.sh for the ledger verify step only; not part of the pilot run.
VERIFICATION_TOOLS = ("scripts/readiness_admission.py",)
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
    tier_b = sorted(str(p.relative_to(SNAP.resolve())) for p in map(Path, pins) if p.name.startswith("readiness_tier_b"))
    assert tier_b == [n for n in EXPECTED_ADDED if n.startswith("src/")], tier_b
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
    assert not set(previous) - set(manifest), "v6 dropped files present in v5"
    added = sorted(set(manifest) - set(previous))
    changed = sorted(n for n in previous if previous[n] != manifest[n])
    assert added == EXPECTED_ADDED, added
    assert changed == EXPECTED_CHANGED, changed
    delta = {
        name: {"native_final_v5_sha256": previous.get(name), "native_final_v6_sha256": manifest[name]}
        for name in sorted(added + changed)
    }
    assert all(previous[n] == manifest[n] for n in ORCHESTRATION), "orchestration changed vs v5"

    sidecar = {
        "schema": "council-pilot-orchestration-pins-v1",
        "attempt_id": ATTEMPT,
        "reason": (
            "The orchestration scripts are outside the m0-tier-a-fresh-v6 admitted "
            "source_pins (351 src/clasher modules + 7 readiness scripts). The pilot "
            "pin file holds exactly the admitted src/clasher subset; these scripts "
            "are bound by snapshot path and hash from native-final-v6/snapshot.json."
        ),
        "coordinator_decision": "2026-09-29: pin scope = admitted src/clasher modules; scripts via this sidecar",
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
        "admission_sha256": None,
        "admission_note": "admission.json did not exist when this sidecar was written; launch.sh records its digest in each launch receipt",
        "source_delta_vs_native_final_v5": delta,
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
