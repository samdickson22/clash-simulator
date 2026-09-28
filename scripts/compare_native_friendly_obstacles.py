"""Capture paired friendly-building navigation controls in both seats."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

from smoke_reference_battle import request

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=26789)
    parser.add_argument(
        "--troop", action="append", choices=["HogRider", "Giant", "Knight"]
    )
    parser.add_argument("--horizon", type=int, default=121)
    args = parser.parse_args()
    if args.horizon < 121:
        raise ValueError("horizon must include the navigation window")
    args.output.mkdir(parents=True, exist_ok=False)
    loader = CardDataLoader()
    plan = [
        {"troop": t, "building": b, "owner": o, "horizon": args.horizon}
        for t, b, o in itertools.product(
            args.troop or ["HogRider", "Giant", "Knight"],
            [None, "Cannon", "Tesla"],
            [0, 1],
        )
    ]
    (args.output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    (args.output / "attestation.json").write_text(
        json.dumps(request(args.port, "attest"), indent=2) + "\n"
    )
    summary = []
    for case in plan:
        troop, building, owner = (case[k] for k in ("troop", "building", "owner"))
        config = json.loads(args.config.read_text())
        names = [
            "Musketeer",
            "Skeletons",
            troop,
            "IceSpirit",
            "IceGolem",
            "Fireball",
            "Log",
            "Archers",
        ]
        if building:
            names[4 if owner == 0 else 3] = building
        ids = {n: loader.get_card(n)._raw_entry["id"] for n in names}
        for seat in (0, 1):
            config["battle"][f"deck{seat}"]["sp"] = [{"d": ids[n]} for n in names]
        request(args.port, "configure " + json.dumps(config, separators=(",", ":")))
        request(args.port, "step 200")
        before = request(args.port, "observe")
        assert before["tick"] == 200 and not before["truncated"]
        player = next(p for p in before["players"] if p["owner"] == owner)
        placements = [(troop, 3.5, 8.5)]
        if building:
            placements.append((building, 3.5, 11.5))
        if owner:
            placements = [(n, 18 - x, 32 - y) for n, x, y in placements]
        actions = []
        for name, x, y in placements:
            card = next(c for c in player["hand"] if c["cardId"] == ids[name])
            actions.extend([owner, card["handIndex"], round(x * 1000), round(y * 1000)])
        pre = request(
            args.port, f"play 1 21 {len(placements)} " + " ".join(map(str, actions))
        )
        assert pre["tick"] == 221 and pre["count"] == 6 and not pre["truncated"]
        battle = BattleState()
        for _ in range(221):
            battle.step()
        for name, x, y in placements:
            battle.players[owner].hand = [name]
            assert battle.deploy_card(owner, name, Position(x, y))
        frames = []
        native_id = None
        scalar_id = None
        sample_ticks = sorted({1, *range(21, 122, 5), args.horizon})
        native_towers = {
            o["nativeObjectId"]: o["hp"]
            for o in pre["objects"]
            if o["owner"] == 1 - owner
        }
        scalar_towers = {
            e.id: e.hitpoints
            for e in battle.entities.values()
            if e.player_id == 1 - owner
        }
        assert sorted(native_towers.values()) == sorted(scalar_towers.values())
        for elapsed in sample_ticks:
            delta = elapsed - (frames[-1]["elapsed"] if frames else 0)
            request(args.port, f"step {delta}")
            for _ in range(delta):
                battle.step()
            native = request(args.port, "observe")
            assert (
                native["tick"] == battle.tick == 221 + elapsed
                and not native["truncated"]
            )
            if native_id is None:
                for name, x, y in placements:
                    bodies = [
                        o
                        for o in native["objects"]
                        if o["owner"] == owner
                        and o["cardId"] == ids[name]
                        and o["hp"] is not None
                    ]
                    assert len(bodies) == 1, (case, name, bodies)
                    scalar = next(
                        e
                        for e in battle.entities.values()
                        if e.player_id == owner and e.card_stats.name == name
                    )
                    assert scalar.max_hitpoints == bodies[0]["maxHp"]
                    assert abs(round(scalar.position.x * 1000) - bodies[0]["x"]) <= 1
                    assert abs(round(scalar.position.y * 1000) - bodies[0]["y"]) <= 1
                    if name == troop:
                        native_id = bodies[0]["nativeObjectId"]
                        scalar_id = scalar.id
            n = next(
                (o for o in native["objects"] if o["nativeObjectId"] == native_id), None
            )
            s = battle.entities.get(scalar_id)
            scalar = (
                None
                if s is None
                else {
                    "x": round(s.position.x * 1000),
                    "y": round(s.position.y * 1000),
                    "hp": s.hitpoints,
                }
            )
            error = (
                math.hypot(n["x"] - scalar["x"], n["y"] - scalar["y"])
                if n and scalar
                else None
            )
            frames.append(
                {
                    "elapsed": elapsed,
                    "native": native,
                    "scalar_troop": scalar,
                    "position_error_units": error,
                }
            )
        final_objects = {
            o["nativeObjectId"]: o for o in frames[-1]["native"]["objects"]
        }
        result = dict(
            **case,
            native_tower_damage=sum(native_towers.values())
            - sum(final_objects.get(i, {}).get("hp", 0) for i in native_towers),
            scalar_tower_damage=sum(scalar_towers.values())
            - sum(
                battle.entities[i].hitpoints if i in battle.entities else 0
                for i in scalar_towers
            ),
            native_troop_alive=native_id in final_objects,
            scalar_troop_alive=scalar_id in battle.entities,
            end_tick=battle.tick,
            max_position_error_units=max(
                f["position_error_units"]
                for f in frames
                if f["position_error_units"] is not None
            ),
            hp_mismatches=sum(
                next(
                    (
                        o["hp"]
                        for o in f["native"]["objects"]
                        if o["nativeObjectId"] == native_id
                    ),
                    None,
                )
                != (f["scalar_troop"] or {}).get("hp")
                for f in frames
            ),
        )
        path = args.output / f"{troop}-{building or 'none'}-{owner}.json"
        path.write_text(
            json.dumps(
                {
                    "config": config,
                    "before": pre,
                    "native_troop_id": native_id,
                    "placements": placements,
                    "frames": frames,
                    "result": result,
                },
                indent=2,
            )
            + "\n"
        )
        summary.append(
            dict(
                **result,
                capture=path.name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
