"""C56 public heuristics, isolated from the admitted P16 scoring path."""

from __future__ import annotations

import copy

import numpy as np

from clasher.card_aliases import resolve_card_name
from clasher.dynamic_spells import create_spell_from_json
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.unit_traits import is_air_unit_card

from .card_semantics import _walk_payload
from .public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from .public_observation import ConfidenceAwareActorObservation

C56_ADDED_CARDS = frozenset(
    {
        "BarbLog",
        "AngryBarbarians",
        "Berserker",
        "Arrows",
        "Tornado",
        "ElectroSpirit",
        "Ghost",
        "Lightning",
        "Balloon",
        "BabyDragon",
        "Wizard",
        "Minions",
        "Valkyrie",
        "Golem",
        "SkeletonArmy",
        "Miner",
        "MiniPekka",
        "FirespiritHut",
        "RoyalHogs",
        "Princess",
        "BlowdartGoblin",
        "Poison",
        "GoblinGang",
        "GoblinBarrel",
        "Bats",
        "Rocket",
        "Wallbreakers",
        "BombTower",
        "Firecracker",
        "MinionHorde",
        "GoblinHut",
        "Goblinstein",
        "Rascals",
        "MightyMiner",
        "Earthquake",
        "FireSpirits",
        "InfernoTower",
        "Xbow",
        "RoyalDelivery",
        "ArcherQueen",
    }
)
CHAMPION_ABILITY_RULE = "masked: C56 scripts never activate abilities; champion probes exercise the engine API separately"


def initialize(bot, builder, style):
    from .public_scripted_opponent import SUPPORTED_CARDS

    if (
        not builder.canonical_perspective
        or not builder.canonical_lane_globals
        or not builder.public_entity_levels
    ):
        raise ValueError(
            "C56 scripts require canonical public coordinates and visible levels"
        )
    if builder.card_semantics_version not in (4, 5):
        raise ValueError("C56 scripts require semantics v4 or v5")
    scope = SUPPORTED_CARDS | C56_ADDED_CARDS
    canonical = {resolve_card_name(n): n for n in scope}
    bot.builder, bot.style = builder, style
    if builder.card_semantics_version == 5:
        from .contract_v5 import ContractV5ActionMaskBuilder

        bot.mask_builder = ContractV5ActionMaskBuilder(builder)
    else:
        if not {resolve_card_name(n) for n in builder.card_vocab} <= canonical.keys():
            raise ValueError("C56 v4 vocabulary exceeds declared action scope")
        bot.mask_builder = PublicActionMaskBuilder(builder)
    bot.cards, bot.bodies, bot.spells = {}, {}, {}
    for declared in builder.card_vocab:
        stats = copy.copy(builder.loader.get_card(declared))
        if stats is None:
            continue
        canonical_name = canonical.get(resolve_card_name(declared))
        if canonical_name is not None:
            if stats.level != 11:
                raise ValueError("own card metadata must declare level11")
            for alias in {declared, canonical_name}:
                bot.cards[builder.token_id(alias, namespace="card_action")] = (
                    canonical_name,
                    stats,
                )
            if str(stats.card_type).lower() == "spell":
                bot.spells[canonical_name] = create_spell_from_json(
                    stats._raw_entry, level=11
                )
        # Every visible payload needs its own health/air metadata, including
        # mixed swarms, death spawns, and broad-scope opponent bodies.
        for payload in _walk_payload(stats._raw_entry):
            if not payload.get("hitpoints") or not payload.get("name"):
                continue
            body = troop_from_character_data(
                payload["name"],
                dict(payload),
                elixir=max(1, stats.mana_cost / max(1, int(stats.summon_count or 1))),
                rarity=payload.get("rarity", "Common"),
            )
            for namespace in ("troop_body", "building_body"):
                token = builder.token_id(payload["name"], namespace=namespace)
                if token > 1:
                    bot.bodies.setdefault(token, body)
        if str(stats.card_type).lower() != "spell":
            namespace = (
                "building_body"
                if str(stats.card_type).lower() == "building"
                else "troop_body"
            )
            for alias in {declared, stats.name}:
                token = builder.token_id(alias, namespace=namespace)
                if token > 1:
                    bot.bodies.setdefault(token, stats)
    bot.crowns = {
        builder.token_id(n, namespace="tower"): n for n in ("Tower", "KingTower")
    }
    tiles = np.arange(576)
    bot.x = tiles % 18 + 0.5
    bot.y = tiles // 18 + 0.5


def ranked_actions(bot, packet, *, all_plays=False):
    from .public_scripted_opponent import PublicScriptedDecision as Decision

    if not isinstance(packet, ConfidenceAwareActorObservation):
        raise TypeError("public confidence-aware observation required")
    packet.validate()
    obs = packet.observation
    if obs.terminal is True:
        return (Decision(2304, "terminal", 0.0),)
    if obs.terminal is None or obs.board_rotated is None:
        raise ValueError("unknown public lifecycle or board orientation")
    empty = (obs.hand_ids[:4] == 0) & (packet.hand_id_confidence[:4] == 0)
    if (
        np.any((packet.hand_id_confidence[:4] < 1) & ~empty)
        or packet.global_feature_confidence[5] < 1
    ):
        raise ValueError("uncertain own hand or elixir")
    if np.any(packet.global_feature_confidence[8:14] < 1):
        raise ValueError("uncertain public Crown health")
    bodies = bot._bodies(packet)
    indices = [
        i
        for i in np.flatnonzero(obs.entity_mask)
        if sum(obs.entity_features[i, 4:6]) >= 0.5
    ]
    enriched = []
    for b, i in zip(bodies, indices):
        stats = bot.bodies.get(int(obs.entity_ids[i]))
        enriched.append(
            (
                b,
                bool(stats and is_air_unit_card(stats)),
                bool(obs.entity_features[i, 5] > 0.5),
            )
        )
    enemies = [
        (b, air, building) for b, air, building in enriched if b.enemy and not b.crown
    ]
    incoming = [r for r in enemies if r[0].y < 17]
    mask = bot.mask_builder.build(
        PublicActionMaskInput.from_confidence_observation(packet)
    ).copy()
    mask[bot.mask_builder.ability_action] = (
        False  # declared rule; no hidden cooldown inference
    )
    elixir = float(obs.global_features[5]) * 10
    reserve = {"pressure": 4, "balanced": 7, "defense": 9}[bot.style]
    decisions = [
        Decision(
            2304, "reserve elixir", 2.8 if not incoming and elixir < reserve else -0.5
        )
    ]
    for slot, token in enumerate(obs.hand_ids[:4]):
        if token == 0:
            continue
        if int(token) not in bot.cards:
            raise ValueError("own hand outside C56 action scope")
        name, stats = bot.cards[int(token)]
        legal = np.flatnonzero(mask[slot * 576 : (slot + 1) * 576])
        if not len(legal):
            continue
        x, y = bot.x[legal], bot.y[legal]
        cost = float(stats.mana_cost)
        if name in {"Miner", "GoblinBarrel"}:
            crowns = [b for b in bodies if b.enemy and b.crown and b.y < 28]
            target = min(crowns, key=lambda b: b.hp, default=None)
            if target is None:
                target = min(
                    (b for b in bodies if b.enemy and b.crown),
                    key=lambda b: b.hp,
                    default=None,
                )
            scores = np.full(len(legal), -1e6)
            if target is not None:
                distance = np.sqrt((x - target.x) ** 2 + (y - target.y) ** 2)
                scores = 6 * np.exp(-abs(distance - 1.8)) - 0.3 * cost
            reason = "enemy-side Crown pressure"
        elif name in bot.spells:
            spell = bot.spells[name]
            value = np.zeros(len(legal))
            lethal = np.zeros(len(legal), bool)
            hits = np.zeros(len(legal), int)
            targets = (
                sorted(enriched, key=lambda row: -row[0].hp)
                if name == "Lightning"
                else enriched
            )
            for b, air, building in targets:
                if (
                    not b.enemy
                    or air
                    and not getattr(
                        spell, "hits_air", name not in {"Log", "BarbLog", "Earthquake"}
                    )
                ):
                    continue
                if building and getattr(spell, "ignore_buildings", False):
                    continue
                radius = float(spell.radius or 0) + b.radius
                overlap = (x - b.x) ** 2 + (y - b.y) ** 2 < radius**2
                if name in {"Log", "BarbLog"}:
                    overlap = (
                        (abs(x - b.x) < radius)
                        & (b.y >= y - 3)
                        & (b.y < y - 3 + spell.projectile_range)
                    )
                if name == "Lightning":
                    overlap &= hits < 3
                    hits += overlap
                if name == "Tornado":
                    # Pull visible threats toward a central defence tile; do
                    # not assume King activation or infer private target locks.
                    if not b.crown and b.y < 19:
                        value += (
                            overlap
                            * b.cost
                            * np.exp(-((x - 9) ** 2 + (y - 10.5) ** 2) / 18)
                        )
                    continue
                horizon = (
                    min(3.0, float(getattr(spell, "duration", 1) or 1))
                    if name in {"Poison", "Earthquake"}
                    else 1.0
                )
                damage = float(getattr(spell, "damage", 0)) * horizon
                if building and not b.crown:
                    damage = float(getattr(spell, "building_damage", damage)) * horizon
                if b.crown:
                    crown = float(getattr(spell, "crown_tower_damage", 0) or 0)
                    lethal |= overlap & (b.hp > 0) & (b.hp <= crown + 1e-3)
                elif b.spell_credit:
                    value += overlap * b.cost * min(damage, b.hp) / max(1, b.max_hp)
            scores = np.where(value >= 0.6 * cost, 4 + value - cost, -1e6)
            scores = np.where(lethal, 100 + value, scores)
            reason = "public spell value"
        else:
            building = str(stats.card_type).lower() == "building"
            can_air = bool(stats.attacks_air or "AIR" in str(stats.target_type))
            threats = [r for r in incoming if not r[1] or can_air]
            threat = min(threats, key=lambda r: r[0].y, default=None)
            lane = np.minimum(abs(x - 3.5), abs(x - 14.5))
            if threat is not None:
                b = threat[0]
                tx = (7.5 if b.x < 9 else 10.5) if building else b.x
                ty = (
                    10.5
                    if building
                    else max(3.5, min(13.5, b.y - max(1, float(stats.range or 0))))
                )
                fit = np.exp(-((x - tx) ** 2 + (y - ty) ** 2) / 8)
                scores = (
                    7 * fit
                    - 0.28 * cost
                    + (2 * fit if building and b.targets_buildings else 0)
                )
                if stats.targets_only_buildings:
                    scores -= 3
                reason = "air-aware defence"
            else:
                desired = (
                    13.5
                    if stats.targets_only_buildings or bot.style == "pressure"
                    else 6.5
                )
                if name == "Xbow":
                    desired = 14.5
                if name == "GoblinHut":
                    desired = 12.5
                if building and name not in {"Xbow", "GoblinHut"}:
                    desired = 10.5
                scores = 4.2 * np.exp(-abs(y - desired) / 3) - lane - 0.32 * cost
                if stats.targets_only_buildings:
                    scores += 1.5
                if incoming and not can_air:
                    scores -= 4
                reason = "siege, spawner or lane placement"
        if all_plays:
            decisions.extend(
                Decision(slot * 576 + int(t), reason, float(s))
                for t, s in zip(legal, scores)
            )
        else:
            at = int(np.argmax(scores))
            decisions.append(
                Decision(slot * 576 + int(legal[at]), reason, float(scores[at]))
            )
    result = tuple(sorted(decisions, key=lambda d: (-d.score, d.action_id)))
    assert mask[result[0].action_id]
    return result
