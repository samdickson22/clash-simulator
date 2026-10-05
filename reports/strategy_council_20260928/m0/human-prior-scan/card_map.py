"""RoyaleAPI/IL_Replay card slugs -> clasher gamedata names (base forms).

Evolution (``-ev1``) and hero (``-hero``) slugs are substituted by their base
form.  ``APPROX`` marks base slugs whose nearest gamedata entry is a known
semantic approximation rather than the same card.
"""

from __future__ import annotations

PILOT16 = (
    "Archers", "Cannon", "DarkPrince", "Fireball", "Giant", "Goblins",
    "HogRider", "IceGolem", "IceSpirit", "Knight", "Log", "Musketeer",
    "Prince", "Skeletons", "Tesla", "Zap",
)

SLUG_TO_GAMEDATA = {
    "archer-queen": "ArcherQueen", "archers": "Archers", "arrows": "Arrows",
    "baby-dragon": "BabyDragon", "balloon": "Balloon", "bandit": "Bandit",
    "barbarian-barrel": "BarbarianBarrel", "barbarian-hut": "BarbarianHut",
    "barbarians": "Barbarians", "bats": "Bats", "battle-healer": "BattleHealer",
    "battle-ram": "BattleRam", "berserker": "Berserker", "bomb-tower": "BombTower",
    "bomber": "Bomber", "boss-bandit": "BossBandit", "bowler": "Bowler",
    "cannon": "Cannon", "cannon-cart": "MovingCannon", "clone": "Clone",
    "dark-prince": "DarkPrince", "dart-goblin": "DartGoblin",
    "earthquake": "Earthquake", "electro-dragon": "ElectroDragon",
    "electro-giant": "ElectroGiant", "electro-spirit": "ElectroSpirit",
    "electro-wizard": "ElectroWizard", "elite-barbarians": "AngryBarbarians",
    "elixir-collector": "Elixir Collector", "elixir-golem": "ElixirGolem",
    "executioner": "AxeMan", "fire-spirit": "FireSpirits", "fireball": "Fireball",
    "firecracker": "Firecracker", "fisherman": "Fisherman",
    "flying-machine": "DartBarrell", "freeze": "Freeze", "furnace": "FirespiritHut",
    "giant": "Giant", "giant-skeleton": "GiantSkeleton",
    "giant-snowball": "GiantSnowball", "goblin-barrel": "GoblinBarrel",
    "goblin-cage": "GoblinCage", "goblin-curse": "GoblinCurse",
    "goblin-demolisher": "GoblinDemolisher", "goblin-drill": "GoblinDrill",
    "goblin-gang": "GoblinGang", "goblin-giant": "GoblinGiant",
    "goblin-hut": "GoblinHut", "goblin-machine": "GoblinMachine",
    "goblins": "Goblins", "goblinstein": "Goblinstein",
    "golden-knight": "GoldenKnight", "golem": "Golem", "graveyard": "Graveyard",
    "guards": "Guards", "heal-spirit": "Heal", "hog-rider": "HogRider",
    "hunter": "Hunter", "ice-golem": "IceGolem", "ice-spirit": "IceSpirit",
    "ice-wizard": "IceWizard", "inferno-dragon": "InfernoDragon",
    "inferno-tower": "InfernoTower", "knight": "Knight", "lava-hound": "LavaHound",
    "lightning": "Lightning", "little-prince": "LittlePrince",
    "lumberjack": "Lumberjack", "magic-archer": "MagicArcher",
    "mega-knight": "MegaKnight", "mega-minion": "MegaMinion",
    "mighty-miner": "MightyMiner", "miner": "Miner", "mini-pekka": "MiniPekka",
    "minion-horde": "MinionHorde", "minions": "Minions", "mirror": "Mirror",
    "monk": "Monk", "mortar": "Mortar", "mother-witch": "WitchMother",
    "musketeer": "Musketeer", "night-witch": "NightWitch", "pekka": "Pekka",
    "phoenix": "Phoenix", "poison": "Poison", "prince": "Prince",
    "princess": "Princess", "rage": "Rage", "ram-rider": "RamRider",
    "rascals": "Rascals", "rocket": "Rocket", "ronin": "Ronin",
    "royal-delivery": "RoyalDelivery", "royal-ghost": "RoyalGhost",
    "royal-giant": "RoyalGiant", "royal-hogs": "RoyalHogs",
    "royal-recruits": "RoyalRecruits", "rune-giant": "GiantBuffer",
    "skeleton-army": "SkeletonArmy", "skeleton-barrel": "SkeletonBarrel",
    "skeleton-dragons": "SkeletonDragons", "skeleton-king": "SkeletonKing",
    "skeletons": "Skeletons", "sparky": "ZapMachine",
    "spear-goblins": "SpearGoblins", "spirit-empress": "MergeMaiden_Normal",
    "suspicious-bush": "SuspiciousBush", "tesla": "Tesla", "the-log": "Log",
    "three-musketeers": "ThreeMusketeers", "tombstone": "Tombstone",
    "tornado": "Tornado", "valkyrie": "Valkyrie", "vines": "Vines",
    "void": "DarkMagic", "wall-breakers": "Wallbreakers", "witch": "Witch",
    "wizard": "Wizard", "x-bow": "Xbow", "zap": "Zap", "zappies": "MiniSparkys",
}

# Nearest-entry approximations (not the same modern card).
APPROX = {
    "heal-spirit": "gamedata has the legacy Heal spell, not the Heal Spirit troop",
    "spirit-empress": "MergeMaiden spell entry is a no-op; the 3-elixir ground MergeMaiden_Normal troop is substituted (no mounted/air mode)",
}

# Scalar smoke results (card_smoke.json / spell_probe.json): accepted by
# deploy_card at level 11 but the defining effect is absent.
NO_EFFECT = {
    "vines": "accepted, zero damage/status on units and towers",
    "void": "DarkMagic accepted, zero damage on units and towers",
    "goblin-curse": "accepted, zero damage, no goblin conversion",
}
BODY_ONLY = {
    "elixir-collector": "building spawns but produces no elixir",
    "goblin-drill": "own-side building only; enemy-side dig rejected, no goblins spawned",
}
UNSUPPORTED_BASE = set(NO_EFFECT) | set(BODY_ONLY)

# Tower-troop variants are substituted by Tower Princess (engine has only Princess towers).
TOWER_SUBSTITUTE = {"tower-princess": "base", "royal-chef": "approx", "cannoneer": "approx", "dagger-duchess": "approx"}

FORM_SUFFIXES = ("-ev1", "-ev2", "-hero")


def base_slug(slug: str) -> tuple[str, str]:
    """Return (base_slug, form) where form is 'base', 'evo' or 'hero'."""
    for suffix in FORM_SUFFIXES:
        if slug.endswith(suffix):
            return slug[: -len(suffix)], ("hero" if suffix == "-hero" else "evo")
    return slug, "base"
