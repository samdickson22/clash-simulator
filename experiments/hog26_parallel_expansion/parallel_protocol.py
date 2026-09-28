"""Same complete-game schedule, with separately pinned parallel execution."""

import json
from pathlib import Path

from expansion_protocol import build_pilot_plan as sequential_plan
from expansion_protocol import preflight_schedules
from expansion_protocol import source_fingerprint as sequential_fingerprint
from probe_worker import sha

from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata
from scripts.hog26_scalar_openings import digest
from scripts.hog26_scalar_pilot_protocol import source_fingerprint as base_fingerprint

WORKERS = 8
BASE_PLAN = "reports/hog26_training_expansion_frozen_plan_20260913.json"


def source_fingerprint(root, *, resource_paths, vocabulary_sha256, card_definitions):
    root = Path(root)
    base = sequential_fingerprint(root, resource_paths=resource_paths,
                                  vocabulary_sha256=vocabulary_sha256, card_definitions=card_definitions)
    resources = {key: value["path"] for key, value in base["resources"].items()}
    for relative in (BASE_PLAN, "reports/hog26_parallel_collection_probe_20260913/complete.json",
                     "reports/hog26_parallel_collection_probe8_20260913/complete.json",
                     "reports/hog26_parallel_collection_probe8_20260913/plan.json",
                     "reports/hog26_training_expansion_preflight_pin_20260913.json"):
        resources[relative] = root / relative
    for directory in ("hog26_parallel_expansion", "hog26_parallel_collection_probe", "hog26_parallel_collection_probe8"):
        for path in (root / "experiments" / directory).glob("*.py"):
            resources[str(path.relative_to(root))] = path
    return base_fingerprint(root, resource_paths=resources, vocabulary_sha256=vocabulary_sha256, card_definitions=card_definitions)


def build_plan(*, authority, preflight=None):
    result = sequential_plan(authority=authority, preflight=preflight)
    original = json.loads(Path(authority["resources"][BASE_PLAN]["path"]).read_text())
    proof = json.loads(Path(authority["resources"]["reports/hog26_parallel_collection_probe8_20260913/complete.json"]["path"]).read_text())
    if (proof["status"] != "parallel-preflight-parity-complete" or proof["games"] != 12
            or proof["workers"] != WORKERS or not proof["all_arrays_exact_except_provenance_metadata"]):
        raise ValueError("exact eight-process preflight replay proof required")
    probe_plan_path = Path(authority["resources"]["reports/hog26_parallel_collection_probe8_20260913/plan.json"]["path"])
    probe_plan = json.loads(probe_plan_path.read_text())
    if sha(probe_plan_path) != proof["plan_sha256"] or any(
            sha(value["path"]) != value["sha256"] for value in probe_plan["source_authority"]["resources"].values()):
        raise ValueError("parallel replay evidence source changed")
    if result["schedules"] != original["schedules"] or result["requirements"] != original["requirements"]:
        raise ValueError("parallel execution changed the declared population or gates")
    result["parallel_execution"] = {"workers": WORKERS, "process_lifetime": "one complete game",
                                    "publication": "validated temporary archive linked atomically to final name",
                                    "collection_order": "results published in original schedule order"}
    result["execution_scope"] = "Same full4608-game schedule; sequential partial files are preserved separately, never selected by outcome."
    result["before_fitting"] = "Require complete combined audit, retired sequential-prefix array parity, and separate memory/source readiness."
    return result


def validate_plan(plan, authority, *, preflight=None):
    if plan.get("source_authority") != authority or plan != build_plan(authority=authority, preflight=preflight):
        raise ValueError("parallel expansion differs from its frozen authority")


def cases_for(plan, mode):
    if mode not in {"preflight", "collect"}:
        raise ValueError("unknown collection mode")
    schedules = preflight_schedules(plan) if mode == "preflight" else plan["schedules"]
    result = []
    for index, schedule in enumerate(schedules):
        for scenario in audit_scalar_opening_metadata(schedule["metadata"], expected_authority=schedule["external_authority"]):
            for seat in schedule["learner_seats"]:
                result.append({"name": f"game-{index:03d}-{scenario.ordinal:03d}-{seat}.npz",
                               "schedule_index": index, "ordinal": scenario.ordinal, "seat": seat})
    if len(result) != (12 if mode == "preflight" else 4608) or len({row["name"] for row in result}) != len(result):
        raise ValueError("parallel case quota differs")
    return schedules, result


def case_at(plan, mode, index):
    if mode not in {"preflight", "collect"} or not 0 <= index < (12 if mode == "preflight" else 4608):
        raise ValueError("parallel case index outside fixed schedule")
    schedules = preflight_schedules(plan) if mode == "preflight" else plan["schedules"]
    per_schedule = 2 if mode == "preflight" else 24
    schedule_index, offset = divmod(index, per_schedule)
    schedule = schedules[schedule_index]
    if len(schedule["learner_seats"]) != 2:
        raise ValueError("parallel schedule needs both learner seats")
    ordinal, seat_index = divmod(offset, 2)
    seat = schedule["learner_seats"][seat_index]
    return {"name": f"game-{schedule_index:03d}-{ordinal:03d}-{seat}.npz", "schedule_index": schedule_index,
            "ordinal": ordinal, "seat": seat, "schedule": schedule}


def expected_metadata(engine, plan, case, mode):
    schedule = case["schedule"]
    scenario = audit_scalar_opening_metadata(schedule["metadata"], expected_authority=schedule["external_authority"])[case["ordinal"]]
    return {"schema": "clasher.scalar-pilot-game-metadata.v1", "mode": mode,
            "source_authority_sha256": digest(plan["source_authority"]), "plan_sha256": digest(plan),
            "opening_metadata": schedule["metadata"], "opening_authority": schedule["external_authority"],
            "scenario_id": scenario.scenario_id, "cluster_id": scenario.cluster_id,
            "ordinal": scenario.ordinal, "learner_seat": case["seat"], "family_id": schedule["family_id"],
            "style": schedule["external_authority"]["opponent_style"], "outcome_token_names": list(engine.outcome_tokens),
            "policy_token_names": list(engine.vocabulary.token_names), "mask_semantics_digest": engine.mask_provider.semantics_digest,
            "retention": "all predecision learner rows through first actual terminal; no filtering by success/outcome"}
