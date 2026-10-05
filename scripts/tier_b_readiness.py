"""Tier B learned-policy transfer: offline steps around native capture/branches.

Subcommands never start an emulator. Native prefixes use
``collect_tier_b_prefix.py``; branches use ``run_readiness_v2.py execute``
with a ``tier_b_transfer`` plan. See
reports/strategy_council_20260928/m0/tier-b/RUNBOOK.md for the exact order.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from clasher.rl.readiness_capture_ownership import get_root_seal
from clasher.rl.readiness_execution import ExecutionPlan, canonical_sha, file_sha, jobs
from clasher.rl.readiness_tier_b import TierBRootBank
from clasher.rl.readiness_tier_b_ledger import (
    _captures,
    _read,
    build_frozen_tier_b_protocol,
    declare_tier_b_attempt,
    evaluate_tier_b_attempt,
    get_tier_b_attempt,
    get_tier_b_root_seal,
    materialize_tier_b_configs,
    seal_tier_b_roots,
    tier_b_declaration_from_bank,
)
from clasher.rl.training_readiness_v2 import MechanismReview

WORKSPACE = Path(__file__).resolve().parents[1]


def write_new(path: Path, value) -> None:
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def generate_roots(args) -> int:
    from clasher.rl.readiness_tier_b_policy import (
        IncompleteRootBank,
        generate_tier_b_root_bank,
        load_frozen_policy,
        probe_slots,
    )

    policy = load_frozen_policy(args.checkpoint, decks_path=args.decks)
    slots = None
    if args.block == "targeted_probe":
        from clasher.rl.readiness_tier_b_policy import DEFAULT_DECK_TABLE

        slots = probe_slots(DEFAULT_DECK_TABLE, per_kind=args.probe_roots_per_kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        bank = generate_tier_b_root_bank(
            policy,
            master_seed=args.master_seed,
            block_kind=args.block,
            slots=slots,
            window_ticks=args.window_ticks,
            max_draws_per_root=args.max_draws,
        )
    except IncompleteRootBank as error:
        write_new(
            args.output.with_suffix(".incomplete.json"),
            {
                "failures": list(error.failures),
                "rejected_draws": [d.model_dump(mode="json") for d in error.rejected],
                "requests": [r.model_dump(mode="json") for r in error.requests],
            },
        )
        print(str(error), file=sys.stderr)
        return 1
    write_new(args.output, bank.model_dump(mode="json"))
    print(json.dumps({"requests": len(bank.requests), "rejected_draws": len(bank.rejected_draws),
                      "bank_sha256": canonical_sha(bank.model_dump(mode="json"))}))
    return 0


def materialize(args) -> int:
    bank = TierBRootBank.model_validate_json(args.bank.read_text())
    manifest = materialize_tier_b_configs(
        bank,
        template_capture=args.template_capture,
        expected_template_plan_sha256=args.template_plan_sha256,
        gamedata=args.gamedata,
        expected_gamedata_sha256=args.gamedata_sha256,
        output=args.output,
    )
    print(json.dumps({"configured": len(manifest.episodes)}))
    return 0


def declare(args) -> int:
    bank = TierBRootBank.model_validate_json(args.bank.read_text())
    tier_a = get_root_seal(args.tier_a_ledger, args.tier_a_attempt_id).protocol
    declaration = tier_b_declaration_from_bank(
        attempt_id=args.attempt_id,
        bank=bank,
        manifest_path=args.manifest,
        checkpoint_path=args.checkpoint,
        tier_a_admission_path=args.tier_a_admission,
        tier_a_protocol=tier_a,
        generator_path=WORKSPACE / "src/clasher/rl/readiness_tier_b_policy.py",
        native_attestation_sha256=args.native_attestation_sha256,
        catalog_path=args.catalog,
        calibration_path=args.calibration_receipt,
        historical_registries=tuple(args.historical_registry),
        decks_path=args.decks,
    )
    digest = declare_tier_b_attempt(
        args.ledger, declaration, tier_a_ledger=args.tier_a_ledger
    )
    print(json.dumps({"attempt_id": args.attempt_id, "design_sha256": digest}))
    return 0


def verify_captures(args) -> int:
    from clasher.rl.readiness_tier_b_policy import (
        load_frozen_policy,
        verify_policy_root_capture,
    )

    declaration = get_tier_b_attempt(args.ledger, args.attempt_id)
    policy = load_frozen_policy(Path(declaration.checkpoint_path), decks_path=args.decks)
    if policy.checkpoint_sha256 != declaration.checkpoint_sha256:
        raise ValueError("checkpoint bytes differ from the declaration")
    with _read(args.ledger) as db:
        rows = _captures(db, args.attempt_id)
    summary = []
    for family_id, receipt, _policy, claim in rows:
        if receipt.status == "selected":
            verify_policy_root_capture(policy, Path(claim.output_path))
        summary.append({"family_id": family_id, "status": receipt.status})
    write_new(args.output, {"attempt_id": args.attempt_id, "verified": summary})
    return 0


def seal(args) -> int:
    if file_sha(args.verification) != args.verification_sha256:
        raise ValueError("policy recomputation audit changed")
    audit = json.loads(args.verification.read_text())
    if audit["attempt_id"] != args.attempt_id:
        raise ValueError("audit covers another attempt")
    protocol = build_frozen_tier_b_protocol(args.ledger, attempt_id=args.attempt_id)
    root_seal = seal_tier_b_roots(args.ledger, attempt_id=args.attempt_id, protocol=protocol)
    write_new(args.output, protocol.model_dump(mode="json"))
    print(json.dumps({"protocol_sha256": protocol.sha256, "seal_sha256": root_seal.sha256,
                      "captured": len(protocol.families),
                      "generation_failures": list(protocol.generation_failures)}))
    return 0


def plan(args) -> int:
    declaration = get_tier_b_attempt(args.ledger, args.attempt_id)
    root_seal = get_tier_b_root_seal(args.ledger, args.attempt_id)
    with _read(args.ledger) as db:
        bindings = tuple(
            r.capture_binding
            for _, r, _, _ in _captures(db, args.attempt_id)
            if r.status == "selected" and r.capture_binding is not None
        )
    execution = ExecutionPlan(
        protocol=root_seal.protocol,
        captures=bindings,
        catalog_path=str(args.catalog.resolve()),
        catalog_sha256=file_sha(args.catalog),
        native_attestation_sha256=declaration.native_attestation_sha256,
        source_pins=declaration.source_pins,
        purpose="tier_b_transfer",
    )
    args.output.mkdir(parents=True, exist_ok=False)
    write_new(args.output / "branch-plan.json", execution.model_dump(mode="json"))
    write_new(args.output / "jobs.json", [j.model_dump(mode="json") for j in jobs(execution)])
    print(json.dumps({"jobs": len(jobs(execution)), "roots": len(bindings)}))
    return 0


def evaluate(args) -> int:
    from clasher.rl.readiness_tier_b_probes import probe_report

    reviews = ()
    if args.reviews is not None:
        reviews = tuple(
            MechanismReview.model_validate(row) for row in json.loads(args.reviews.read_text())
        )
    report, _receipt = evaluate_tier_b_attempt(
        args.ledger,
        attempt_id=args.attempt_id,
        calibration_receipt_path=args.calibration_receipt,
        report_path=args.report,
        receipt_path=args.receipt,
        reviews=reviews,
    )
    if report.block_kind == "targeted_probe":
        protocol = get_tier_b_root_seal(args.ledger, args.attempt_id).protocol
        write_new(args.report.with_suffix(".probes.json"),
                  probe_report(protocol, report).model_dump(mode="json"))
    print(json.dumps({"status": report.status, "informative": report.informative_families,
                      "material_failures": report.material_failures,
                      "missing_roots": list(report.missing_roots)}))
    return 0


def main() -> int:
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate-roots")
    g.add_argument("--checkpoint", type=Path, required=True)
    g.add_argument("--decks", type=Path, required=True)
    g.add_argument("--master-seed", type=int, required=True)
    g.add_argument("--block", choices=("representative", "targeted_probe"), required=True)
    g.add_argument("--window-ticks", type=int, default=300)
    g.add_argument("--max-draws", type=int, default=3)
    g.add_argument("--probe-roots-per-kind", type=int, default=4)
    g.add_argument("--output", type=Path, required=True)
    g.set_defaults(run=generate_roots)
    m = sub.add_parser("materialize-configs")
    m.add_argument("--bank", type=Path, required=True)
    m.add_argument("--template-capture", type=Path, required=True)
    m.add_argument("--template-plan-sha256", required=True)
    m.add_argument("--gamedata", type=Path, required=True)
    m.add_argument("--gamedata-sha256", required=True)
    m.add_argument("--output", type=Path, required=True)
    m.set_defaults(run=materialize)
    d = sub.add_parser("declare")
    d.add_argument("--ledger", type=Path, required=True)
    d.add_argument("--attempt-id", required=True)
    d.add_argument("--bank", type=Path, required=True)
    d.add_argument("--manifest", type=Path, required=True)
    d.add_argument("--checkpoint", type=Path, required=True)
    d.add_argument("--decks", type=Path, required=True)
    d.add_argument("--tier-a-ledger", type=Path, required=True)
    d.add_argument("--tier-a-attempt-id", required=True)
    d.add_argument("--tier-a-admission", type=Path, required=True)
    d.add_argument("--native-attestation-sha256", required=True)
    d.add_argument("--catalog", type=Path, required=True)
    d.add_argument("--calibration-receipt", type=Path, required=True)
    d.add_argument("--historical-registry", type=Path, action="append", required=True)
    d.set_defaults(run=declare)
    v = sub.add_parser("verify-captures")
    v.add_argument("--ledger", type=Path, required=True)
    v.add_argument("--attempt-id", required=True)
    v.add_argument("--decks", type=Path, required=True)
    v.add_argument("--output", type=Path, required=True)
    v.set_defaults(run=verify_captures)
    s = sub.add_parser("seal")
    s.add_argument("--ledger", type=Path, required=True)
    s.add_argument("--attempt-id", required=True)
    s.add_argument("--verification", type=Path, required=True)
    s.add_argument("--verification-sha256", required=True)
    s.add_argument("--output", type=Path, required=True)
    s.set_defaults(run=seal)
    p = sub.add_parser("plan")
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--attempt-id", required=True)
    p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.set_defaults(run=plan)
    e = sub.add_parser("evaluate")
    e.add_argument("--ledger", type=Path, required=True)
    e.add_argument("--attempt-id", required=True)
    e.add_argument("--calibration-receipt", type=Path, required=True)
    e.add_argument("--report", type=Path, required=True)
    e.add_argument("--receipt", type=Path, required=True)
    e.add_argument("--reviews", type=Path)
    e.set_defaults(run=evaluate)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
