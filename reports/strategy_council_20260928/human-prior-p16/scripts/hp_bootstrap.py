"""Bind drivers to the frozen pilot runtime and load the new research modules.

The engine, observation builder, mask builder and model come from the frozen
pilot runtime (CLASHER_ROOT / first PYTHONPATH entry). The new modules are not
part of that snapshot (it must stay byte-identical), so they are loaded by file
path from the main tree under their package names.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPO = HERE.parents[3]
COUNCIL = REPO / "reports/strategy_council_20260928"
RUNTIME = COUNCIL / "m0/runtime-snapshots/pilot-runtime-v4"
SCAN = COUNCIL / "m0/human-prior-scan"
TRAINING_DECKS = COUNCIL / "m0/data/roles_v2/training.json"
DEVELOPMENT_DECKS = COUNCIL / "m0/data/roles_v2/development.json"
HOG26_DECKS = COUNCIL / "pilot/hog26-deployment.json"
NEW_MODULES = ("human_replay_demonstrations", "human_replay_bc")


def bind_runtime() -> None:
    if os.environ.get("CLASHER_ROOT") != str(RUNTIME):
        raise SystemExit(f"run with CLASHER_ROOT={RUNTIME} PYTHONPATH={RUNTIME}/src")
    import clasher

    if Path(clasher.__file__).resolve().parents[2] != RUNTIME.resolve():
        raise SystemExit("clasher was not imported from the frozen pilot runtime")


def load_new_module(name: str):
    bind_runtime()
    qualified = f"clasher.rl.{name}"
    if qualified in sys.modules:
        return sys.modules[qualified]
    for dependency in NEW_MODULES[:NEW_MODULES.index(name)]:
        load_new_module(dependency)
    path = REPO / "src/clasher/rl" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(qualified, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


def slug_map() -> dict[str, str]:
    sys.path.insert(0, str(SCAN))
    from card_map import SLUG_TO_GAMEDATA

    return dict(SLUG_TO_GAMEDATA)


def pilot_builder():
    """The pilot's observation builder (council_warmstart.run_script_warmstart)."""
    bind_runtime()
    from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS
    from clasher.rl.structured_obs import StructuredObservationBuilder

    return StructuredObservationBuilder(
        decks_path=TRAINING_DECKS, card_vocab=sorted(SUPPORTED_CARDS), max_entities=128,
        canonical_perspective=True, canonical_lane_globals=True, public_history_slots=4,
        public_seen_card_slots=8, card_semantics_version=4, public_entity_levels=True,
        public_hand_levels=True)


def read_payloads(shard: int):
    import gzip

    with gzip.open(OUT / "data/payloads" / f"shard-{shard:03d}.jsonl.gz", "rt") as stream:
        for line in stream:
            yield json.loads(line)
