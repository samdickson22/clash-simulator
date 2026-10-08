"""Read-only C56 public-controller metadata and action/mask differentials."""

import json
from types import SimpleNamespace

import numpy as np
import clasher_core
from clasher.arena import TileGrid
from clasher.balance import tournament_tower_stat
from clasher.rl.c56_scripted import C56_ADDED_CARDS
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from clasher.rl.public_action_mask import PublicActionMaskInput
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent, SUPPORTED_CARDS
from clasher.unit_traits import is_air_unit_card

CARDS = tuple(sorted(SUPPORTED_CARDS | C56_ADDED_CARDS))
STYLES = ("balanced", "pressure", "defense")


def metadata(builder, *, bot=None, action_cards=CARDS, mask_version=1):
    if type(mask_version) is not int or mask_version not in (1, 2):
        raise ValueError("mask_version must be 1 (frozen) or 2")
    if bot is None:
        bot = PublicScriptedOpponent(builder, card_scope="c56")
    grid = TileGrid()

    def row(token, stats):
        return dict(
            token=int(token),
            radius=float(stats.collision_radius or 0.5),
            blocker_radius=float(builder.card_stat_features[token, 12]) * 3,
            cost=float(stats.mana_cost),
            count=float(stats.summon_count or 1),
            hp=float(stats.scaled_hitpoints or 0),
            damage=float(stats.scaled_damage or 0),
            range=float(stats.range or 0),
            shield=bool(
                (stats._raw_entry.get("summonCharacterData") or {}).get(
                    "shieldHitpoints", 0
                )
            ),
            building=str(stats.card_type).lower() == "building",
            spell=False,
            margin=int(stats.deploy_w_tile_margin or 0),
            only_buildings=bool(stats.targets_only_buildings),
            air=is_air_unit_card(stats),
            can_air=bool(stats.attacks_air or "AIR" in str(stats.target_type)),
        )

    cards, bodies = {}, {}
    for token, (name, stats) in bot.cards.items():
        data = row(token, stats)
        spell = bot.spells.get(name)
        data["spell"] = spell is not None
        data["unrestricted"] = bool(
            (
                spell is not None
                and not grid._requires_deploy_zone_spell(spell)
                and not getattr(spell, "requires_walkable_target", False)
            )
            or (spell is None and getattr(stats, "can_deploy_on_enemy_side", False))
        )
        if spell is not None:
            if mask_version == 2:
                data["requires_walkable"] = bool(getattr(spell, "requires_walkable_target", False))
                data["requires_territory"] = grid._requires_deploy_zone_spell(spell)
            building_damage = getattr(spell, "building_damage", None)
            data["c56_spell"] = dict(
                radius=float(spell.radius or 0),
                damage=float(getattr(spell, "damage", 0)),
                crown_damage=float(getattr(spell, "crown_tower_damage", 0) or 0),
                building_damage=None
                if building_damage is None
                else float(building_damage),
                duration=float(getattr(spell, "duration", 1) or 1),
                projectile_range=float(getattr(spell, "projectile_range", 0) or 0),
                hits_air=bool(
                    getattr(
                        spell, "hits_air", name not in {"Log", "BarbLog", "Earthquake"}
                    )
                ),
                ignore_buildings=bool(getattr(spell, "ignore_buildings", False)),
            )
        cards[name] = data
    assert set(cards) == set(action_cards)
    # Runtime card names can name a swarm (Bats/Goblins/etc.), while the
    # public token names its serialized child body. Resolve that same token
    # before selecting heuristic cost, radius and blocker metadata.
    samples = [*bot.bodies.values(), *(stats for _, stats in bot.cards.values())]
    for stats in samples:
        if str(stats.card_type).lower() == "spell":
            continue
        namespace = (
            "building_body"
            if str(stats.card_type).lower() == "building"
            else "troop_body"
        )
        token = builder._runtime_entity_token_id(
            SimpleNamespace(card_stats=stats), namespace
        )
        if token not in bot.bodies:
            continue
        visible = bot.bodies[token]
        bodies[stats.name] = row(token, visible)
        bodies[stats.name]["radius"] = float(visible.collision_radius or 0)
    for token, name in bot.crowns.items():
        bodies[name] = dict(
            token=token,
            radius=1.0,
            blocker_radius=float(builder.card_stat_features[token, 12]) * 3,
            cost=0.0,
            count=1.0,
            hp=float(
                tournament_tower_stat(
                    "PrincessTower" if name == "Tower" else "KingTower", "hitpoints"
                )
            ),
            damage=0.0,
            range=0.0,
            shield=False,
            building=True,
            spell=False,
            margin=0,
            only_buildings=False,
            air=False,
            can_air=True,
        )
    result = dict(c56=True, cards=cards, bodies=bodies)
    if mask_version == 2:
        from clasher.rl.public_placement_v2 import payload_radii, building_radii

        result.update(mask_version=2, payload_radii=payload_radii(builder), building_radii=building_radii(builder))
    return result


def resources():
    builder = ContractV5ObservationBuilder()
    meta = metadata(builder)
    scripts = clasher_core.NativeScripts(json.dumps(meta))
    bots = {
        style: PublicScriptedOpponent(builder, style=style, card_scope="c56")
        for style in STYLES
    }
    return builder, meta, scripts, bots


def verify(b, native, builder, scripts, bots, seat, *, actions=True):
    packet = builder.build_public(b, seat)
    bot = bots["balanced"]
    expected = bot.mask_builder.build(
        PublicActionMaskInput.from_confidence_observation(packet)
    ).copy()
    expected[bot.mask_builder.ability_action] = False
    actual = np.asarray(scripts.public_mask(native, seat))
    if not np.array_equal(expected, actual):
        return dict(
            ok=False,
            kind="mask",
            tick=b.tick,
            seat=seat,
            differences=np.flatnonzero(expected != actual).tolist(),
            expected_on_differences=expected[expected != actual].tolist(),
            actual_on_differences=actual[expected != actual].tolist(),
        )
    view = json.loads(scripts.public_view(native, seat))
    bodies = bot._bodies(packet)
    if len(view["bodies"]) != len(bodies):
        return dict(
            ok=False,
            kind="body_count",
            tick=b.tick,
            seat=seat,
            expected=len(bodies),
            actual=len(view["bodies"]),
        )
    for index, (got, want) in enumerate(zip(view["bodies"], bodies)):
        for key in (
            "x",
            "y",
            "enemy",
            "hp",
            "radius",
            "cost",
            "crown",
            "spell_credit",
            "maximum",
            "only_buildings",
        ):
            value = getattr(
                want,
                {"maximum": "max_hp", "only_buildings": "targets_buildings"}.get(
                    key, key
                ),
            )
            if got[key] != value:
                return dict(
                    ok=False,
                    kind="body",
                    tick=b.tick,
                    seat=seat,
                    index=index,
                    field=key,
                    expected=value,
                    actual=got[key],
                )
    if actions:
        for style, controller in bots.items():
            want = controller.select_action(packet)
            got = scripts.select_action(native, seat, style)
            if want != got:
                return dict(
                    ok=False,
                    kind="action",
                    tick=b.tick,
                    seat=seat,
                    style=style,
                    expected=want,
                    actual=got,
                    ranked=[
                        dict(action=d.action_id, score=d.score, reason=d.reason)
                        for d in controller._ranked_actions(packet)
                    ],
                )
    return dict(ok=True, tick=b.tick, seat=seat, styles=len(bots) if actions else 0)
