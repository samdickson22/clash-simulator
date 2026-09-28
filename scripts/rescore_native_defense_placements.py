"""Re-evaluate fixed native placement captures with the current scalar simulator."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from compare_native_defense_placements import order_sign

from clasher.arena import Position
from clasher.battle import BattleState


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads((args.captures / "results.json").read_text())
    families = []
    for family in baseline["families"]:
        rows = []
        for index, case in enumerate(family["cases"]):
            b = BattleState()
            for _ in range(91):
                b.step()
            towers = {
                e.id: e.hitpoints for e in b.entities.values() if e.player_id == 1
            }
            deployments = [(0, case["attacker"], 3.5, 14.5)]
            if case["placement"] is not None:
                deployments.append((1, case["defender"], *case["placement"]))
            for owner, name, x, y in deployments:
                b.players[owner].hand = [name]
                assert b.deploy_card(owner, name, Position(x, y))
            for _ in range(case["end_tick"] - 91):
                b.step()
            damage = sum(towers.values()) - sum(
                b.entities[i].hitpoints if i in b.entities else 0 for i in towers
            )
            capture_path = (
                args.captures / f"{case['attacker']}-{case['defender']}-{index}.json"
            )
            capture = json.loads(capture_path.read_text())
            initial_ids = {
                o["nativeObjectId"] for o in capture["native_before"]["objects"]
            }
            actor_ids = {
                o["nativeObjectId"]
                for o in capture["native_first"]["objects"]
                if o["owner"] == 0
                and o["nativeObjectId"] not in initial_ids
                and o["hp"] is not None
            }
            native_alive = any(
                o["nativeObjectId"] in actor_ids and o["hp"] is not None and o["hp"] > 0
                for o in capture["native_final"]["objects"]
            )
            scalar_alive = any(
                e.player_id == 0
                and e.card_stats.name == case["attacker"]
                and e.entity_kind == 0
                and e.is_alive
                for e in b.entities.values()
            )
            rows.append(
                {
                    **case,
                    "previous_scalar_tower_damage": case["scalar_tower_damage"],
                    "scalar_tower_damage": damage,
                    "native_attacker_alive": native_alive,
                    "scalar_attacker_alive": scalar_alive,
                }
            )
        pairs = []
        for i, j in itertools.combinations(range(len(rows)), 2):
            native = order_sign(
                rows[i]["native_tower_damage"] - rows[j]["native_tower_damage"]
            )
            scalar = order_sign(
                rows[i]["scalar_tower_damage"] - rows[j]["scalar_tower_damage"]
            )
            pairs.append(
                {
                    "i": i,
                    "j": j,
                    "native_order": native,
                    "scalar_order": scalar,
                    "agrees": native == scalar,
                    "strict_reversal": native * scalar < 0,
                }
            )
        result = {
            "attacker": family["attacker"],
            "defender": family["defender"],
            "cases": rows,
            "pairs": pairs,
            "ordering_disagreements": sum(not p["agrees"] for p in pairs),
            "strict_reversals": sum(p["strict_reversal"] for p in pairs),
        }
        families.append(result)
        print(
            result["attacker"],
            result["defender"],
            [(r["native_tower_damage"], r["scalar_tower_damage"]) for r in rows],
            result["ordering_disagreements"],
        )
    with args.output.open("x") as stream:
        json.dump(
            {
                "scope": "Fixed diagnostic captures; not a training gate pass or official-game parity result.",
                "families": families,
            },
            stream,
            indent=2,
        )
        stream.write("\n")


if __name__ == "__main__":
    main()
