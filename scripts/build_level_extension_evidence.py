"""Declare the level-extension probes and assemble the evidence-v2 receipt.

``declare`` freezes the four prospective probe configs against the issued
nominal admission, the pinned native attestation and the admitted ruleset
(``LevelExtensionDeclaration``). Run it *before* any probe executes.

``assemble`` gathers the raw native probe files, native and scalar ranking
branches and the scalar mixed-level study into a ``LevelExtensionReceipt``,
optionally binds the independent-card protocol decision, and then runs the
pinned verifier once as a local check. The receipt carries no pass flag; the
verifier (and ``readiness_admission.py extend-levels``) recompute everything.
No ledger is written here.
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
import time  # noqa: E402

import clasher.rl.readiness_level_extension as level_module  # noqa: E402
from clasher.paths import gamedata_path  # noqa: E402
from clasher.rl.readiness_level_extension import (  # noqa: E402
    PROBE_PLANS,
    FilePin,
    LevelExtensionDeclaration,
    LevelExtensionReceipt,
    LevelProbeDeclaration,
    NativeLevelProbe,
    configure_native_levels,
    verify_level_extension_receipt,
)
from clasher.rl.training_readiness_v2 import APPROVED_STRATEGY_SHA  # noqa: E402

RANKINGS_SCHEMA = "readiness-level-rankings-v1"
DECISION_SCHEMA = "readiness-level-randomization-decision-v1"


def fpin(path: Path) -> FilePin:
    return FilePin.model_validate(common.pin(path))


# ------------------------------------------------------------------ declare


def declare(configs_manifest: Path, base_admission: Path, native_attestation: Path, gamedata: Path,
            output: Path, attempt_declaration: Path | None = None) -> LevelExtensionDeclaration:
    manifest = json.loads(configs_manifest.read_text())
    if manifest.get("schema") != "readiness-level-probe-configs-v1":
        raise ValueError("unexpected probe config manifest")
    gamedata_sha = common.file_sha(gamedata)
    if manifest.get("gamedata_sha256") != gamedata_sha:
        raise ValueError("probe configs were prepared for another ruleset")
    admission = json.loads(base_admission.read_text())
    if admission.get("gamedata_sha256") not in (None, gamedata_sha):
        raise ValueError("base admission ruleset differs from the probe ruleset")
    if admission.get("parent_admission_path") is not None:
        raise ValueError("extensions bind the original nominal admission directly")
    attestation_sha = common.canonical_sha(json.loads(native_attestation.read_text()))
    if attempt_declaration is not None:
        attempt = json.loads(attempt_declaration.read_text())
        if attempt.get("native_attestation_sha256") != attestation_sha:
            raise ValueError("native attestation differs from the admitted attempt")
        if attempt.get("gamedata_sha256") != gamedata_sha:
            raise ValueError("admitted attempt ruleset differs from the probe ruleset")
    probes = []
    for row, plan in zip(manifest["probes"], PROBE_PLANS, strict=True):
        path = configs_manifest.parent / row["config_path"]
        config = json.loads(path.read_text())
        if (
            common.file_sha(path) != row["config_file_sha256"]
            or common.canonical_sha(config) != row["config_sha256"]
            or configure_native_levels(config, plan) != config
            or row["plan"] != plan.model_dump(mode="json")
        ):
            raise ValueError(f"probe config {path.name} differs from its manifest or plan")
        probes.append(LevelProbeDeclaration(plan=plan, config_sha256=row["config_sha256"]))
    declaration = LevelExtensionDeclaration(
        base_admission_sha256=common.file_sha(base_admission),
        native_attestation_sha256=attestation_sha,
        gamedata_sha256=gamedata_sha,
        probes=tuple(probes),
    )
    output.mkdir(parents=True, exist_ok=False)
    with (output / "declaration.json").open("x") as stream:
        stream.write(declaration.model_dump_json(indent=2) + "\n")
    common.write_new(output / "declaration-inputs.json", {
        "schema": "readiness-level-extension-declaration-inputs-v1",
        "declared_at": time.time(),
        "configs_manifest": common.pin(configs_manifest),
        "configs": [common.pin(configs_manifest.parent / r["config_path"]) for r in manifest["probes"]],
        "base_admission": common.pin(base_admission),
        "native_attestation": common.pin(native_attestation),
        "native_attestation_canonical_sha256": attestation_sha,
        "gamedata": common.pin(gamedata),
        "attempt_declaration": None if attempt_declaration is None else common.pin(attempt_declaration),
        "status": "declared_not_executed",
        "training_permission": None,
    })
    return declaration


# ----------------------------------------------------------------- assemble


def _require_pin(row: dict) -> FilePin:
    value = FilePin.model_validate(row)
    value.read_bytes()
    return value


def verifier_source_files() -> list[Path]:
    """The verifier's own required pins, resolved from the imported modules."""
    package = Path(level_module.__file__).resolve().parents[1]
    return [
        Path(level_module.__file__).resolve(),
        package / "tower_scaling.py",
        package / "balance.py",
        package / "stat_scaling.py",
        package / "data.py",
        package / "dynamic_spells.py",
        package / "rl" / "readiness_transport.py",
        package / "rl" / "native_command_checks.py",
        package / "rl" / "native_frame_storage.py",
    ]


def check_native_crown_projection(row: dict) -> None:
    """Re-derive each native Crown-only ending from its retained raw frame."""
    ending = _require_pin(row["ending_frame"]).payload()
    raw = _require_pin(ending["raw_frame"]).payload()
    ordinary = raw.get("ordinary", raw)
    if (
        ending.get("schema") != "readiness-level-ending-crowns-v1"
        or common.canonical_sha(ordinary) != ending["raw_ordinary_sha256"]
        or common.native_crown_frame(ordinary) != ending["ordinary"]
    ):
        raise ValueError("native Crown ending does not re-derive from its raw frame")


def check_ranking_provenance(native_rows: list, scalar_rows: list, native_run: Path,
                             scalar_run: Path) -> None:
    """Native and scalar branch rows must come from their own engines and files.

    The pinned verifier keys branches by ``engine`` but cannot tell a native
    ending from a scalar one. Here each native row must be ``reference`` with a
    native-form Crown projection under ``native_run`` (re-derived from its raw
    frame by ``check_native_crown_projection``), each scalar row ``scalar`` with
    a scalar-form ending under ``scalar_run``, and no ending file may be shared.
    Equal Crown HP in both engines is allowed (that is parity); swapped or
    duplicated evidence is not.
    """
    def ending(row: dict, root: Path) -> tuple[str, dict]:
        pin = _require_pin(row["ending_frame"])
        path = Path(pin.path).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError(f"{row.get('engine')} ranking ending lies outside its run: {pin.path}")
        return str(path), pin.payload()

    seen: dict[str, str] = {}
    for engine, rows, root in (("reference", native_rows, native_run), ("scalar", scalar_rows, scalar_run)):
        for row in rows:
            if row.get("engine") != engine:
                raise ValueError(f"{engine} ranking file carries a {row.get('engine')!r} branch")
            path, payload = ending(row, root)
            ordinary = payload.get("ordinary", payload)
            if engine == "reference":
                if payload.get("schema") != "readiness-level-ending-crowns-v1" or ordinary.get("engine") != "reference":
                    raise ValueError("native ranking ending is not a native Crown projection")
            elif payload.get("engine") != "scalar" or "raw_frame" in payload:
                raise ValueError("scalar ranking ending is not a scalar Crown frame")
            if path in seen:
                raise ValueError(f"ranking ending file is shared by {seen[path]} and {engine} branches")
            seen[path] = engine


def margin_summary(rankings: dict, study: dict | None) -> dict:
    """Informational margins recomputed with the verifier's own helpers (no verdict)."""
    from clasher.rl.readiness_level_extension import (
        ANCHORS, INFORMATIVE_MARGIN, _crown_hp, _ending_ordinary, _plan_max_hp,
    )
    from clasher.tower_scaling import tower_stat

    margins = {}
    for row in rankings["branches"]:
        plan = PROBE_PLANS[row["probe"]]
        hps = _crown_hp(_ending_ordinary(row), _plan_max_hp(plan))
        owner = row["probe"] % 2
        margins[(row["probe"], row["condition"], row["candidate"], row["engine"])] = (
            (hps[owner] - hps[1 - owner]) / plan.starting_crown_hp(owner)
        )
    probes = []
    for p in range(4):
        row = {"probe": p}
        for engine in ("reference", "scalar"):
            try:
                row[engine] = [sum(margins[p, c, a, engine] for c in range(2)) / 2 for a in range(2)]
            except KeyError:
                row[engine] = None
        if row["reference"] and row["scalar"]:
            chosen = [a for a in range(2) if row["scalar"][a] == max(row["scalar"])]
            row["regret"] = max(row["reference"]) - min(row["reference"][a] for a in chosen)
            row["reference_separation"] = abs(row["reference"][0] - row["reference"][1])
        probes.append(row)
    cases = []
    for case in (study or {}).get("cases", []):
        towers, owner = case["tower_levels"], case["root_owner"]
        maximum = {a: tower_stat("KingTower" if s == 2 else "PrincessTower", "hitpoints", towers[a[0]])
                   for a, s in ANCHORS.items()}
        denominator = sum(v for (o, _x, _y), v in maximum.items() if o == owner)
        values = []
        for branch in case["branches"]:
            hps = _crown_hp(_ending_ordinary(branch), maximum)
            values.append((hps[owner] - hps[1 - owner]) / denominator)
        cases.append({"case": case["case"], "margins": values,
                      "separation": abs(values[0] - values[1]) if len(values) == 2 else None})
    return {"informative_margin": INFORMATIVE_MARGIN, "probes": probes, "adaptation_cases": cases}


def assemble(args) -> Path:
    declaration_pin = fpin(args.declaration)
    declaration = LevelExtensionDeclaration.model_validate_json(declaration_pin.read_bytes())
    base_sha = common.file_sha(args.base_admission)
    if declaration.base_admission_sha256 != base_sha:
        raise ValueError("declaration belongs to another base admission")
    if common.file_sha(args.gamedata) != declaration.gamedata_sha256:
        raise ValueError("gamedata differs from the declaration")
    native = json.loads((args.native_run / "collection-result.json").read_text())
    if native["declaration"]["sha256"] != declaration_pin.sha256:
        raise ValueError("native collection belongs to another declaration")
    if native.get("producer_sources_unchanged") is not True:
        raise ValueError("native producer sources changed during collection")
    for name, digest in native["source_pins"].items():
        if common.file_sha(Path(name)) != digest:
            raise ValueError(f"native producer source changed since collection: {name}")
    probes = []
    for record, declared in zip(native["probes"], declaration.probes, strict=True):
        if record.get("status") == "failed" or "raw" not in record:
            raise ValueError(f"native probe {record['probe']} failed; the receipt needs all four")
        raw = record["raw"]
        probes.append(NativeLevelProbe(
            config=_require_pin(record["config"]),
            frames=_require_pin(raw["frames.jsonl.gz"]),
            verified_read_session=_require_pin(raw["read-session.json"]),
            transport_decisions=_require_pin(raw["decisions.jsonl.gz"]),
            transport_rows=_require_pin(raw["transport.jsonl.gz"]),
        ))
        if common.canonical_sha(probes[-1].config.payload()) != declared.config_sha256:
            raise ValueError("native probe config differs from its declaration")
    native_rankings = json.loads((args.native_run / "native-rankings.json").read_text())
    scalar_rankings = json.loads((args.scalar_rankings / "scalar-rankings.json").read_text())
    for study in (native_rankings, scalar_rankings):
        if study["declaration_sha256"] != declaration_pin.sha256:
            raise ValueError("ranking branches belong to another declaration")
    for row in native_rankings["branches"]:
        check_native_crown_projection(row)
    check_ranking_provenance(native_rankings["branches"], scalar_rankings["branches"],
                             args.native_run, args.scalar_rankings)
    args.output.mkdir(parents=True, exist_ok=False)
    rankings = common.write_new(args.output / "rankings.json", {
        "schema": RANKINGS_SCHEMA,
        "declaration_sha256": declaration_pin.sha256,
        "horizon_ticks": common.HORIZON_TICKS,
        "conditions": list(common.RANKING_CONDITIONS),
        "branches": native_rankings["branches"] + scalar_rankings["branches"],
        "native_rankings": common.pin(args.native_run / "native-rankings.json"),
        "native_collection": common.pin(args.native_run / "collection-result.json"),
        "scalar_rankings": common.pin(args.scalar_rankings / "scalar-rankings.json"),
        "scalar_failures": scalar_rankings.get("failures", []),
    })
    scalar_adaptation = decision = None
    if args.scalar_adaptation is not None:
        scalar_adaptation = fpin(args.scalar_adaptation / "scalar-adaptation.json")
    if args.independent_cards_decision_evidence is not None:
        if scalar_adaptation is None:
            raise ValueError("independent-card scope needs the scalar adaptation study")
        decision = fpin(Path(common.write_new(args.output / "level-randomization-decision.json", {
            "schema": DECISION_SCHEMA,
            "status": "approved",
            "strategy_sha256": APPROVED_STRATEGY_SHA,
            "base_admission_sha256": base_sha,
            "native_declaration_sha256": declaration_pin.sha256,
            "level_sampling_scope": "independent_cards",
            "scalar_adaptation_sha256": scalar_adaptation.sha256,
            "decision_evidence": common.pin(args.independent_cards_decision_evidence),
            "basis": "implementer application of the approved schedule (implementation decision), "
                     "bounded to 10-12; no new council endorsement is claimed",
            "created_at": time.time(),
        })["path"]))
    tool_files = [
        Path(__file__).resolve(), Path(common.__file__).resolve(),
        Path(common.SCRIPT_DIR / "collect_level_extension_probes.py"),
        Path(common.SCRIPT_DIR / "run_level_extension_scalar_study.py"),
    ]
    helpers = [
        Path(__import__(name).__file__).resolve()
        for name in ("read_native_public_levels", "run_readiness_v2", "smoke_reference_battle")
    ]
    pins = common.source_pins([*verifier_source_files(), *helpers, *[p for p in tool_files if p.exists()]])
    receipt = LevelExtensionReceipt(
        declaration=declaration_pin,
        base_admission=fpin(args.base_admission),
        nominal_protocol=fpin(args.nominal_protocol),
        ranking_checks=FilePin.model_validate(rankings),
        gamedata=fpin(args.gamedata),
        source_pins=pins,
        probes=tuple(probes),
        protocol_decision=decision,
        scalar_adaptation=scalar_adaptation if decision is not None else None,
    )
    receipt_path = args.output / "level-extension-receipt.json"
    with receipt_path.open("x") as stream:
        stream.write(receipt.model_dump_json(indent=2) + "\n")
    local = {"schema": "readiness-level-extension-local-check-v1", "receipt": common.pin(receipt_path),
             "process_gamedata": str(gamedata_path()), "checked_at": time.time(),
             "note": "informational only; admission re-verifies with extend-levels"}
    try:
        local["margins"] = margin_summary(
            FilePin.model_validate(rankings).payload(),
            None if scalar_adaptation is None else scalar_adaptation.payload(),
        )
    except Exception as error:  # informational only
        local["margins_error"] = f"{type(error).__name__}: {error}"
    try:
        verified = verify_level_extension_receipt(receipt_path, base_admission_sha256=base_sha)
    except Exception as error:
        local.update(verifier_error=f"{type(error).__name__}: {error}")
        common.write_new(args.output / "local-verifier-check.json", local)
        raise
    local.update(verified=json.loads(verified.model_dump_json()))
    common.write_new(args.output / "local-verifier-check.json", local)
    return receipt_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("declare")
    d.add_argument("--configs-manifest", type=Path, required=True)
    d.add_argument("--base-admission", type=Path, required=True)
    d.add_argument("--native-attestation", type=Path, required=True)
    d.add_argument("--gamedata", type=Path, required=True)
    d.add_argument("--attempt-declaration", type=Path)
    d.add_argument("--output", type=Path, required=True)
    a = sub.add_parser("assemble")
    a.add_argument("--declaration", type=Path, required=True)
    a.add_argument("--base-admission", type=Path, required=True)
    a.add_argument("--nominal-protocol", type=Path, required=True)
    a.add_argument("--gamedata", type=Path, required=True)
    a.add_argument("--native-run", type=Path, required=True)
    a.add_argument("--scalar-rankings", type=Path, required=True)
    a.add_argument("--scalar-adaptation", type=Path)
    a.add_argument("--independent-cards-decision-evidence", type=Path)
    a.add_argument("--output", type=Path, required=True)
    for parser_ in (d, a):
        parser_.add_argument("--allow-workspace-runtime", action="store_true")
    args = parser.parse_args()
    common.require_runtime_root(args.allow_workspace_runtime)
    if args.command == "declare":
        declaration = declare(args.configs_manifest, args.base_admission, args.native_attestation,
                              args.gamedata, args.output, args.attempt_declaration)
        print(json.dumps({"declaration": str(args.output / "declaration.json"),
                          "probes": [p.config_sha256 for p in declaration.probes]}))
        return
    path = assemble(args)
    check = json.loads((args.output / "local-verifier-check.json").read_text())
    print(json.dumps({"receipt": str(path), "local_check": check.get("verified", {}).get("level_sampling_scope")}))


if __name__ == "__main__":
    main()
