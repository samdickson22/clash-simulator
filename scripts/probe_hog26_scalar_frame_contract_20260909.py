"""Trace actual BattleState.step dispatch without replacing its phase scheduler."""

import hashlib
import json
from pathlib import Path

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.dynamic_spells import create_spell_from_json


def trace(card):
    battle = BattleState()
    battle.rng.seed(1279011)
    target = next(e for e in battle.entities.values()
                  if e.position == Position(3.5, 25.5))
    before = set(battle.entities)
    spell = create_spell_from_json(battle.card_loader.get_card(card)._raw_entry,
                                   battle.card_loader.load_card_definitions())
    assert spell.cast(battle, 0, Position(3.5, 25.5))
    objects = [e for key, e in battle.entities.items() if key not in before]
    events = []

    def instrument(entity, method):
        original = getattr(entity, method)

        def wrapped(*args, **kwargs):
            record = {"tick": battle.tick, "entity_id": entity.id, "method": method,
                      "deferred_projectile_mode": battle._defer_projectile_impacts,
                      "target_hp_before": target.hitpoints}
            events.append(record)
            result = original(*args, **kwargs)
            record["target_hp_after"] = target.hitpoints
            return result

        setattr(entity, method, wrapped)

    for method in ("update_combat_component", "update_movement_component",
                   "update_hitpoint_component", "update_buff_component",
                   "tick_character_object_phase"):
        instrument(target, method)
    for entity in objects:
        instrument(entity, "update")
        if hasattr(entity, "_resolve_impact"):
            instrument(entity, "_resolve_impact")
    for _ in range(30):
        battle.step()
    damage = [e for e in events if e["target_hp_after"] != e["target_hp_before"]]
    return {"card": card, "initial_hp": 3052, "final_hp": target.hitpoints,
            "damage_events": damage,
            "tick25_dispatch": [e for e in events if e["tick"] == 25],
            "all_impact_resolution_events": [e for e in events if e["method"] == "_resolve_impact"]}


def main():
    root = Path(__file__).resolve().parents[1]
    sources = ["src/clasher/battle.py", "src/clasher/entities.py", "src/clasher/spells.py",
               Path(__file__).relative_to(root).as_posix()]
    report = {"scope": "Actual BattleState.step dispatch after direct spell.cast; "
                       "no scheduler replacement or deferred-mode override. "
                       "Does not certify action ingress timing or native parity.",
              "source_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest()
                                for p in sources},
              "cases": [trace("Arrows"), trace("Poison")]}
    path = root / "reports/hog26_scalar_frame_contract_20260909.json"
    with path.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    for case in report["cases"]:
        print(json.dumps({"card": case["card"], "final_hp": case["final_hp"],
                          "damage": [{"tick": e["tick"], "method": e["method"],
                                      "deferred": e["deferred_projectile_mode"]}
                                     for e in case["damage_events"]]}))


if __name__ == "__main__":
    main()
