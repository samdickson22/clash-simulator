"""Constructed scalar development roots, no fitting or native admission claim."""

import hashlib
import json
import random
from pathlib import Path

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.c56_scripted import C56_ADDED_CARDS, CHAMPION_ABILITY_RULE
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from clasher.rl.deck_pool import apply_ordered_deck_to_player
from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS, PublicScriptedOpponent

E = Path(__file__).resolve().parents[1]
ROOT = E.parents[3]


def main():
    builder = ContractV5ObservationBuilder()
    bot = PublicScriptedOpponent(builder, card_scope="c56")
    space = DiscreteTileActionSpace()
    rows = []
    for focal in sorted(SUPPORTED_CARDS | C56_ADDED_CARDS):
        for seat in (0, 1):
            for context in ("idle", "ground_cluster", "air_threat"):
                battle = BattleState(rng=random.Random(20261003 + len(rows)))
                own = list(
                    dict.fromkeys(
                        [
                            focal,
                            "HogRider",
                            "Musketeer",
                            "Skeletons",
                            "Knight",
                            "Cannon",
                            "Zap",
                            "IceSpirit",
                            "Giant",
                        ]
                    )
                )[:8]
                apply_ordered_deck_to_player(battle.players[seat], own)
                for _ in range(90):
                    battle.step()
                battle.players[seat].elixir = 10
                threats = (
                    []
                    if context == "idle"
                    else ["Balloon", "Minions"]
                    if context == "air_threat"
                    else ["Giant", "Musketeer", "Knight"]
                )
                for index, name in enumerate(threats):
                    xy = (3.5 + index, 11.5 + index * 0.5)
                    if seat:
                        xy = (18 - xy[0], 32 - xy[1])
                    battle._spawn_troop(
                        Position(*xy), 1 - seat, battle.card_loader.get_card(name)
                    )
                packet = builder.build_public(battle, seat)
                ranked = bot._ranked_actions(packet, all_plays=True)
                wait = next(d.score for d in ranked if d.action_id == 2304)
                useful = {
                    d.action_id // 576
                    for d in ranked
                    if d.action_id < 2304 and d.score > wait
                }
                choice = ranked[0]
                accepted = True
                if choice.action_id < 2304:
                    decoded = space.decode_action(choice.action_id, seat)
                    name = builder.card_name_for_token_id(
                        int(packet.observation.hand_ids[decoded.slot])
                    )
                    accepted = battle.deploy_card(seat, name, decoded.position)
                rows.append(
                    {
                        "focal": focal,
                        "seat": seat,
                        "context": context,
                        "action": choice.action_id,
                        "non_wait": choice.action_id < 2304,
                        "accepted": bool(accepted),
                        "useful_card_count": len(useful),
                        "focal_useful": 0 in useful,
                    }
                )
    aggregate = lambda rs: {
        "roots": len(rs),
        "non_wait": sum(r["non_wait"] for r in rs),
        "at_least_two_useful_cards": sum(r["useful_card_count"] >= 2 for r in rs),
        "focal_useful": sum(r["focal_useful"] for r in rs),
        "rejected": sum(not r["accepted"] for r in rs),
    }
    report = {
        "role": "constructed scalar development fixtures only; no fitting or native acceptance",
        "champion_ability_rule": CHAMPION_ABILITY_RULE,
        "summary": aggregate(rows),
        "contexts": {
            c: aggregate([r for r in rows if r["context"] == c])
            for c in ("idle", "ground_cluster", "air_threat")
        },
        "per_card": {
            c: aggregate([r for r in rows if r["focal"] == c])
            for c in sorted(SUPPORTED_CARDS | C56_ADDED_CARDS)
        },
        "rows": rows,
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                ROOT / "src/clasher/rl/c56_scripted.py",
                ROOT / "src/clasher/rl/public_scripted_opponent.py",
                Path(__file__),
            ]
        },
    }
    (E / "controller_coverage.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"]))
    if report["summary"]["rejected"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
