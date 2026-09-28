"""Recompute captured timed branches without changing native evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from clasher.arena import Position
from clasher.battle import BattleState


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    rows = []
    for root in args.captures:
        for path in sorted(root.glob("case-*.json")):
            data = json.loads(path.read_text())
            battle = BattleState()
            commands = {c["expected_execution_tick"] - 1: c for c in data["commands"]}
            owner = data["result"]["owner"]
            towers = {
                e.id: e.hitpoints
                for e in battle.entities.values()
                if e.player_id == 1 - owner
            }
            for _ in range(1421):
                command = commands.get(battle.tick)
                if command:
                    battle.players[command["owner"]].hand = [command["name"]]
                    assert battle.deploy_card(
                        command["owner"], command["name"], Position(*command["xy"])
                    )
                battle.step()
            damage = sum(towers.values()) - sum(
                battle.entities[i].hitpoints if i in battle.entities else 0
                for i in towers
            )
            rows.append(
                {
                    "capture": str(path),
                    "native_damage": data["result"]["native_tower_damage"],
                    "scalar_damage": damage,
                    "attacker_alive": any(
                        e.player_id == owner
                        and e.card_stats
                        and e.card_stats.name == data["result"]["attacker"]
                        for e in battle.entities.values()
                    ),
                }
            )
    with args.output.open("x") as output:
        json.dump(rows, output, indent=2)
        output.write("\n")
    print(
        json.dumps(
            {
                "cases": len(rows),
                "mismatches": [
                    r
                    for r in rows
                    if r["native_damage"] != r["scalar_damage"] or r["attacker_alive"]
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
