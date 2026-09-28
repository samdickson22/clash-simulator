"""Require the production parallel preflight and exact array parity before collection."""

import json
import shutil
from pathlib import Path

from parallel_engine import compare_arrays, initialize
from parallel_io import publish_json
from parallel_protocol import (
    BASE_PLAN,
    WORKERS,
    build_plan,
    source_fingerprint,
    validate_plan,
)
from probe_worker import sha
from publish_plan import audit_preflight


def main():
    root = Path(__file__).resolve().parents[2]
    plan_path = root / "reports/hog26_training_expansion_parallel_frozen_plan_20260913.json"
    pin_path = root / "reports/hog26_training_expansion_parallel_preflight_pin_20260913.json"
    if plan_path.exists() or pin_path.exists():
        raise ValueError("preserve existing parallel collection authority")
    if shutil.disk_usage(root).free < 20 * 1024**3:
        raise ValueError("parallel expansion requires at least 20 GiB free")
    original = json.loads((root / BASE_PLAN).read_text())
    engine = initialize(root, original["source_authority"]["contract"]["canonical_names"])
    authority = source_fingerprint(root, resource_paths={
        "checkpoint": root / "checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt",
        "card_data": Path(engine.builder.loader.data_file)}, vocabulary_sha256=engine.vocabulary.sha256,
        card_definitions=engine.builder.loader.load_card_definitions())
    draft = build_plan(authority=authority)
    directory = root / "datasets/derived/hog26_training_expansion_parallel_preflight_20260913"
    pin = audit_preflight(directory, authority, draft)
    complete = json.loads((directory / "complete.json").read_text())
    if complete["parallel_workers"] != WORKERS or complete["parity_verified_games"] != 12:
        raise ValueError("production parallel preflight proof differs")
    for row in complete["games"]:
        compare_arrays(root / "datasets/derived/hog26_training_expansion_preflight_20260913" / row["path"], directory / row["path"])
    pin["parallel_checks"] = {"workers": WORKERS, "all_twelve_reference_arrays_exact": True,
                              "provenance_metadata_only_difference": True}
    plan = build_plan(authority=authority, preflight=pin)
    validate_plan(plan, authority, preflight=pin)
    publish_json(pin_path, pin)
    publish_json(plan_path, plan)
    print(json.dumps({"status": "parallel-collection-frozen", "games": 4608, "workers": WORKERS,
                      "plan_sha256": sha(plan_path), "preflight_pin_sha256": sha(pin_path)}), flush=True)


if __name__ == "__main__":
    main()
