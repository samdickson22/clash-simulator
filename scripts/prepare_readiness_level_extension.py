"""Prepare four bounded level probes; no native execution or admission issuance."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from clasher.data import CardDataLoader
from clasher.rl.readiness_execution import canonical_sha, file_sha
from clasher.rl.readiness_level_extension import (
    BODY_CHECKS,
    PROBE_PLANS,
    SPELL_CHECKS,
    LevelExtensionDeclaration,
    LevelProbeDeclaration,
    configure_native_levels,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nominal-config", type=Path, required=True)
    parser.add_argument("--gamedata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-admission", type=Path)
    parser.add_argument("--native-attestation", type=Path)
    args = parser.parse_args()
    if (args.base_admission is None) != (args.native_attestation is None):
        parser.error(
            "bind both base admission and native attestation, or leave the draft unbound"
        )
    original = json.loads(args.nominal_config.read_text())
    if (
        original["battle"].get("lvlcap") != 11
        or original["battle"].get("cardlvlmin") != 11
    ):
        raise ValueError("input must be a nominal level11 configuration")
    loader = CardDataLoader(args.gamedata)
    deck = (*BODY_CHECKS, *SPELL_CHECKS, "HogRider")
    ids = [loader.get_card(name)._raw_entry["id"] for name in deck]
    template = copy.deepcopy(original)
    for owner in (0, 1):
        template["battle"][f"deck{owner}"]["sp"] = [{"d": i} for i in ids]
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    probes = []
    for index, plan in enumerate(PROBE_PLANS):
        config = configure_native_levels(template, plan)
        path = args.output / f"probe-{index}.json"
        path.write_text(json.dumps(config, indent=2) + "\n")
        probes.append(
            LevelProbeDeclaration(plan=plan, config_sha256=canonical_sha(config))
        )
        rows.append(
            {
                "plan": plan.model_dump(mode="json"),
                "config_path": path.name,
                "config_sha256": canonical_sha(config),
                "config_file_sha256": file_sha(path),
                "starting_crown_hp_by_owner": [
                    plan.starting_crown_hp(o) for o in (0, 1)
                ],
            }
        )
    if args.base_admission is not None:
        declaration = LevelExtensionDeclaration(
            base_admission_sha256=file_sha(args.base_admission),
            native_attestation_sha256=canonical_sha(
                json.loads(args.native_attestation.read_text())
            ),
            gamedata_sha256=file_sha(args.gamedata),
            probes=tuple(probes),
        )
        (args.output / "declaration.json").write_text(
            declaration.model_dump_json(indent=2) + "\n"
        )
    manifest = {
        "schema": "readiness-level-probe-configs-v1",
        "status": "declared_not_executed"
        if args.base_admission
        else "draft_missing_nominal_admission",
        "native_scope": "uniform_cards_asymmetric_kings",
        "training_permission": None,
        "source_config_sha256": file_sha(args.nominal_config),
        "gamedata_sha256": file_sha(args.gamedata),
        "deck": deck,
        "probes": rows,
        "independent_acceptance_family_count": 0,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Prepared {len(rows)} unexecuted level probes; no training permission")


if __name__ == "__main__":
    main()
