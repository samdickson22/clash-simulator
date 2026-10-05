"""Write fixed, unexecuted B1-B4 development probes in nm_lib command format."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLES = {
    "B1": [
        "BarbLog",
        "Arrows",
        "Tornado",
        "ElectroSpirit",
        "Lightning",
        "Poison",
        "Rocket",
        "Earthquake",
        "RoyalDelivery",
    ],
    "B2": [
        "BabyDragon",
        "Minions",
        "Bats",
        "MinionHorde",
        "Balloon",
        "Wizard",
        "Valkyrie",
        "Princess",
        "Firecracker",
        "BlowdartGoblin",
    ],
    "B3": [
        "AngryBarbarians",
        "Berserker",
        "MiniPekka",
        "SkeletonArmy",
        "GoblinGang",
        "Rascals",
        "Golem",
        "RoyalHogs",
        "Wallbreakers",
        "FireSpirits",
        "Ghost",
    ],
    "B4": [
        "FirespiritHut",
        "GoblinHut",
        "InfernoTower",
        "Xbow",
        "BombTower",
        "Miner",
        "GoblinBarrel",
        "MightyMiner",
        "Goblinstein",
        "ArcherQueen",
    ],
}
FILL = [
    "Knight",
    "Archers",
    "Giant",
    "Skeletons",
    "Zap",
    "Cannon",
    "Musketeer",
    "IceSpirit",
]


def deck(cards):
    return (cards + [n for n in FILL if n not in cards])[:8]


def cmd(tick, owner, card, xy):
    return {"tick": tick, "owner": owner, "card": card, "xy": xy}


def scenario(key, bundle, own, opponent, commands, measure, end=700, variants=None):
    return {
        "id": key,
        "bundle": bundle,
        "decks": [deck(own), deck(opponent)],
        "need": [own, opponent],
        "seed_start": 1610030001,
        "seed_count": 200,
        "end_tick": end,
        "measure": measure,
        "variants": variants or {"base": commands},
    }


out = []
for bundle, cards in BUNDLES.items():
    for card in cards:
        opponent = "Knight"
        ownxy = (3.5, 14.5)
        enemyxy = (3.5, 17.5)
        cast = 250
        if card in [
            "Minions",
            "Bats",
            "MinionHorde",
            "BabyDragon",
            "Wizard",
            "Princess",
            "Firecracker",
            "BlowdartGoblin",
        ]:
            opponent = "Minions"
        if card in ["Balloon", "Golem", "RoyalHogs", "Wallbreakers", "InfernoTower"]:
            opponent = "Giant"
        if card in ["GoblinHut", "BombTower", "InfernoTower", "Xbow"]:
            ownxy = (7.5, 12.5)
            enemyxy = (7.5, 17.5)
        if card == "FirespiritHut":
            ownxy = (3.5, 4.5)
        if card in ["Miner", "GoblinBarrel"]:
            ownxy = (2.5, 23.5)
        if card in [
            "BarbLog",
            "Arrows",
            "Lightning",
            "Poison",
            "Rocket",
            "RoyalDelivery",
        ]:
            cast = 290
            ownxy = (3.5, 14.5)
        if card == "Earthquake":
            opponent = "Cannon"
            enemyxy = (3.5, 19.5)
            ownxy = enemyxy
            cast = 290
        commands = [cmd(250, 1, opponent, enemyxy), cmd(cast, 0, card, ownxy)]
        measure = "Record births, positions, HP deltas, hit ticks, retargets, and death payloads at each 50 ms tick."
        if card in ["MightyMiner", "Goblinstein", "ArcherQueen"]:
            commands.append({"tick": 330, "owner": 0, "ability": card})
            measure += " Record ability acceptance, elixir debit, cast/trigger, effect geometry and expiry."
        if card == "Tornado":
            # Spell belongs to defender; friendly King cannot be damaged by it.
            # Compare no pull, pull, and direct-damage wake control. A Hog hit
            # before the first King shot distinguishes damage wake from proximity.
            base = [cmd(250, 1, "HogRider", (3.5, 17.5))]
            variants = {
                "no_pull": base,
                "pull": base + [cmd(370, 0, "Tornado", (7.5, 5.5))],
                "damage_wake_control": base + [cmd(350, 1, "Zap", (9.0, 3.0))],
            }
            out.append(
                scenario(
                    "B1_tornado_king",
                    "B1",
                    ["Tornado"],
                    ["HogRider", "Zap"],
                    [],
                    "King HP-loss tick vs first target/shot; Hog xy and target; both Princess survival. Proximity alone is NOT presumed to activate King.",
                    variants=variants,
                )
            )
            continue
        out.append(
            scenario(f"{bundle}_{card}", bundle, [card], [opponent], commands, measure)
        )
# Isolate production from combat, then compare an approaching threat.
for card in ["FirespiritHut", "GoblinHut"]:
    base = [cmd(250, 0, card, (7.5, 10.5))]
    out.append(
        scenario(
            f"B4_{card}_production",
            "B4",
            [card],
            ["Knight"],
            [],
            "First child birth relative to parent deployment, cadence, child deploy duration/offset, wake/sleep, parent movement.",
            end=1000,
            variants={
                "alone": base,
                "approach": base + [cmd(350, 1, "Knight", (7.5, 17.5))],
            },
        )
    )
# Multi-target geometry and air/ground splash contexts supplement single-card probes.
out += [
    scenario(
        "B1_lightning_selection",
        "B1",
        ["Lightning"],
        ["Knight", "Musketeer", "Cannon"],
        [
            cmd(250, 1, "Cannon", (7.5, 19.5)),
            cmd(250, 1, "Knight", (7.5, 18.5)),
            cmd(330, 1, "Musketeer", (9.5, 18.5)),
            cmd(360, 0, "Lightning", (8.5, 18.5)),
        ],
        "Highest-HP order, strike travel times and stun. Shield-order comparison remains a follow-up.",
    ),
    scenario(
        "B3_spirit_swarm",
        "B3",
        ["FireSpirits"],
        ["SkeletonArmy"],
        [
            cmd(250, 1, "SkeletonArmy", (3.5, 17.5)),
            cmd(270, 0, "FireSpirits", (3.5, 14.5)),
        ],
        "One spirit self-removal and one splash; survivor positions and HP.",
    ),
    scenario(
        "B3_hogs_split",
        "B3",
        ["RoyalHogs"],
        ["Cannon"],
        [cmd(250, 0, "RoyalHogs", (8.5, 10.5)), cmd(290, 1, "Cannon", (7.5, 20.5))],
        "Four deployment offsets/staggers, two-lane split and building pull.",
    ),
]
for spell in ("Arrows", "Rocket"):
    out.append(
        scenario(
            f"B1_{spell}_edge",
            "B1",
            [spell],
            ["Cannon", "Knight"],
            [],
            "Damage waves and actual target-to-impact distance on either side of the radius boundary; moving Knight trajectory retained.",
            variants={
                label: [
                    cmd(250, 1, "Cannon", (3.5, 19.5)),
                    cmd(250, 1, "Knight", (5.5, 19.5)),
                    cmd(300, 0, spell, (x, 19.5)),
                ]
                for label, x in (
                    ("near", 5.5 if spell == "Rocket" else 8.5),
                    ("far", 6.5 if spell == "Rocket" else 9.5),
                )
            },
        )
    )
out += [
    scenario(
        "B2_balloon_death",
        "B2",
        ["Balloon"],
        ["Musketeer", "Minions"],
        [
            cmd(250, 0, "Balloon", (3.5, 14.5)),
            cmd(250, 1, "Musketeer", (3.5, 20.5)),
            cmd(290, 1, "Minions", (3.5, 17.5)),
        ],
        "Balloon death location, 3 s bomb fuse, air/ground overlap and damage at explosion.",
    ),
    scenario(
        "B3_golem_death",
        "B3",
        ["Golem"],
        ["InfernoTower", "Knight"],
        [
            cmd(250, 0, "Golem", (3.5, 14.5)),
            cmd(250, 1, "InfernoTower", (3.5, 20.5)),
            cmd(350, 1, "Knight", (3.5, 17.5)),
        ],
        "Golem death damage and push, two Golemite offsets/travel/first action, subsequent Golemite death damage.",
        end=1000,
    ),
    scenario(
        "B3_ghost_reveal",
        "B3",
        ["Ghost"],
        ["Knight", "Archers"],
        [
            cmd(250, 0, "Ghost", (3.5, 14.5)),
            cmd(250, 1, "Knight", (3.5, 17.5)),
            cmd(300, 1, "Archers", (3.5, 22.5)),
        ],
        "Enemy target-lock tick vs Ghost attack-range entry, hit tick and post-kill recloak.",
    ),
    scenario(
        "B1_lightning_shield",
        "B1",
        ["Lightning"],
        ["DarkPrince", "Knight", "Musketeer"],
        [
            cmd(250, 1, "DarkPrince", (5.5, 17.5)),
            cmd(250, 1, "Musketeer", (7.5, 17.5)),
            cmd(320, 1, "Knight", (9.5, 17.5)),
            cmd(340, 0, "Lightning", (7.5, 15.5)),
        ],
        "Highest-HP target selection with shield HP, strike order and flight delay; retain targets inside and outside radius.",
    ),
]
(HERE / "manifest.json").write_text(
    json.dumps(
        {
            "schema": "c56.nm-scenarios.v1",
            "status": "written_only",
            "bundles": BUNDLES,
            "scenarios": out,
        },
        indent=2,
    )
    + "\n"
)
print(f"wrote {len(out)} scenarios; native executions: 0")
