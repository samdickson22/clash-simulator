"""Compare a fixed defensive-placement diagnostic against the offline native engine."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from smoke_reference_battle import request

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader

PLACEMENTS = (
    None,
    (3.5, 18.5),
    (5.5, 18.5),
    (7.5, 19.5),
    (9.5, 20.5),
    (11.5, 21.5),
    (13.5, 18.5),
)


def order_sign(value):
    return (value > 0) - (value < 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=26789)
    parser.add_argument("--horizon", type=int, default=400)
    parser.add_argument(
        "--attacker", action="append", choices=["HogRider", "Giant", "Prince"]
    )
    args = parser.parse_args()
    if args.horizon < 2:
        raise ValueError("horizon must include deployment and later outcomes")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "attestation.json").write_text(
        json.dumps(request(args.port, "attest"), indent=2) + "\n"
    )
    loader = CardDataLoader()
    results = []
    for attacker, defender in itertools.product(
        args.attacker or ["HogRider", "Giant", "Prince"], ["Cannon", "Tesla"]
    ):
        family = []
        for index, placement in enumerate(PLACEMENTS):
            config = json.loads(args.config.read_text())
            cards = [
                "Musketeer",
                "Skeletons",
                attacker,
                defender,
                "IceGolem",
                "IceSpirit",
                "Fireball",
                "Log",
            ]
            ids = {name: loader.get_card(name)._raw_entry["id"] for name in cards}
            for owner in (0, 1):
                config["battle"][f"deck{owner}"]["sp"] = [{"d": ids[n]} for n in cards]
            request(args.port, "configure " + json.dumps(config, separators=(",", ":")))
            request(args.port, "step 70")
            before = request(args.port, "observe")
            actions = []
            deployment = [(0, attacker, 3.5, 14.5)]
            if placement is not None:
                deployment.append((1, defender, *placement))
            for owner, name, x, y in deployment:
                player = next(p for p in before["players"] if p["owner"] == owner)
                card = next(c for c in player["hand"] if c["cardId"] == ids[name])
                actions.extend(
                    [owner, card["handIndex"], round(x * 1000), round(y * 1000)]
                )
            pre = request(
                args.port, f"play 1 21 {len(deployment)} " + " ".join(map(str, actions))
            )
            assert pre["tick"] == 91 and pre["count"] == 6 and not pre["truncated"]
            battle = BattleState()
            for _ in range(91):
                battle.step()
            native_towers = {
                o["nativeObjectId"]: o["hp"] for o in pre["objects"] if o["owner"] == 1
            }
            scalar_towers = {
                e.id: e.hitpoints for e in battle.entities.values() if e.player_id == 1
            }
            assert sorted(native_towers.values()) == sorted(scalar_towers.values())
            for owner, name, x, y in deployment:
                battle.players[owner].hand = [name]
                assert battle.deploy_card(owner, name, Position(x, y)), (
                    attacker,
                    defender,
                    placement,
                )
            request(args.port, "step 1")
            first = request(args.port, "observe")
            battle.step()
            for owner, name, _, _ in deployment:
                bodies = [
                    o
                    for o in first["objects"]
                    if o["owner"] == owner
                    and o.get("cardId") == ids[name]
                    and o["hp"] is not None
                ]
                assert len(bodies) == 1, (
                    "missing or ambiguous native execution",
                    name,
                    bodies,
                )
                body = next(
                    e
                    for e in battle.entities.values()
                    if e.player_id == owner and e.card_stats.name == name
                )
                assert (
                    body.max_hitpoints,
                    round(body.position.x * 1000),
                    round(body.position.y * 1000),
                ) == (bodies[0]["maxHp"], bodies[0]["x"], bodies[0]["y"])
            request(args.port, f"step {args.horizon - 1}")
            final = request(args.port, "observe")
            for _ in range(args.horizon - 1):
                battle.step()
            assert (
                final["tick"] == battle.tick == 91 + args.horizon
                and not final["truncated"]
            )
            native_final = {o["nativeObjectId"]: o for o in final["objects"]}
            native_damage = sum(native_towers.values()) - sum(
                native_final.get(i, {}).get("hp", 0) for i in native_towers
            )
            scalar_damage = sum(scalar_towers.values()) - sum(
                battle.entities[i].hitpoints if i in battle.entities else 0
                for i in scalar_towers
            )
            row = {
                "attacker": attacker,
                "defender": defender,
                "placement": placement,
                "native_tower_damage": native_damage,
                "scalar_tower_damage": scalar_damage,
                "end_tick": final["tick"],
            }
            family.append(row)
            (args.output / f"{attacker}-{defender}-{index}.json").write_text(
                json.dumps(
                    {
                        "config": config,
                        "native_before": pre,
                        "native_first": first,
                        "native_final": final,
                        "result": row,
                    },
                    indent=2,
                )
                + "\n"
            )
        pairs = []
        for i, j in itertools.combinations(range(len(family)), 2):
            nd = family[i]["native_tower_damage"] - family[j]["native_tower_damage"]
            sd = family[i]["scalar_tower_damage"] - family[j]["scalar_tower_damage"]
            pairs.append(
                {
                    "i": i,
                    "j": j,
                    "native_order": order_sign(nd),
                    "scalar_order": order_sign(sd),
                    "agrees": order_sign(nd) == order_sign(sd),
                }
            )
        result = {
            "attacker": attacker,
            "defender": defender,
            "cases": family,
            "pairs": pairs,
            "ordering_disagreements": sum(not p["agrees"] for p in pairs),
        }
        results.append(result)
        (args.output / "results.json").write_text(
            json.dumps(
                {
                    "scope": "Diagnostic only; not a training authorization or official-game parity result. Fixed plans, no learned policy or optimization.",
                    "families": results,
                },
                indent=2,
            )
            + "\n"
        )
        print(
            attacker,
            defender,
            [(r["native_tower_damage"], r["scalar_tower_damage"]) for r in family],
            result["ordering_disagreements"],
            flush=True,
        )


if __name__ == "__main__":
    main()
