"""Offline rehearsal of the level-extension pipeline under the admitted runtime.

Uses the scalar-backed fake native probe (tests/level_extension_fake_native.py),
the real prospective configs and a clearly synthetic base admission. It
exercises declare -> collect -> scalar rankings -> scalar study -> assemble ->
pinned verifier with the runtime's own game data. Its output is never native
evidence and must never be passed to ``readiness_admission.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parent))
import level_extension_common as common  # noqa: E402

common.prefer_runtime_scripts()

import argparse  # noqa: E402
import json  # noqa: E402
import runpy  # noqa: E402
import types  # noqa: E402

import build_level_extension_evidence as builder  # noqa: E402
import collect_level_extension_probes as collector  # noqa: E402
import run_level_extension_scalar_study as scalar  # noqa: E402

from clasher.data import CardDataLoader  # noqa: E402
from clasher.paths import gamedata_path  # noqa: E402
from clasher.rl.native_public_observation import NativeProjectileCatalog  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configs-manifest", type=Path, required=True)
    parser.add_argument("--nominal-protocol-source", type=Path, required=True,
                        help="tests/test_training_readiness_v2.py (synthetic protocol factory)")
    parser.add_argument("--fake-native", type=Path, required=True,
                        help="tests/level_extension_fake_native.py")
    parser.add_argument("--decision-evidence", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-workspace-runtime", action="store_true")
    args = parser.parse_args()
    from run_readiness_v2 import public_views

    sys.path.append(str(args.fake_native.resolve().parent))
    from level_extension_fake_native import FAKE_ATTESTATION, FakeNative

    common.require_runtime_root(args.allow_workspace_runtime)

    catalog = NativeProjectileCatalog.from_csv(args.catalog, expected_sha256=args.catalog_sha256)
    gamedata = gamedata_path()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    proto = runpy.run_path(str(args.nominal_protocol_source))["protocol"]()
    (out / "synthetic-nominal-protocol.json").write_text(proto.model_dump_json(indent=2) + "\n")
    base = out / "synthetic-base-NOT-AN-ADMISSION.json"
    base.write_text(json.dumps({"protocol_sha256": proto.sha256, "gamedata_sha256": common.file_sha(gamedata),
                                "synthetic_rehearsal_only": True}, indent=2) + "\n")
    (out / "fake-attestation.json").write_text(json.dumps(FAKE_ATTESTATION) + "\n")
    builder.declare(args.configs_manifest, base, out / "fake-attestation.json", gamedata, out / "declaration")
    fake = FakeNative(CardDataLoader(gamedata))
    declaration = out / "declaration/declaration.json"
    native = collector.run(types.SimpleNamespace(
        declaration=declaration, configs_manifest=args.configs_manifest, gamedata=gamedata,
        output=out / "native", ranking_root_tick=common.DEFAULT_RANKING_ROOT_TICK,
        max_probe_tick=common.DEFAULT_MAX_PROBE_TICK,
    ), call=fake, session_factory=fake.session_factory, public_views=public_views, catalog=catalog, fast=False)
    rankings = scalar.run_rankings(types.SimpleNamespace(
        declaration=declaration, gamedata=gamedata, native_run=out / "native", output=out / "scalar-rankings"),
        catalog)
    study = scalar.run_adaptation(types.SimpleNamespace(
        declaration=declaration, gamedata=gamedata, base_admission=base, output=out / "scalar-adaptation"),
        catalog)
    try:
        receipt = builder.assemble(types.SimpleNamespace(
            declaration=declaration, base_admission=base, nominal_protocol=out / "synthetic-nominal-protocol.json",
            gamedata=gamedata, native_run=out / "native", scalar_rankings=out / "scalar-rankings",
            scalar_adaptation=out / "scalar-adaptation", independent_cards_decision_evidence=args.decision_evidence,
            output=out / "assembled"))
    except Exception:  # the verifier error is kept in local-verifier-check.json
        receipt = out / "assembled/level-extension-receipt.json"
        if not (out / "assembled/local-verifier-check.json").exists():
            raise
    check = json.loads((out / "assembled/local-verifier-check.json").read_text())
    summary = {
        "rehearsal_only": True,
        "gamedata_sha256": common.file_sha(gamedata),
        "runtime": common.runtime_identity(),
        "probes": [{"probe": p["probe"], "status": p["status"], "final_tick": p.get("final_tick"),
                    "coverage": p.get("coverage")} for p in native["probes"]],
        "native_failures": native["failures"],
        "scalar_ranking_branches": len(rankings["branches"]),
        "scalar_ranking_failures": len(rankings["failures"]),
        "adaptation_cases": len(study["cases"]),
        "receipt": str(receipt),
        "verifier": check.get("verified"),
        "verifier_error": check.get("verifier_error"),
        "verifier_module": str(Path(builder.level_module.__file__).resolve()),
        "fake_commands": sorted(set(fake.commands)),
    }
    common.write_new(out / "rehearsal-summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("native_failures", "scalar_ranking_branches", "adaptation_cases")}
                     | {"scope": (summary["verifier"] or {}).get("level_sampling_scope"),
                        "probe_status": [p["status"] for p in summary["probes"]],
                        "verifier_error": summary["verifier_error"]}))
    raise SystemExit(0 if summary["verifier"] else 1)


if __name__ == "__main__":
    main()
