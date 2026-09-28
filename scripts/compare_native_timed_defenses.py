"""Collect predeclared timed defensive branches against the offline native engine."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

from smoke_reference_battle import request

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=26789)
    parser.add_argument(
        "--attacker", action="append", choices=["HogRider", "Giant", "Prince"]
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    plan = []
    for attacker, owner in itertools.product(
        args.attacker or ["HogRider", "Giant", "Prince"], [0, 1]
    ):
        plan.append(
            {
                "attacker": attacker,
                "owner": owner,
                "defender": None,
                "position": None,
                "execution_tick": None,
            }
        )
        for defender, position, tick in itertools.product(
            ["Cannon", "Tesla"], [(5.5, 18.5), (7.5, 19.5)], [251, 271, 291]
        ):
            plan.append(
                {
                    "attacker": attacker,
                    "owner": owner,
                    "defender": defender,
                    "position": position,
                    "execution_tick": tick,
                }
            )
    write(
        args.output / "plan.json",
        {"end_tick": 1421, "role": "opened_development", "cases": plan},
    )
    write(args.output / "attestation.json", request(args.port, "attest"))
    loader = CardDataLoader()
    rows = []
    for index, case in enumerate(plan):
        attacker, owner, defender = (case[k] for k in ("attacker", "owner", "defender"))
        names = [
            "Musketeer",
            "Skeletons",
            attacker,
            defender or "Cannon",
            "IceGolem",
            "IceSpirit",
            "Fireball",
            "Log",
        ]
        if owner:
            names[2], names[3] = names[3], names[2]
        ids = {n: loader.get_card(n)._raw_entry["id"] for n in names}
        config = json.loads(args.config.read_text())
        for seat in (0, 1):
            config["battle"][f"deck{seat}"]["sp"] = [{"d": ids[n]} for n in names]
        request(args.port, "configure " + json.dumps(config, separators=(",", ":")))
        request(args.port, "step 200")
        battle = BattleState()
        for _ in range(200):
            battle.step()
        commands = []
        native_ids = {}
        scalar_ids = {}
        frames = []
        pending = None
        before = request(args.port, "observe")
        native_towers = {
            o["nativeObjectId"]: o["hp"]
            for o in sorted(before["objects"], key=lambda o: (o["x"], o["y"]))
            if o["owner"] == 1 - owner
        }
        scalar_towers = {
            e.id: e.hitpoints
            for e in sorted(battle.entities.values(), key=lambda e: (e.position.x, e.position.y))
            if e.player_id == 1 - owner
        }
        assert sorted(native_towers.values()) == sorted(scalar_towers.values())

        def submit(name, seat, xy, *, ids=ids, battle=battle, commands=commands):
            nonlocal pending
            before = request(args.port, "observe")
            player = next(p for p in before["players"] if p["owner"] == seat)
            card = next(c for c in player["hand"] if c["cardId"] == ids[name])
            command = f"play 1 1 1 {seat} {card['handIndex']} {round(xy[0] * 1000)} {round(xy[1] * 1000)}"
            after = request(args.port, command)
            battle.step()
            assert after["tick"] == battle.tick == before["tick"] + 1
            commands.append(
                {
                    "name": name,
                    "owner": seat,
                    "xy": xy,
                    "submitted_tick": before["tick"],
                    "expected_execution_tick": before["tick"] + 22,
                    "before": before,
                    "submission_after": after,
                }
            )
            pending = commands[-1]

        attack_xy = (3.5, 14.5) if owner == 0 else (14.5, 17.5)
        submit(attacker, owner, attack_xy)
        while battle.tick < 1421:
            if defender and battle.tick == case["execution_tick"] - 22:
                assert pending is None
                x, y = case["position"]
                submit(defender, 1 - owner, (18 - x, 32 - y) if owner else (x, y))
                continue
            if pending and battle.tick == pending["expected_execution_tick"] - 1:
                name, seat = pending["name"], pending["owner"]
                battle.players[seat].hand = [name]
                assert battle.deploy_card(seat, name, Position(*pending["xy"]))
            request(args.port, "step 1")
            battle.step()
            capture = request(args.port, "observe-atomic")
            native = capture["ordinary"]
            assert (
                capture["atomic"]
                and not capture["rich"]["truncated"]
                and not native["truncated"]
            )
            assert native["tick"] == battle.tick
            if pending and battle.tick == pending["expected_execution_tick"]:
                name, seat = pending["name"], pending["owner"]
                bodies = [
                    o
                    for o in native["objects"]
                    if o["owner"] == seat
                    and o["cardId"] == ids[name]
                    and o["hp"] is not None
                ]
                assert len(bodies) == 1, (case, pending, bodies)
                body = bodies[0]
                scalar = next(
                    e
                    for e in battle.entities.values()
                    if e.player_id == seat and e.card_stats.name == name
                )
                assert body["maxHp"] == scalar.max_hitpoints
                assert abs(body["x"] - round(scalar.position.x * 1000)) <= 1
                assert abs(body["y"] - round(scalar.position.y * 1000)) <= 1
                player = next(p for p in native["players"] if p["owner"] == seat)
                prior = next(
                    p for p in pending["before"]["players"] if p["owner"] == seat
                )
                cost = next(
                    c["cost"] for c in prior["hand"] if c["cardId"] == ids[name]
                )
                assert cost - 1 < prior["elixir"] - player["elixir"] <= cost
                native_ids[name] = body["nativeObjectId"]
                scalar_ids[name] = scalar.id
                pending["after"] = native
                pending = None
            native_objects = {o["nativeObjectId"]: o for o in native["objects"]}
            rich_objects = {o["nativeObjectId"]: o for o in capture["rich"]["objects"]}
            facts = {}
            for name, identity in native_ids.items():
                n = native_objects.get(identity)
                s = battle.entities.get(scalar_ids[name])
                r = rich_objects.get(identity, {})
                facts[name] = {
                    "native": None
                    if n is None
                    else {k: n[k] for k in ("x", "y", "hp")},
                    "scalar": None
                    if s is None
                    else {
                        "x": round(s.position.x * 1000),
                        "y": round(s.position.y * 1000),
                        "hp": s.hitpoints,
                        "target_id": s.target_id,
                    },
                    "native_target": r.get("targetEntityKey"),
                    "native_target_validated": r.get("targetEntityValidated"),
                }
            nd = [native_objects.get(i, {}).get("hp", 0) for i in native_towers]
            sd = [
                battle.entities[i].hitpoints if i in battle.entities else 0
                for i in scalar_towers
            ]
            frames.append(
                {
                    "tick": battle.tick,
                    "actors": facts,
                    "native_tower_hp": nd,
                    "scalar_tower_hp": sd,
                }
            )
            # Once both attackers are absent, no further actions are scheduled.
            # Complete the fixed horizon without retaining duplicate empty frames.
            if (
                attacker in native_ids
                and pending is None
                and (not defender or defender in native_ids)
                and native_ids[attacker] not in native_objects
                and scalar_ids[attacker] not in battle.entities
            ):
                break
        terminal_tick = battle.tick
        if battle.tick < 1421:
            request(args.port, f"step {1421 - battle.tick}")
            while battle.tick < 1421:
                battle.step()
        final = request(args.port, "observe")
        assert final["tick"] == battle.tick == 1421 and not final["truncated"]
        objects = {o["nativeObjectId"]: o for o in final["objects"]}
        result = dict(
            **case,
            case_index=index,
            native_tower_damage=sum(native_towers.values())
            - sum(objects.get(i, {}).get("hp", 0) for i in native_towers),
            scalar_tower_damage=sum(scalar_towers.values())
            - sum(
                battle.entities[i].hitpoints if i in battle.entities else 0
                for i in scalar_towers
            ),
            native_attacker_alive=native_ids[attacker] in objects,
            scalar_attacker_alive=scalar_ids[attacker] in battle.entities,
            last_traced_tick=terminal_tick,
        )
        path = args.output / f"case-{index:03d}.json"
        write(
            path,
            {
                "config": config,
                "result": result,
                "commands": commands,
                "native_ids": native_ids,
                "scalar_ids": scalar_ids,
                "frames": frames,
                "native_final": final,
            },
        )
        rows.append(
            dict(
                **result,
                capture=path.name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
        write(args.output / "summary.json", rows)
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
