"""Full-tick differential against the unchanged Python engine; no training imports.

Run with PYTHONPATH=engine-rs:src. Native simulation never calls back into Python.
Card data and initial state are exported once, before either engine is timed.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ES = ROOT / "reports/strategy_council_20260928/engine-speed"
sys.path.insert(0, str(ES))
from es_common import battle_digest
from clasher.battle import BattleState
from clasher.arena import Position
from clasher.pathfinding import _native_grid_route, _standard_path_cost_map
from clasher.native_tilemap import native_spawn_tile_blocked
from clasher.unit_traits import unit_mass
import clasher_core

CARDS = ("Knight", "Archers", "Giant", "Musketeer")


def initial(seed=1, cards=CARDS, *, level=11):
    b = BattleState(rng=random.Random(seed))
    for p in b.players:
        if level != 11:
            p.set_card_levels({name: level for name in cards})
        p.hand = list(cards[:4])
        p.deck = (list(cards) * 2)[:8]
        p.cycle_queue = deque((list(cards) * 2)[4:8])
    return b


def entity(e, *, clone_prototype=True):
    from mirror_snapshot import payload_key
    from clasher.unit_traits import is_knockback_immune, is_hover_unit_card
    from clasher.gamedata_normalization import serialized_hit_planes
    from clasher.ordinary_combat_clock import supported

    from champion_snapshot import champion
    from scope_snapshot import effect_state
    from spawn_snapshot import spawner
    from dash_snapshot import dash
    from leap_snapshot import leap
    from hook_snapshot import hook

    spawn_spec, spawn_state = spawner(e)
    spawn_push = next((m for m in e.mechanics if type(m).__name__ == "SpawnPushback"), None)
    dash_spec, dash_state = dash(e)
    leap_spec, leap_state = leap(e)
    hook_spec, hook_state = hook(e)

    s = e.card_stats
    projectile = getattr(s, "projectile_data", None) or {}
    child = (
        getattr(e, "spawn_projectile_data", projectile.get("spawnProjectileData")) or {}
    )
    interval = int(getattr(s, "hit_speed", 0) or 1)
    load = int(getattr(s, "load_time", 0) or 0)
    spirit = next(
        (
            m
            for m in e.mechanics
            if type(m).__name__
            in (
                "IceSpiritFreeze",
                "ElectroSpiritChain",
                "KamikazeSplash",
                "HealSpiritBurst",
            )
        ),
        None,
    )
    from clasher.balance import (
        LOGIC_SPAWN_PATHFIND_REACHED_RADIUS_FROM_SPEED,
        LOGIC_CHARACTER_CONTINUOUS_DAMAGE_ATTACK_CLOSER,
    )

    tunnel = next(
        (m for m in e.mechanics if type(m).__name__ == "UndergroundDeployment"), None
    )
    if tunnel is None:
        tunnel = next(
            (m.tunnel for m in e.mechanics if type(m).__name__ == "MightyMinerSwitch"),
            None,
        )
    crown = next(
        (m for m in e.mechanics if type(m).__name__ == "CrownTowerScaling"), None
    )
    collector = next(
        (m for m in e.mechanics if type(m).__name__ == "ElixirProduction"), None
    )
    ramp = next((m for m in e.mechanics if type(m).__name__ == "DamageRamp"), None)
    death = next((m for m in e.mechanics if type(m).__name__ == "DeathDamage"), None)
    death_spawn = next((m for m in e.mechanics if type(m).__name__ == "DeathSpawn"), None)
    multi = next((m for m in e.mechanics if type(m).__name__ == "MultipleTargetAttack"), None)
    hit_buff = next((m for m in e.mechanics if type(m).__name__ == "SerializedOnHitBuff"), None)
    dragon_source = getattr(e, "source_entity", None) or e
    dragon = next((m for m in dragon_source.mechanics if type(m).__name__ == "ElectroDragonChainLightning"), None)
    souls = next((m for m in e.mechanics if type(m).__name__ == "SkeletonKingSoulCollector"), None)
    hide = next((m for m in e.mechanics if type(m).__name__ == "HideWhenIdle"), None)
    ghost = next(
        (m for m in e.mechanics if type(m).__name__ == "InvisibilityWhenNotAttacking"),
        None,
    )
    projectile_air, projectile_ground = serialized_hit_planes(
        projectile,
        default_air=e._can_attack_air(),
        default_ground=e._can_attack_ground(),
    )
    buff = projectile.get("targetBuffData") or {}
    projectile_stun = (
        float(projectile.get("buffTime", 0)) / 1000.0
        if buff.get("speedMultiplier") == -100
        and buff.get("hitSpeedMultiplier") == -100
        else 0.0
    )
    stats = dict(
        spawn_push=(spawn_push.distance_tiles, spawn_push.radius_tiles, spawn_push.hits_air, spawn_push.hits_ground) if spawn_push else None,
        dash=dash_spec,
        leap=leap_spec,
        hook=hook_spec,
        dragon_chain=dragon is not None,
        multi_attack=dict(count=multi.target_count, fill_primary=multi.all_targets_hit, scale=multi.damage_scale) if multi else None,
        souls=dict(radius=souls.soul_collection_radius, maximum=souls.max_souls) if souls else None,
        hit_buff=dict(duration=hit_buff.duration_ms / 1000.0, axes=(hit_buff.movement_multiplier, hit_buff.attack_multiplier, hit_buff.spawn_multiplier)) if hit_buff else None,
        skip_deploy_snap=float(getattr(s, "speed", 0) or 0) <= 0,
        break_on_building_hit=any(type(m).__name__ == "BattleRamCharge" for m in e.mechanics),
        death_spawn_radius=death_spawn.radius_tiles if death_spawn else float(getattr(e,'death_spawn_radius',0)),
        death_spawn_angle=int(getattr(s, "spawn_angle_shift", 0) or 0) if death_spawn else 0,
        death_spawn_const=bool(getattr(e,'spawn_const_priority',getattr(death_spawn,'spawn_const_priority',False))),
        death_zero_count=(
            death_spawn.count
            if death_spawn is not None
            and death_spawn.radius_tiles == 0
            and (death_spawn.unit_data or {}).get("hitpoints")
            else 0
        ),
        leaf_elixir_share=max(0.0, float(getattr(s, "mana_cost", 0) or 0))
        / max(1, int(getattr(s, "summon_count", 0) or 0)
              + int(getattr(s, "summon_character_second_count", 0) or 0)),
        projectile_stun=float(getattr(e, "stun_duration", projectile_stun)),
        projectile_slow_duration=float(getattr(e, "slow_duration", 0 if projectile_stun else float(projectile.get("buffTime", 0)) / 1000.0)),
        projectile_slow_multiplier=float(e.slow_multiplier if e.entity_kind == 2 else max(0.0, 1.0 + float(buff.get("speedMultiplier", 0)) / 100.0)),
        area_while_invisible=bool(
            getattr(s, "allow_area_damage_when_invisible", False)
        ),
        spawner=spawn_spec,
        collect_interval=getattr(collector, "interval_ms", 0.0),
        collect_amount=getattr(collector, "amount", 0.0),
        collect_death=getattr(collector, "on_death_amount", 0.0),
        crown_damage=getattr(crown, "crown_tower_damage", None),
        tunnel_speed=round(getattr(tunnel, "travel_speed_logic_units_per_tick", 0)),
        tunnel_reached_from_speed=LOGIC_SPAWN_PATHFIND_REACHED_RADIUS_FROM_SPEED,
        tunnel_emergence=float(getattr(e, "_underground_emergence_delay", 0)),
        ramp_stages=getattr(ramp, "stages", []),
        ramp_approach=(
            LOGIC_CHARACTER_CONTINUOUS_DAMAGE_ATTACK_CLOSER / 1000
            if ramp and e.entity_kind == 0
            else 0.0
        ),
        hover=is_hover_unit_card(s),
        ghost_fade=getattr(ghost, "fade_delay_ms", 0),
        ghost_range=getattr(ghost, "use_attack_range", False),
        kamikaze=any(type(m).__name__ == "WallBreakersDemolition" for m in e.mechanics),
        kamikaze_delay=float(getattr(s,'kamikaze_time',0) or 0)/1000
        if getattr(s,'kamikaze',False) and getattr(s,'damage',None) is None else None,
        projectile_air=bool(getattr(e, "hits_air", projectile_air)),
        projectile_ground=bool(getattr(e, "hits_ground", projectile_ground)),
        rolling=bool(projectile.get('projectileRadius') and projectile.get('projectileRange') and projectile.get('pushback')),
        projectile_knockback=float(projectile.get('pushback', 0) or 0) / 1000,
        homing_time=int(projectile.get('homingTime', 0) or 0),
        homing_min=float(projectile.get('homingMinDistance', 0) or 0) / 1000,
        rolling_radius=float(projectile.get('projectileRadius', 0) or 0) / 1000,
        projectile_extra=float(getattr(e,'start_extra_radius',float(projectile.get('projectileStartExtraRadius',0) or 0)/1000)),
        projectile_range=float(projectile.get("projectileRange", 0) or 0) / 1000,
        recoil=next(
            (
                m.recoil_distance
                for m in e.mechanics
                if type(m).__name__ == "AttackRecoil"
            ),
            0,
        ),
        projectile_damage=0.0 if child and projectile.get("damage") is None else None,
        child_count=int(child.get("spawnCount", 0)),
        child_damage=float(s.get_scaled_stat(child["damage"]))
        if child.get("damage") and s
        else 0,
        child_speed=int(child.get("speed", 0)),
        child_radius=float(child.get("projectileRadius", child.get("radius", 0)))
        / 1000,
        child_range=int(child.get("projectileRange", 0)),
        child_spread=int(child.get("spawnRadius", 0)),
        child_extra=float(child.get("projectileStartExtraRadius", 0)) / 1000,
        air=bool(getattr(e, "is_air_unit", False)),
        electro_chain=bool(spirit and type(spirit).__name__ == "ElectroSpiritChain"),
        chain_range=getattr(e, "chain_range", getattr(spirit, "chain_range", 0)),
        chain_count=getattr(spirit, "max_targets", 0),
        chain_interval=getattr(e, "fixed_hop_duration", None)
        or getattr(spirit, "chain_interval_seconds", 0),
        spirit_speed=spirit.jump_speed_logic_units_per_tick if spirit else 0,
        spirit_radius=getattr(spirit, "freeze_radius", 0),
        spirit_stun=0
        if type(spirit).__name__ in ("KamikazeSplash", "HealSpiritBurst")
        else (
            getattr(
                spirit, "freeze_duration_ms", getattr(spirit, "stun_duration_ms", 0)
            )
            / 1000
        )
        if spirit
        else getattr(e, "stun_duration", 0),
        death_damage=death.scaled_damage if death else 0,
        death_radius=death.radius_tiles if death else 0,
        death_knockback=death.knockback_distance if death else 0,
        charge_range=int(getattr(s, "charge_range", 0) or 0),
        charge_speed=round(e._native_charge_speed())
        if getattr(s, "charge_range", None)
        else 0,
        special_damage=float(getattr(s, "scaled_damage_special", 0) or 0),
        area_radius=float(getattr(s, "area_damage_radius", 0) or 0) / 1000,
        self_area=bool(getattr(s, "self_as_aoe_center", False)),
        can_air=e._can_attack_air(),
        can_ground=bool(getattr(e, "hits_ground", e._can_attack_ground())),
        jump_speed=int(getattr(s, "jump_speed", 0) or 0)
        if getattr(s, "jump_height", None) else 0,
        knockback_immune=is_knockback_immune(s),
        hide_ms=hide.hide_delay_ms if hide else 0,
        rise_ms=hide.rise_time_ms if hide else 0,
        ordinary=supported(e),
        finish_allowed=interval > 1
        and not any(
            getattr(s, name, False)
            for name in (
                "load_first_hit",
                "override_attack_finish_time",
                "attack_sequence",
            )
        ),
        lifetime=int(getattr(s, "lifetime_ms", 0) or 0),
        max_hp=float(e.max_hitpoints),
        name=getattr(s, "name", ""),
        payload_key=payload_key(getattr(s, 'name', ''), getattr(s, 'level', 11)),
        radius=e.get_collision_radius(),
        mass=unit_mass(s),
        range=float(getattr(e, "range", 0)),
        sight=float(getattr(e, "sight_range", 0)),
        speed=round((getattr(s, "speed", 0) or 0) if type(e).__name__ == "Troop" else getattr(e, "speed", 0)),
        damage=float(getattr(e, "damage", 0)),
        interval=interval,
        load=load,
        projectile_speed=int(projectile.get("speed", 0)),
        homing=bool(
            getattr(
                e,
                "tracks_target",
                projectile.get("homing", True)
                and not projectile.get("spawnProjectileData")
                and not projectile.get("projectileRange"),
            )
        ),
        projectile_radius=float(
            getattr(e, "splash_radius", projectile.get("radius", 0) / 1000)
        ),
        only_buildings=bool(getattr(s, "targets_only_buildings", False)),
        stop_ms=int(getattr(s, "stop_movement_after_ms", 0) or 0),
        wait_ms=int(getattr(s, "wait_ms", 0) or 0),
        sight_back=float(getattr(s, "sight_clip", 0) or 0),
        sight_side=float(getattr(s, "sight_clip_side", 0) or 0),
        first=e.get_preloaded_attack_time_seconds(),
        retarget=float(getattr(s, "retarget_time", 0) or 0) / 1000,
        muzzle=float(getattr(s, "projectile_start_radius", 0) or 0),
        muzzle_y=float(getattr(s, "projectile_y_offset", 0) or 0),
        activation=float(getattr(e, "activation_delay_seconds", 0)),
        activation_hit=float(getattr(e, "activation_first_hit_delay_seconds", 0)),
        distance_discount=float(
            getattr(e, "_native_target_distance_discount_sq_units", 0)
        ),
    )

    def coord(value):
        return (value.x, value.y) if value is not None else (0.0, 0.0)

    out = dict(
        souls_collected=getattr(souls, "souls_collected", 0),
        kamikaze_primed=bool(getattr(e,'kamikaze_primed',False)),
        kamikaze_timer=float(getattr(e,'kamikaze_timer_remaining',0)),
        entity_kind=e.entity_kind,
        freeze_pause=float(e._freeze_target_pause_remaining),
        champion=champion(e),
        is_clone=bool(e.is_clone),
        freeze_carrier=bool(getattr(e, "carries_freeze_to_children", False)),
        scope_skip_birth=getattr(e, "_native_object_birth_tick", None) is not None,
        move_mode=float(e.movement_mode_multiplier),
        attack_mode=float(e.attack_mode_multiplier),
        production=spawn_state,
        spawn_area_done=bool(e.is_clone and getattr(e, '_spawn_hook_fired', False)) or all(
            getattr(m, "_applied", False)
            for m in e.mechanics
            if type(m).__name__ == "SpawnAreaEffect"
        ),
        collect_elapsed=getattr(collector, "_elapsed_ms", 0.0),
        scope=effect_state(e),
        hastes=[list(v) for v in e._haste_effects],
        dash=dash_state,
        leap=leap_state,
        hook=hook_state,
        forced_active=bool(e.forced_movement_active),
        spawn_push_done=not bool(getattr(e,"_spawn_hook_pending",False)) if spawn_push else True,
        grounded=bool(getattr(e, "_vines_grounded", False)),
        freeze_expiry=float(getattr(e, "freeze_expiry_time", 0)),
        source_character=getattr(getattr(e, "source_entity", None), "entity_kind", 4)
        in (0, 1),
        underground=bool(getattr(e, "_underground_deployment", False)),
        tunnel_origin=coord(getattr(e, "_underground_origin", None)),
        tunnel_destination=coord(getattr(e, "_underground_destination", None)),
        tunnel_duration=float(getattr(e, "_underground_travel_duration", 0)),
        tunnel_total=float(getattr(e, "placement_delay_total", 0)),
        death_immunity=(
            e._death_spawn_target_immunity_elapsed_ms
            if e._death_spawn_target_immunity_elapsed_ms >= 0
            else None
        ),
        death_travel=(
            None
            if e._death_spawn_travel_target is None
            else (e._death_spawn_travel_target.x, e._death_spawn_travel_target.y)
        ),
        death_ticks=e._death_spawn_travel_ticks_remaining,
        stealth_until=int(getattr(e, "_stealth_until", 0)),
        ghost_time=float(getattr(ghost, "time_since_attack_ms", 0)),
        ramp_target=getattr(ramp, "_current_target_id", None),
        ramp_time=getattr(ramp, "_current_target_ms", 0.0),
        placement_radius=(
            float(getattr(e, "deployment_collision_radius", 0.5) or 0.5)
            if getattr(e, "blocks_deployment", False)
            else None
        ),
        bomb_knockback=float(getattr(e, "knockback_distance", 0)),
        bomb_ignores_mass=bool(getattr(e, "knockback_ignores_mass", False)),
        bomb_timer=float(getattr(e, "explosion_timer", 0)),
        bomb_damage=float(getattr(e, "explosion_damage", 0)),
        bomb_radius=float(getattr(e, "explosion_radius", 0)),
        effect_duration=float(getattr(e, "duration", 0)),
        effect_radius=float(getattr(e, "radius", 0)),
        effect_slow_ms=round(getattr(e, "slow_refresh_duration", 0) * 1000),
        effect_multiplier=float(getattr(e, "speed_multiplier", 1)),
        shield=sum(getattr(m, "current_shield", 0) for m in e.mechanics),
        id=e.id,
        owner=e.player_id,
        x=e.position.x,
        y=e.position.y,
        hp=float(e.hitpoints),
        alive=e.is_alive,
        **{"class": type(e).__name__},
        target=e.target_id,
        stats=stats,
        deploy=e.deploy_delay_remaining,
        stagger=e.spawn_stagger_remaining,
        king=bool(getattr(e, "_is_king_tower", False)),
        active=bool(getattr(e, "_tower_active", True)),
        lane=int(getattr(e, "_native_lane_id", 0)),
        age=int(getattr(e, "_native_deployed_elapsed_ms", 0)),
        clock_initialized=e._ordinary_clock is not None,
        clock=dict(interval=interval, load=load, timeline=0, remaining=0, finish=0),
        facing=[int(e._facing_x_units), int(e._facing_y_units)],
        cooldown=float(e.attack_cooldown),
        force_due=stats["ordinary"] and e.attack_cooldown <= 0,
    )
    if clone_prototype and type(e).__name__ == 'Troop' and not e.is_clone and s is not None:
        from clone_snapshot import prototype
        out['clone_template'] = prototype(e)
    return out


def config(cards=CARDS, *, level=11, mirror_templates=True):
    from functools import partial
    template_battle = partial(initial, level=level)
    from clasher.logic_math import logic_cos, logic_sin, _ATAN_TABLE

    out = dict(
        atan=list(_ATAN_TABLE),
        rotations=[(logic_cos(a, 1024), logic_sin(a, 1024)) for a in range(360)],
        costs=[
            _standard_path_cost_map(0, False)[x, y]
            for y in range(64)
            for x in range(36)
        ],
        water=[native_spawn_tile_blocked(x, y) for y in range(64) for x in range(36)],
        cards={},
        death_areas={},
        death_objects={},
        death_children={},
        spirit_areas={},
        production_children={},
        spawn_areas={},
        ability_bombs={},
    )
    from clasher.placement import ground_spawn_tile_clear

    from clasher.native_tilemap import nearest_native_path_id

    out["lane_ids"] = [
        nearest_native_path_id(x * 500, y * 500) for y in range(64) for x in range(36)
    ]
    arena = template_battle().arena
    out["blocked_tiles"] = [
        (x, y) in arena.BLOCKED_TILES for y in range(32) for x in range(18)
    ]
    out["walkable"] = [
        arena.is_walkable(Position(x + 0.5, y + 0.5))
        for y in range(32)
        for x in range(18)
    ]
    out["spawn_clear"] = [
        ground_spawn_tile_clear(Position(x + 0.5, y + 0.5))
        and arena.is_walkable(Position(x + 0.5, y + 0.5))
        for y in range(32)
        for x in range(18)
    ]
    for card in cards:
        if card == 'Mirror':
            out['cards'][card] = dict(cost=1.0, units=[[], []], mirror=True, footprint=0)
            continue
        b = template_battle(cards=(card,) + CARDS)
        _, stats, spell = b.resolve_card_play(0, card)
        if spell is not None:
            from dataclasses import asdict

            templates = [[], []]
            spawns = [[], []]
            if type(spell).__name__ in (
                "ProjectileSpell",
                "RollingProjectileSpell",
                "RoyalDeliverySpell",
                "SpawnProjectileSpell",
            ):
                for seat in (0, 1):
                    probe = template_battle()
                    spell.cast(probe, seat, Position(4.5, 10.5))
                    templates[seat] = [entity(probe.entities[max(probe.entities)])]
                    templates[seat][0]["stats"]["speed"] = round(
                        spell.travel_speed
                        * (
                            1
                            if type(spell).__name__ == "RollingProjectileSpell"
                            else 50
                        )
                    )
                    templates[seat][0]["spell_name"] = card
                    if (
                        type(spell).__name__ == "RollingProjectileSpell"
                        and spell.spawn_character
                    ):
                        carrier = probe.entities[max(probe.entities)]
                        carrier._spawn_character(probe)
                        spawns[seat] = [entity(probe.entities[max(probe.entities)])]
                    elif type(spell).__name__ in (
                        "RoyalDeliverySpell",
                        "SpawnProjectileSpell",
                    ):
                        carrier = probe.entities[max(probe.entities)]
                        carrier._spawn_units(probe)
                        spawns[seat] = [
                            entity(probe.entities[id])
                            for id in range(carrier.id + 1, probe.next_entity_id)
                        ]
                        for child in spawns[seat]:
                            child["x"] = round(
                                child["x"] - carrier.target_position.x, 3
                            )
                            child["y"] = round(
                                child["y"] - carrier.target_position.y, 3
                            )
            elif type(spell).__name__ in (
                "RankedStrikeSpell",
                "AreaEffectSpell",
                "TornadoSpell",
                "VinesSpell",
                "VoidSpell",
                "GoblinCurseSpell",
                "GraveyardSpell",
                "SummonedAreaSpell",
            ):
                for seat in (0, 1):
                    probe = template_battle()
                    spell.cast(probe, seat, Position(4.5, 10.5))
                    templates[seat] = [entity(probe.entities[max(probe.entities)])]
                    templates[seat][0]["spell_name"] = card
                    if type(spell).__name__ == "GraveyardSpell":
                        effect = probe.entities[max(probe.entities)]
                        effect._spawn_skeleton(probe)
                        spawns[seat] = [entity(probe.entities[max(probe.entities)])]
                    if type(spell).__name__ == "GoblinCurseSpell":
                        effect = probe.entities[max(probe.entities)]
                        effect._spawn_goblin(probe, Position(4.5, 10.5))
                        spawns[seat] = [entity(probe.entities[max(probe.entities)])]
            spell_data = asdict(spell)
            spell_data.setdefault("crown_tower_damage_multiplier", 1.0)
            if type(spell).__name__ == "TornadoSpell":
                spell_data.update(
                    damage=spell.damage_per_hit,
                    max_damage_ticks=0,
                    target_local_damage=True,
                    periodic_damage_buff_duration=spell.buff_duration,
                    periodic_damage_controlled_by_parent=spell.controlled_by_parent,
                )
            out["cards"][card] = dict(
                cost=float(stats.mana_cost),
                units=templates,
                footprint=0,
                anchors=[],
                spell=spell_data,
                spawns=spawns,
            )
            continue
        formations = []
        for seat in (0, 1):
            b = template_battle(cards=(card,) + tuple(c for c in CARDS if c != card))
            b.players[seat].elixir = 10
            old = set(b.entities)
            x, y = (8.5 if card == "RoyalRecruits" else 4.5), 10.5 if seat == 0 else 21.5
            assert b.deploy_card(seat, card, Position(x, y))
            units = [entity(b.entities[i]) for i in sorted(b.entities.keys() - old)]
            for unit in units:
                if unit["underground"]:
                    unit["x"], unit["y"] = unit["tunnel_destination"]
                # Formation offsets exclude the documented one-unit anchor snap.
                unit["x"] = (
                    0.0
                    if unit["class"] == "Building"
                    else round(
                        unit["x"] - x + (0 if unit["stats"]["air"] or unit["stats"]["skip_deploy_snap"] else 0.001), 3
                    )
                )
                unit["y"] = (
                    0.0
                    if unit["class"] == "Building"
                    else round(
                        unit["y"]
                        - y
                        + (0.001 if seat and not unit["stats"]["air"] and not unit["stats"]["skip_deploy_snap"] else 0),
                        3,
                    )
                )
            formations.append(units)
        from clasher.placement import _buildable_anchors

        building = units[0]["class"] == "Building" if units else False
        size = (
            b._building_footprint_size_tiles(b.entities[max(b.entities)].card_stats)
            if building
            else 0
        )
        out["cards"][card] = dict(
            cost=10.0 - b.players[seat].elixir,
            units=formations,
            anchors=_buildable_anchors(size) if building else [],
            footprint=size,
            anywhere=bool(getattr(stats, "can_deploy_on_enemy_side", False)),
            margin=int(getattr(stats, "deploy_w_tile_margin", 0) or 0),
            mirror_x=len(units) in (2, 3, 4),
            recruits_line=card == "RoyalRecruits",
        )
        if card == "MightyMiner":
            source = b.entities[max(b.entities)]
            mechanic = next(
                m for m in source.mechanics if type(m).__name__ == "MightyMinerSwitch"
            )
            mechanic.pending_ms = 0
            mechanic.on_object_tick(source, 0)
            out["ability_bombs"][source.card_stats.name] = entity(
                b.entities[max(b.entities)]
            )
        if card == "ElectroDragon":
            source = b.entities[units[0]["id"]]
            mechanic = next(m for m in source.mechanics if type(m).__name__ == "ElectroDragonChainLightning")
            mechanic.on_attack_hit(source,b.entities[1])
            chain = b.entities[max(b.entities)]
            out["cards"][card]["chain"] = entity(chain)
            out["cards"][card]["chain"]["stats"]["speed"] = round(chain.travel_speed * 50)
            out["cards"][card]["chain"]["chain_remaining"] = chain.remaining_bounces
        if card == "ElectroSpirit":
            source = b.entities[max(b.entities)]
            mechanic = next(
                m for m in source.mechanics if type(m).__name__ == "ElectroSpiritChain"
            )
            mechanic._land(source, b.entities[1])
            out["cards"][card]["chain"] = entity(b.entities[max(b.entities)])
        if card in ("RageBarbarian", "SuspiciousBush"):
            source = b.entities[units[0]["id"]]
            mechanic = next(m for m in source.mechanics if type(m).__name__ == "DeathAreaEffect")
            mechanic.on_death(source)
            out["death_areas"][source.card_stats.name] = entity(b.entities[max(b.entities)])
        if card == "SuspiciousBush":
            from payload_snapshot import export_payloads
            export_payloads(b.entities[units[0]["id"]], b, out)
        if card == "IceGolem":
            source = b.entities[max(b.entities)]
            name = source.card_stats.name
            source.take_damage(source.hitpoints)
            out["death_areas"][name] = entity(b.entities[max(b.entities)])
        if card == "Heal":
            source = b.entities[max(b.entities)]
            mechanic = next(
                m for m in source.mechanics if type(m).__name__ == "HealSpiritBurst"
            )
            mechanic._after_impact(source, source.position)
            out["spirit_areas"][source.card_stats.name] = entity(
                b.entities[max(b.entities)]
            )
        if card in ("Golem", "GoblinDrill", "GoblinHut", "GoblinCage", "Tombstone", "BattleRam"):
            source = b.entities[max(b.entities)]
            if getattr(source, "_underground_deployment", False):
                source.position = Position(
                    source._underground_destination.x, source._underground_destination.y
                )
            mechanic = next(
                m for m in source.mechanics if type(m).__name__ == "DeathSpawn"
            )
            first = b.next_entity_id
            mechanic.on_death(source)
            children = []
            for id in range(first, b.next_entity_id):
                child = entity(b.entities[id])
                destination = child["death_travel"] or (child["x"], child["y"])
                child["x"] = round(destination[0] - source.position.x, 3)
                child["y"] = round(destination[1] - source.position.y, 3)
                children.append(child)
            out["death_children"][source.card_stats.name] = children
        if card in ("GoblinDrill", "FirespiritHut", "GoblinHut", "Tombstone", "Witch"):
            # The original parent survives any metadata-only death-spawn probe.
            source = b.entities[units[0]["id"]]
            spawner = next(
                m
                for m in source.mechanics
                if type(m).__name__ in ("PeriodicSpawner", "GoblinHutProduction")
            )
            spawner._spawn_units(
                source, count=1, start_index=0, wave_size=spawner.count
            )
            out["production_children"][source.card_stats.name] = entity(
                b.entities[max(b.entities)]
            )
        source = b.entities[units[0]["id"]]
        if card == "SkeletonKing":
            import math
            groups = [[], []]
            for owner in (0, 1):
                for x in (4.5, 13.5):
                    probe = template_battle()
                    first = probe.next_entity_id
                    probe._spawn_troop(Position(x, 10.5), owner, probe.card_loader.get_card("Skeleton"))
                    group = []
                    for id in range(first, probe.next_entity_id):
                        child = entity(probe.entities[id])
                        child['x'] = round(child['x'] - x, 3)
                        child['y'] = round(child['y'] - 10.5, 3)
                        group.append(child)
                    groups[owner].append(group)
            out["soul_skeletons"] = groups
            out["soul_offsets"] = [
                [(1.5 * math.cos(2 * math.pi * i / count),
                  1.5 * math.sin(2 * math.pi * i / count)) for i in range(count)]
                for count in range(1, 11)
            ]
        spawn_area = next(
            (m for m in source.mechanics if type(m).__name__ == "SpawnAreaEffect"), None,
        )
        if spawn_area is not None:
            spawn_area.on_spawn(source)
            out["spawn_areas"][source.card_stats.name] = entity(b.entities[max(b.entities)])
        if card in ("Balloon", "BombTower", "GiantSkeleton"):
            source = b.entities[max(b.entities)]
            name = source.card_stats.name
            source.take_damage(source.hitpoints)
            out["death_objects"][name] = entity(b.entities[max(b.entities)])
        if card in ('DarkWitch','SkeletonBalloon','LavaHound','ElixirGolem','BarbarianHut'):
            from payload_snapshot import export_payloads
            export_payloads(b.entities[units[0]['id']],b,out)
    if mirror_templates and 'Mirror' in cards:
        from mirror_snapshot import extend
        extend(out, cards)
    return out


def snapshot(b, cfg):
    from live_snapshot import live_entity, pending_casts

    rng = b.rng.getstate()[1]
    return json.dumps(
        dict(
            tick=b.tick,
            placement_signature=list(b._building_cache_signature),
            placement_masks={str(size):mask.reshape(-1).tolist()
                             for size,mask in b._building_placement_blocked_masks.items()},
            next_id=b.next_entity_id,
            champion_owners=[
                (owner, key, id)
                for (owner, key), id in b._champion_ability_owner_ids.items()
            ],
            players=[
                dict(
                    elixir=p.elixir,
                    hand=p.hand,
                    cycle=list(p.cycle_queue),
                    refill=p.next_card_refill_cooldown_ms,
                    last_card=p.last_played_card,
                    last_cost=p.last_played_card_cost,
                )
                for p in b.players
            ],
            entities=[live_entity(e, b, cfg) for e in b.entities.values()],
            pending_casts=pending_casts(b),
            sudden_death=b.sudden_death,
            rng=dict(state=list(rng[:-1]), index=rng[-1]),
            game_over=b.game_over,
            winner=b.winner,
            config=cfg,
        )
    )


def primitive_checks(cfg):
    b = initial(119)
    native = clasher_core.BattleState(snapshot(b, cfg))
    assert native.digest() == battle_digest(b)
    for _ in range(2000):
        assert native.rng_u32() == b.rng.getrandbits(32)
    for _ in range(2000):
        assert native.rng_random() == b.rng.random()
    for n in (1, 2, 3, 17, 2**31, 2**32 - 1):
        for _ in range(100):
            assert native.rng_below(n) == b.rng.randrange(n)
    r = random.Random(449)
    mismatches = 0
    for _ in range(2000):
        start = r.randrange(36), r.randrange(64)
        goal = r.randrange(36), r.randrange(64)
        costs = list(cfg["costs"])
        for _ in range(20):
            k = r.randrange(len(costs))
            costs[k] = max(50, costs[k])
        python = _native_grid_route(
            start,
            goal,
            lambda c: (
                costs[c[1] * 36 + c[0]] if 0 <= c[0] < 36 and 0 <= c[1] < 64 else None
            ),
        )
        rust = clasher_core.route(costs, start, goal)
        mismatches += python != rust
    return dict(
        mt_checks=4600, mt_mismatches=0, astar_cases=2000, astar_mismatches=mismatches
    )


def public_fields(b):
    return dict(
        tick=b.tick,
        next_id=b.next_entity_id,
        players=[
            dict(elixir=p.elixir, hand=list(p.hand), cycle=list(p.cycle_queue))
            for p in b.players
        ],
        entities=[
            dict(
                id=e.id,
                owner=e.player_id,
                x=e.position.x,
                y=e.position.y,
                hp=float(e.hitpoints),
                alive=e.is_alive,
                **{"class": type(e).__name__},
                target=e.target_id,
            )
            for e in b.entities.values()
        ],
        game_over=b.game_over,
        winner=b.winner,
    )


def native_fields(native):
    data = json.loads(native.snapshot())
    data.pop("config")
    data.pop("rng")
    for p in data["players"]:
        p.pop("refill")
        p.pop("last_card", None)
        p.pop("last_cost", None)
    keep = {"id", "owner", "x", "y", "hp", "alive", "class", "target"}
    data["entities"] = [
        {k: v for k, v in e.items() if k in keep} for e in data["entities"]
    ]
    return data


def scripted_actions(b, native, cfg, case, t):
    focus, game = CARDS[case % 4], case // 4
    actions = []
    action_mismatches = 0
    if t % 80 == 0:
        for seat in (0, 1):
            p = b.players[seat]
            order = [focus] + [c for c in CARDS if c != focus]
            card = next(
                (
                    c
                    for c in order
                    if c in p.hand and p.elixir + 1e-9 >= cfg["cards"][c]["cost"]
                ),
                None,
            )
            if card:
                x = 4.5 if (t // 80 + seat + game) % 2 == 0 else 13.5
                if game >= 3:
                    x += -1.0 if x < 9.0 else 1.0
                depth = game % 3
                y = (10.5 - depth) if seat == 0 else (21.5 + depth)
                pa = b.deploy_card(seat, card, Position(x, y))
                ra = native.apply_action(seat, card, x, y)
                action_mismatches += pa != ra
                actions.append([t, seat, card, x, y, pa, ra])
    return actions, action_mismatches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=12)
    parser.add_argument("--case", type=int)
    parser.add_argument("--ticks", type=int, default=2200)
    parser.add_argument(
        "--bisect-tick",
        type=int,
        help="Replay to N-1, capture each subsystem of tick N",
    )
    parser.add_argument("--skip-primitives", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ES / "results/stage1b_differential.json"
    )
    args = parser.parse_args()
    from diagnostics import detail, phase_step

    cfg = config()
    checks = primitive_checks(cfg) if not args.skip_primitives else {}
    print("primitives", checks, flush=True)
    results = []
    live_roots = []
    for case in [args.case] if args.case is not None else range(args.games):
        focus_index, game = case % 4, case // 4
        focus = CARDS[focus_index]
        b = initial(9700 + case)
        native = clasher_core.BattleState(snapshot(b, cfg))
        assert native.digest() == battle_digest(b), "initial import already differs"
        mismatches = action_mismatches = rng_mismatches = 0
        first = None
        python_cpu = rust_cpu = 0.0
        actions = []
        ticks = 0
        for t in range(args.bisect_tick or args.ticks):
            if b.game_over:
                break
            new_actions, rejected = scripted_actions(b, native, cfg, case, t)
            actions.extend(new_actions)
            action_mismatches += rejected
            if args.bisect_tick and t == args.bisect_tick - 1:
                phases = phase_step(b, native)
                args.output.write_text(json.dumps(phases, indent=2) + "\n")
                print({k: v["field_diff"] for k, v in phases.items()}, flush=True)
                return
            start = time.process_time()
            b.step()
            python_cpu += time.process_time() - start
            start = time.process_time()
            native.step()
            rust_cpu += time.process_time() - start
            ticks += 1
            pd, rd = battle_digest(b), native.digest()
            rng_words, rng_index = native.rng_state()
            rng_matches = tuple(rng_words) + (rng_index,) == b.rng.getstate()[1]
            rng_mismatches += not rng_matches
            if b.tick == 600 and case < 4:
                live_roots.append((case, b.clone(), native.clone()))
            mismatches += pd != rd
            if pd != rd or not rng_matches:
                if first is None:
                    first = dict(
                        tick=b.tick,
                        python_digest=pd,
                        rust_digest=rd,
                        **detail(b, native),
                    )
        final_native = json.loads(native.snapshot())
        result = dict(
            card=focus,
            game=game,
            ticks=ticks,
            rust_advanced_ticks=final_native["tick"],
            digest_mismatches=mismatches,
            action_mismatches=action_mismatches,
            rng_mismatches=rng_mismatches,
            first_difference=first,
            python_step_cpu=python_cpu,
            rust_step_cpu=rust_cpu,
            python_ticks_per_core_s=ticks / python_cpu,
            rust_ticks_per_core_s=final_native["tick"] / rust_cpu,
            same_trajectory_speed_comparison_valid=mismatches == 0
            and action_mismatches == 0
            and rng_mismatches == 0,
            actions=actions,
        )
        results.append(result)
        print(
            {
                k: v
                for k, v in result.items()
                if k not in ("actions", "first_difference")
            },
            flush=True,
        )
    # Clone cost measured on exactly imported pre-step public states with bodies.
    b = initial(1)
    for seat in (0, 1):
        for k, card in enumerate(CARDS):
            b.players[seat].elixir = 10
            assert b.deploy_card(
                seat, card, Position(2.5 + 4 * k, 10.5 if seat == 0 else 21.5)
            )
    native = clasher_core.BattleState(snapshot(b, cfg))
    assert native.digest() == battle_digest(b)

    def measure_clone(b, native):
        clones = {}
        for name, obj in [("python", b), ("rust", native)]:
            start = time.process_time()
            for _ in range(1000):
                clone = obj.clone()
            clones[name + "_us"] = (time.process_time() - start) * 1000
        parent_digest = native.digest()
        cloned_python, cloned_native = b.clone(), native.clone()
        assert cloned_native.digest() == parent_digest
        for _ in range(20):
            cloned_python.step()
            cloned_native.step()
            assert cloned_native.digest() == battle_digest(cloned_python), (
                "live clone continuation differs"
            )
        assert native.digest() == parent_digest
        assert battle_digest(b) == parent_digest
        return clones

    clones = measure_clone(b, native)
    live_clones = [
        dict(
            case=case,
            tick=root.tick,
            entities=len(root.entities),
            **measure_clone(root, rust),
        )
        for case, root, rust in live_roots
        if all(r["same_trajectory_speed_comparison_valid"] for r in results)
    ]
    out = dict(
        primitives=checks,
        scenarios=results,
        clone=clones,
        clone_entities=len(b.entities),
        live_clones=live_clones,
        python_source="src/clasher, pure Python P1-P5 reference",
        note="Raw timing on divergent trajectories is diagnostic, not an accepted speed gate.",
        per_card_ticks={
            c: sum(r["ticks"] for r in results if r["card"] == c) for c in CARDS
        },
        parity_gate=(
            all(
                sum(r["ticks"] for r in results if r["card"] == c) >= 2000
                for c in CARDS
            )
            and all(
                r["digest_mismatches"] == 0
                and r["action_mismatches"] == 0
                and r["rng_mismatches"] == 0
                for r in results
            )
        ),
        clone_gate=clones["rust_us"] < 20
        and all(c["rust_us"] < 20 for c in live_clones),
    )
    out["total_ticks"] = sum(r["ticks"] for r in results)
    out["ticks_per_core_s"] = {
        name: out["total_ticks"] / sum(r[name + "_step_cpu"] for r in results)
        for name in ("python", "rust")
    }
    out["speed_ratio"] = sum(r["python_step_cpu"] for r in results) / sum(
        r["rust_step_cpu"] for r in results
    )
    out["speed_gate"] = (
        out["parity_gate"]
        and sum(r["python_step_cpu"] for r in results)
        / sum(r["rust_step_cpu"] for r in results)
        >= 30
    )
    out["stage2_go"] = (
        len(results) >= 24
        and out["parity_gate"]
        and out["speed_gate"]
        and out["clone_gate"]
    )
    path = args.output
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "scenarios"}), flush=True)
    if not out["stage2_go"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
