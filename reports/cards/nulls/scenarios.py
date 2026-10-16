#!/usr/bin/env python3
"""Offline, name-only native scenario declarations. No game tables or socket I/O."""
from __future__ import annotations

import hashlib
import json

VERSION = {"client": "15.535.13", "content": "15.535.86"}
START = 100
END = 600  # Includes warmup: the entire native battle is at most 30 seconds.
FILL = "Knight Archer Giant Minions Musketeer BabyDragon Balloon Wizard Zap Skeletons".split()
A = "GoblinCage SpearGoblins Bomber Tombstone Barbarians BattleRam MegaMinion BarbarianHut Mortar DartBarrell Witch Pekka SkeletonWarriors SkeletonDragons".split()
B = "RoyalRecruits ThreeMusketeers GiantSkeleton SkeletonBalloon Hunter MiniSparkys RoyalGiant BattleHealer GoblinGiant GiantBuffer Freeze Snowball Vines Rage DarkMagic GoblinCurse Clone Graveyard Heal".split()
BUILDINGS = {"GoblinCage", "Tombstone", "BarbarianHut", "Mortar"}
SPELLS = {"Freeze", "Snowball", "Vines", "Rage", "DarkMagic", "GoblinCurse", "Clone", "Graveyard"}
ALIASES = {"DartBarrell": "FlyingMachine", "Pekka": "PEKKA", "SkeletonWarriors": "Guards",
           "MiniSparkys": "Zappies", "GiantBuffer": "RuneGiant", "DarkMagic": "Void", "Heal": "HealSpirit"}
RESIDUALS = {("GoblinCage", "giant"), ("Tombstone", "hog"), ("Barbarians", "minions"),
             ("BattleRam", "minions"), ("Witch", "alone")}
QUESTIONS = {
    "GoblinCage": "Cage death -> Brawler birth/deploy end -> first nonlethal hit; separate deploy and load clocks",
    "Tombstone": "First periodic wave and death wave count; birth-tick displacement and target of death Skeletons",
    "Barbarians": "Formation/deploy stagger; Minion -> Barbarian -> Princess target/impact ordering",
    "BattleRam": "Charge/impact -> death -> Barbarian birth/deploy; later Minion/Princess cascade",
    "Witch": "Wave count, simultaneous birth and same-tick first step; compare complete wave multisets",
    "SpearGoblins": "Formation/stagger, projectile launch -> impact; hit/load speed values are versioned stats",
    "Bomber": "Ground-only targeting, projectile/splash ordering; damage is a versioned stat",
    "MegaMinion": "Air movement, ground/air target acquisition and first-hit ordering control",
    "BarbarianHut": "First wave at deploy end; subsequent short-prefix waves; death release",
    "Mortar": "Keep/acquire/drop inside minimum range; launch offset -> impact; hit/load values are stats",
    "DartBarrell": "Flying body immune to Knight; projectile launch offset and air targeting",
    "Pekka": "Slow first attack/retarget control; nonlethal hits before HP-dependent divergence",
    "SkeletonWarriors": "Formation and deploy stagger; shield break absorbs excess without HP spill",
    "SkeletonDragons": "Two-body formation, splash/air targeting and projectile launch offset",
    "RoyalRecruits": "Six-body formation, lane split, stagger, shield-break ordering",
    "ThreeMusketeers": "Three-body formation/stagger and individual target/shot ordering",
    "GiantSkeleton": "Combat death -> bomb birth/arming -> explosion; retained target and radius",
    "SkeletonBalloon": "Air-only parent -> death impact -> ground Skeleton count, geometry and deploy",
    "Hunter": "Pellet count/spread and near/far projectile targeting; count uncapped nonlethal contacts",
    "MiniSparkys": "Three deploy clocks, stun application, pending shot and target reacquisition",
    "RoyalGiant": "Building-only target selection, ranged launch and retarget ordering",
    "BattleHealer": "Attack-linked/passive heal trigger and target eligibility on naturally wounded allies",
    "GoblinGiant": "Passenger shots during travel; parent death -> passenger release and first step",
    "GiantBuffer": "Friendly enchantment selection and every-third-hit trigger; support case required",
    "Freeze": "Cast/impact -> freeze start/expiry -> reacquire; duration is versioned, pause ordering is mechanics",
    "Snowball": "Impact -> knockback/slow; geometry and displacement order; no synthetic zero-speed target",
    "Vines": "Target selection/cap, snare entry/expiry and DoT cadence; separate duration/radius stats",
    "Rage": "Buff entry/refresh/exit on a moving friendly push; haste application order",
    "DarkMagic": "Void strike clock, target-count tier selection and area membership; damage values are stats",
    "GoblinCurse": "DoT + amplification order, kill ownership and converted Goblin birth/position",
    "Clone": "Clone offset/parent mapping, cloned shield and death releases; count/HP flags, not damage totals",
    "Graveyard": "First spawn, ready delay and cadence; compare seeded repeat distributions, not PRNG coordinates",
    "Heal": "Heal Spirit jump -> impact -> heal eligibility/order; no spell-only interpretation of Heal",
}


def command(side, card, tile, relative=0):
    return {"side": side, "card": card, "tile": list(tile), "command_tick": START + relative,
            "schedule_tick": START + relative + 1}


def script(card, variant):
    if variant == "alone":
        return [command(0, card, (7.5, 10.5) if card in BUILDINGS else (3.5, 14.5))]
    if variant in ("knight", "minions", "hog", "giant"):
        opponent = {"knight": "Knight", "minions": "Minions", "hog": "HogRider", "giant": "Giant"}[variant]
        return [command(0, card, (7.5, 12.5) if card in BUILDINGS else (3.5, 14.5)),
                command(1, opponent, (3.5, 17.5))]
    if variant == "tower":
        return [command(0, card, (3.5, 25.5))]
    if variant == "cluster":
        return [command(1, "Knight", (3.5, 18.5)), command(1, "SkeletonArmy", (5.5, 18.5), 1),
                command(1, "Minions", (3.5, 20.5), 2), command(0, card, (3.5, 18.5), 30)]
    if variant == "support":
        return [command(0, "Giant", (3.5, 14.5)), command(1, "Knight", (3.5, 17.5)),
                command(0, card, (3.5, 14.5), 35)]
    if variant == "wounded_support":
        return [command(0, "Giant", (3.5, 14.5)), command(1, "Knight", (3.5, 17.5)),
                command(0, card, (4.5, 13.5), 80)]
    if variant == "enchant_support":
        return [command(0, card, (3.5, 12.5)), command(0, "Archer", (3.5, 13.5), 1),
                command(0, "Skeletons", (4.5, 13.5), 2), command(1, "Giant", (3.5, 17.5))]
    if variant == "hunter_far":
        return [command(0, card, (3.5, 12.5)), command(1, "Giant", (3.5, 17.5))]
    if variant == "shield_break":
        return [command(1, card, (14.5, 21.5)), command(0, "Fireball", (14.5, 21.0))]
    raise ValueError(variant)


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def scenarios():
    rows = []
    for card in A + B:
        variants = ["alone", "hog", "giant"] if card in BUILDINGS else (
            ["tower", "cluster", "support"] if card in SPELLS else ["alone", "knight", "minions"])
        if card in {"BattleHealer", "Heal"}:
            variants += ["wounded_support"]
        if card == "GiantBuffer":
            variants += ["enchant_support"]
        if card == "Hunter":
            variants += ["hunter_far"]
        if card in {"SkeletonWarriors", "RoyalRecruits"}:
            variants += ["shield_break"]
        for variant in variants:
            commands = script(card, variant)
            # Native examples start at six elixir, whereas the old paired
            # harness sets ten artificially. Let expensive/support casts refill
            # naturally. Keep all five residual scripts at their original tick.
            start = 300 if variant in {"cluster", "support", "wounded_support", "enchant_support"} else (
                220 if card == "ThreeMusketeers" else START)
            for c in commands:
                c["command_tick"] += start - START
                c["schedule_tick"] += start - START
            decks = [list(dict.fromkeys([c["card"] for c in commands if c["side"] == s] + FILL))[:8]
                     for s in (0, 1)]
            replay = {"decks": decks, "commands": commands, "start_tick": start, "end_tick": END,
                      "level": 11, "king_level": 11, "forms": "base", "tower": "PrincessTower"}
            row = {"id": f"{card}.{variant}", "card": card, "display_name": ALIASES.get(card, card),
                   "variant": variant, "priority": 0 if (card, variant) in RESIDUALS else 1 if card in A else 2,
                   "native_version": dict(VERSION), "question": QUESTIONS[card],
                   "script": replay, "script_sha256": signature(replay)}
            rows.append(row)
    control = {"id": "Wizard.minions.control", "card": "Wizard", "display_name": "Wizard",
               "variant": "minions", "priority": 0, "native_version": dict(VERSION),
               "question": "C56 Minions/Princess cascade control; no C56 coverage expansion claim"}
    commands = script("Wizard", "minions")
    control["script"] = {"decks": [list(dict.fromkeys(["Wizard"] + FILL))[:8],
                                   list(dict.fromkeys(["Minions"] + FILL))[:8]],
                         "commands": commands, "start_tick": START, "end_tick": END,
                         "level": 11, "king_level": 11, "forms": "base", "tower": "PrincessTower"}
    control["script_sha256"] = signature(control["script"])
    rows.append(control)
    return sorted(rows, key=lambda r: (r["priority"], r["id"]))


if __name__ == "__main__":
    print(json.dumps({"schema": "cards.nulls.scenarios.v1", "scenarios": scenarios()}, indent=2))
