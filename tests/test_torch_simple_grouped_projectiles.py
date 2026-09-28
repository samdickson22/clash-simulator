from __future__ import annotations

from dataclasses import fields, replace

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.dynamic_spells import create_spell_from_json
from clasher.kinematics import (
    logic_speed_to_tiles_per_second,
    tiles_per_second_to_logic_speed,
    tiles_to_logic_units,
)
from clasher.torch_sim.simple_cast_rng import CPUExactCastRNG
from clasher.torch_sim.simple_grouped_geometry import FastGroupedGeometry
from clasher.torch_sim.simple_grouped_projectiles import (
    FastGroupedCastCommands,
    FastGroupedProjectileState,
    admit_fast_grouped_casts,
    allocate_fast_grouped_casts_,
    collect_fast_grouped_impacts_diagnostic_,
    resolve_fast_grouped_impacts_,
    step_fast_grouped_projectiles_,
)
from clasher.torch_sim.simple_modifiers import FastModifierState
from clasher.torch_sim.simple_state import FastGymState


def _device(device):
    if device == "mps" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    return device


def _commands(pool, *, count=1, delays=True):
    b, _, w, m = pool.member_active.shape

    def tensor(value, dtype=torch.int64):
        return torch.full((b, count), value, dtype=dtype, device=pool.device)

    return FastGroupedCastCommands(
        ready=tensor(True, torch.bool),
        owner=tensor(0),
        source_card_id=tensor(1),
        damage=tensor(10, torch.float32),
        crown_damage=tensor(3, torch.float32),
        radius_units=tensor(1500),
        speed_units_per_tick=tensor(500),
        hits_air=tensor(True, torch.bool),
        hits_ground=tensor(True, torch.bool),
        origin_units=torch.zeros((b, count, 2), dtype=torch.int64, device=pool.device),
        destination_units=torch.zeros(
            (b, count, w, m, 2), dtype=torch.int64, device=pool.device
        ),
        launch_delay_ticks=(
            torch.arange(w, device=pool.device)[None, None, :, None]
            .expand(b, count, w, m)
            .clone()
            if delays
            else torch.zeros((b, count, w, m), dtype=torch.int64, device=pool.device)
        ),
    )


def _step(gym, pool, modifiers=None, receivable=None):
    b, e = gym.active.shape
    return step_fast_grouped_projectiles_(
        gym,
        pool,
        entity_collision_radius_units=torch.full(
            (b, e), 100, dtype=torch.int64, device=pool.device
        ),
        entity_is_air=torch.zeros((b, e), dtype=torch.bool, device=pool.device),
        entity_is_crown_tower=torch.zeros((b, e), dtype=torch.bool, device=pool.device),
        entity_area_receivable=(
            torch.ones(
                (b, pool.active.shape[1], e), dtype=torch.bool, device=pool.device
            )
            if receivable is None
            else receivable
        ),
        modifiers=modifiers,
    )


def _gym(device, e=2):
    gym = FastGymState.empty(1, max_entities=e, device=device)
    gym.active[:] = True
    gym.stable_id[0] = torch.arange(1, e + 1, device=device)
    gym.owner[:] = 1
    gym.hp[:] = gym.max_hp[:] = 1000
    return gym


@pytest.mark.parametrize("device", ["cpu", "mps"])
@pytest.mark.parametrize("owner", [0, 1])
def test_actual_arrows_every_tick_matches_scalar(device, owner):
    device = _device(device)
    loader = CardDataLoader()
    spell = create_spell_from_json(
        loader.get_card("Arrows")._raw_entry, loader.load_card_definitions()
    )
    battle = BattleState()
    battle.rng.seed(1279011)
    towers = list(battle.entities.values())
    assert len(towers) == 6
    pool = FastGroupedProjectileState.empty(
        1, max_casts=1, max_hit_records=6, device=device
    )
    gym = FastGymState.empty(1, max_entities=6, device=device)
    for slot, tower in enumerate(towers):
        gym.active[0, slot] = True
        gym.stable_id[0, slot] = tower.id
        gym.kind[0, slot] = tower.entity_kind
        gym.owner[0, slot] = tower.player_id
        gym.x_units[0, slot] = tiles_to_logic_units(tower.position.x)
        gym.y_units[0, slot] = tiles_to_logic_units(tower.position.y)
        gym.hp[0, slot] = gym.max_hp[0, slot] = tower.hitpoints
    target = Position(3.5, 25.5) if owner == 0 else Position(14.5, 6.5)
    preflight = admit_fast_grouped_casts(
        pool, torch.ones((1, 1), dtype=torch.bool, device=device)
    )
    rng = CPUExactCastRNG([battle.rng])
    angles = rng.draw_angles(preflight.accepted).angles.reshape(1, 1, 3, 10)
    geometry = FastGroupedGeometry.compile(
        pattern="grouped_ring",
        projectile_count=10,
        spread_radius_units=tiles_to_logic_units(spell.spread_radius),
        projectile_radius_units=tiles_to_logic_units(spell.radius),
        device=device,
    )
    targets = torch.tensor(
        [tiles_to_logic_units(target.x), tiles_to_logic_units(target.y)], device=device
    ).expand(1, 1, 3, 2)
    destinations = geometry.destinations(
        angles=angles,
        target_units=targets,
        owner=torch.full((1, 1, 3), owner, dtype=torch.int64, device=device),
    )
    origin = spell._get_launch_position(battle, owner)
    commands = replace(
        _commands(pool),
        owner=torch.tensor([[owner]], device=device),
        damage=torch.tensor([[spell.damage]], dtype=torch.float32, device=device),
        crown_damage=torch.tensor(
            [[spell.crown_tower_damage]], dtype=torch.float32, device=device
        ),
        radius_units=torch.tensor(
            [[tiles_to_logic_units(spell.radius)]], device=device
        ),
        speed_units_per_tick=torch.tensor(
            [[tiles_per_second_to_logic_speed(spell.travel_speed)]], device=device
        ),
        origin_units=torch.tensor(
            [[[tiles_to_logic_units(origin.x), tiles_to_logic_units(origin.y)]]],
            device=device,
        ),
        destination_units=destinations,
        launch_delay_ticks=(
            torch.arange(3, device=device) * round(spell.damage_wave_interval / 0.05)
        )[None, None, :, None]
        .expand(1, 1, 3, 10)
        .clone(),
    )
    allocate_fast_grouped_casts_(pool, commands)
    before = set(battle.entities)
    spell.cast(battle, owner, target)
    projectiles = [p for key, p in battle.entities.items() if key not in before]
    assert rng.state.python_state(0) == battle.rng.getstate()
    radius = torch.tensor(
        [[tiles_to_logic_units(t.get_collision_radius()) for t in towers]],
        device=device,
    )
    for tick in range(1, 61):
        for projectile in projectiles:
            projectile.update(0.05, battle)
        step_fast_grouped_projectiles_(
            gym,
            pool,
            entity_collision_radius_units=radius,
            entity_is_air=torch.zeros((1, 6), dtype=torch.bool, device=device),
            entity_is_crown_tower=torch.ones((1, 6), dtype=torch.bool, device=device),
            entity_area_receivable=torch.tensor(
                [[[t.can_receive_area_damage("Arrows") for t in towers]]], device=device
            ),
        )
        assert gym.hp[0].cpu().tolist() == [t.hitpoints for t in towers], tick
        assert pool.member_active.flatten().cpu().tolist() == [
            p.is_alive for p in projectiles
        ], tick
        assert pool.position_units.reshape(30, 2).cpu().tolist() == [
            [tiles_to_logic_units(p.position.x), tiles_to_logic_units(p.position.y)]
            for p in projectiles
        ], tick
    assert not pool.active.any()


@pytest.mark.parametrize("device", ["cpu", "mps"])
def test_same_wave_dedup_and_simultaneous_wave_shields(device):
    device = _device(device)
    pool = FastGroupedProjectileState.empty(
        1, max_casts=1, max_hit_records=2, device=device
    )
    gym = _gym(device)
    modifiers = FastModifierState.empty(1, max_entities=2, device=pool.device)
    modifiers.shield[:] = modifiers.max_shield[:] = 15
    allocate_fast_grouped_casts_(pool, _commands(pool, delays=False))
    result = _step(gym, pool, modifiers)
    # Thirty overlapping circles become three hits, never one hit or thirty.
    assert result.hit.sum((1, 2, 3)).cpu().tolist() == [[3, 3]]
    assert modifiers.shield.cpu().tolist() == [[0, 0]]
    assert gym.hp.cpu().tolist() == [[990, 990]]


@pytest.mark.parametrize("device", ["cpu", "mps"])
def test_atomic_capacity_reset_and_slot_reuse(device):
    device = _device(device)
    pool = FastGroupedProjectileState.empty(
        1, max_casts=1, max_hit_records=2, device=device
    )
    gym = _gym(device)
    result = allocate_fast_grouped_casts_(pool, _commands(pool, count=2))
    assert result.accepted.cpu().tolist() == [[True, False]]
    assert pool.member_active.sum() == 30
    for _ in range(3):
        _step(gym, pool)
    assert gym.hp.cpu().tolist() == [[970, 970]]
    assert not pool.active.any()
    allocate_fast_grouped_casts_(pool, _commands(pool, delays=False))
    assert pool.hit_stable_ids.count_nonzero() == 0
    _step(gym, pool)
    assert gym.hp.cpu().tolist() == [[940, 940]]
    pool.reset_rows_(torch.ones(1, dtype=torch.bool, device=device))
    assert pool.next_cast_id.tolist() == [1]
    for descriptor in fields(pool):
        value = getattr(pool, descriptor.name)
        if isinstance(value, torch.Tensor) and descriptor.name != "next_cast_id":
            assert value.count_nonzero() == 0


@pytest.mark.parametrize("device", ["cpu", "mps"])
def test_owner_guard_boundary_and_stable_identity(device):
    device = _device(device)
    pool = FastGroupedProjectileState.empty(
        1, max_casts=1, max_hit_records=2, device=device
    )
    gym = _gym(device)
    gym.owner[0, 0] = 0
    gym.x_units[0, 1] = 1600  # tangent to radius1500 + target100: excluded
    commands = _commands(pool)
    allocate_fast_grouped_casts_(pool, commands)
    _step(gym, pool)
    assert gym.hp.cpu().tolist() == [[1000, 1000]]
    gym.x_units[0, 1] = 1599
    blocked = torch.zeros((1, 1, 2), dtype=torch.bool, device=device)
    _step(gym, pool, receivable=blocked)
    _step(gym, pool)
    assert gym.hp.cpu().tolist() == [[1000, 990]]


@pytest.mark.parametrize("device", ["cpu", "mps"])
@pytest.mark.parametrize("reuse", [False, True])
def test_group_membership_follows_identity_not_physical_slot(device, reuse):
    device = _device(device)
    pool = FastGroupedProjectileState.empty(
        1, max_casts=1, waves=1, members=2, max_hit_records=2, device=device
    )
    gym = _gym(device)
    gym.owner[0, 1] = 0
    commands = _commands(pool, delays=False)
    commands.destination_units[0, 0, 0, 1, 0] = 1000
    allocate_fast_grouped_casts_(pool, commands)
    _step(gym, pool)
    assert gym.hp[0, 0] == 990
    if reuse:
        gym.stable_id[0, 0] = 99
    _step(gym, pool)
    assert gym.hp[0, 0] == (980 if reuse else 990)


@pytest.mark.parametrize("device", ["cpu", "mps"])
def test_reused_cast_slot_keeps_chronological_shield_order(device):
    device = _device(device)
    pool = FastGroupedProjectileState.empty(
        1, max_casts=2, waves=1, members=1, max_hit_records=2, device=device
    )
    gym = _gym(device)
    old = _commands(pool, count=2, delays=False)
    old.launch_delay_ticks[0, 1] = 1
    old.damage[0, 1] = 20
    allocate_fast_grouped_casts_(pool, old)
    _step(gym, pool)
    assert pool.active.cpu().tolist() == [[False, True]]
    allocate_fast_grouped_casts_(pool, _commands(pool, delays=False))
    assert pool.cast_id.cpu().tolist() == [[3, 2]]
    modifiers = FastModifierState.empty(1, max_entities=2, device=pool.device)
    modifiers.shield[:] = modifiers.max_shield[:] = 15
    _step(gym, pool, modifiers)
    # Old 20 breaks shield, new 10 reaches HP. Reversed slot order would
    # absorb both hits and incorrectly leave HP unchanged.
    assert gym.hp.cpu().tolist() == [[980, 980]]


@pytest.mark.parametrize("device", ["cpu", "mps"])
def test_recycled_identity_ledger_overflow_is_explicit(device):
    device = _device(device)
    pool = FastGroupedProjectileState.empty(
        1, max_casts=1, waves=1, members=3, max_hit_records=2, device=device
    )
    gym = _gym(device)
    gym.owner[0, 1] = 0
    commands = _commands(pool, delays=False)
    commands.launch_delay_ticks[0, 0, 0] = torch.arange(3, device=pool.device)
    allocate_fast_grouped_casts_(pool, commands)
    for identity in (1, 99):
        gym.stable_id[0, 0] = identity
        result = _step(gym, pool)
        assert not result.hit_capacity_rejected.any()
    gym.stable_id[0, 0] = 100
    result = _step(gym, pool)
    assert result.hit_capacity_rejected.sum() == 1
    assert gym.hp[0, 0] == 980


@pytest.mark.parametrize("device", ["cpu", "mps"])
def test_invalid_cast_does_not_mutate_pool(device):
    device = _device(device)
    pool = FastGroupedProjectileState.empty(
        1, max_casts=1, max_hit_records=2, device=device
    )
    commands = _commands(pool)
    commands.destination_units[0, 0, 0, 0, 0] = torch.iinfo(torch.int64).min
    before = {
        f.name: getattr(pool, f.name).clone()
        for f in fields(pool)
        if isinstance(getattr(pool, f.name), torch.Tensor)
    }
    with pytest.raises(ValueError, match="invalid ready"):
        allocate_fast_grouped_casts_(pool, commands)
    for name, value in before.items():
        assert torch.equal(getattr(pool, name), value)


def _collect(gym, pool):
    b, e = gym.hp.shape
    return collect_fast_grouped_impacts_diagnostic_(
        gym,
        pool,
        entity_collision_radius_units=torch.full(
            (b, e), 100, dtype=torch.int64, device=pool.device
        ),
        entity_is_air=torch.zeros((b, e), dtype=torch.bool, device=pool.device),
        entity_is_crown_tower=torch.zeros((b, e), dtype=torch.bool, device=pool.device),
        entity_area_receivable=torch.ones(
            (b, pool.active.shape[1], e), dtype=torch.bool, device=pool.device
        ),
    )


@pytest.mark.parametrize("device", ["cpu", "mps"])
def test_shared_pre_damage_collection_preserves_group_commitment_after_lethal_hit(
    device,
):
    device = _device(device)
    pool = FastGroupedProjectileState.empty(
        1, max_casts=1, waves=1, members=10, max_hit_records=2, device=device
    )
    gym = _gym(device)
    allocate_fast_grouped_casts_(pool, _commands(pool, delays=False))
    modifiers = FastModifierState.empty(1, max_entities=2, device=pool.device)
    modifiers.shield[:] = modifiers.max_shield[:] = 15
    hp_before, shield_before = gym.hp.clone(), modifiers.shield.clone()
    # An ordinary-like event snapshots the same live targets. This fixture
    # tests an explicit deferred seam, not the current scalar object-phase
    # scheduling (which resolves objects immediately in object-ID order).
    ordinary_targets = gym.active & (gym.hp > 0)
    ordinary_damage = ordinary_targets.float() * 2000
    pending = _collect(gym, pool)
    assert torch.equal(gym.hp, hp_before)
    assert torch.equal(modifiers.shield, shield_before)
    assert pending.hit.sum((1, 2, 3)).cpu().tolist() == [[1, 1]]
    assert pool.hit_stable_ids[0, 0, 0].sort().values.cpu().tolist() == [1, 2]
    # Earlier ordinary event kills the targets before grouped resolution.
    gym.hp.sub_(ordinary_damage).clamp_min_(0)
    result = resolve_fast_grouped_impacts_(gym, pending)
    assert result.hit.sum((1, 2, 3)).cpu().tolist() == [[1, 1]]
    assert result.damage_by_entity.cpu().tolist() == [[10, 10]]
    assert gym.hp.cpu().tolist() == [[0, 0]]
    # Re-querying live HP at this point would have discarded committed hits.
    assert not (gym.active & (gym.hp > 0)).any()


@pytest.mark.parametrize("device", ["cpu", "mps"])
def test_pending_impacts_snapshot_reused_cast_and_reject_replaced_target(device):
    device = _device(device)
    pool = FastGroupedProjectileState.empty(
        1, max_casts=1, waves=1, members=1, max_hit_records=2, device=device
    )
    gym = _gym(device)
    allocate_fast_grouped_casts_(pool, _commands(pool, delays=False))
    pending = _collect(gym, pool)
    replacement = _commands(pool, delays=False)
    replacement.damage[:] = 99
    allocate_fast_grouped_casts_(pool, replacement)
    assert pending.cast_id.cpu().tolist() == [[1]]
    assert pool.cast_id.cpu().tolist() == [[2]]
    assert pending.damage.flatten().cpu().tolist() == [10, 10]
    gym.stable_id[0, 0] = 100
    hp_before = gym.hp.clone()
    with pytest.raises(ValueError, match="identity changed"):
        resolve_fast_grouped_impacts_(gym, pending)
    assert torch.equal(gym.hp, hp_before)


@pytest.mark.parametrize("device", ["cpu", "mps"])
@pytest.mark.parametrize("owner", [0, 1])
def test_lethal_first_member_excludes_later_waves_in_live_scalar_object_phase(
    device, owner
):
    device = _device(device)
    loader = CardDataLoader()
    template = create_spell_from_json(
        loader.get_card("Arrows")._raw_entry, loader.load_card_definitions()
    )
    # Force all real grouped members to arrive this tick, exposing the live
    # object's immediate HP/ledger ordering without a full-battle claim.
    spell = replace(
        template,
        damage_wave_interval=0,
        travel_speed=logic_speed_to_tiles_per_second(50000),
    )
    battle = BattleState()
    battle.rng.seed(1279011)
    towers = list(battle.entities.values())
    target = next(t for t in towers if t.player_id != owner)
    target.hitpoints = 10
    gym = FastGymState.empty(1, max_entities=6, device=device)
    for slot, tower in enumerate(towers):
        gym.active[0, slot] = True
        gym.stable_id[0, slot] = tower.id
        gym.owner[0, slot] = tower.player_id
        gym.kind[0, slot] = tower.entity_kind
        gym.hp[0, slot] = gym.max_hp[0, slot] = tower.hitpoints
        gym.x_units[0, slot] = tiles_to_logic_units(tower.position.x)
        gym.y_units[0, slot] = tiles_to_logic_units(tower.position.y)
    initial = set(battle.entities)
    spell.cast(battle, owner, target.position)
    projectiles = [p for key, p in battle.entities.items() if key not in initial]
    pool = FastGroupedProjectileState.empty(
        1, max_casts=1, max_hit_records=6, device=device
    )
    destinations = torch.tensor(
        [
            [
                [
                    [
                        tiles_to_logic_units(p.target_position.x),
                        tiles_to_logic_units(p.target_position.y),
                    ]
                    for p in projectiles
                ]
            ]
        ],
        device=device,
    ).reshape(1, 1, 3, 10, 2)
    origin = projectiles[0].position
    commands = replace(
        _commands(pool, delays=False),
        owner=torch.tensor([[owner]], device=device),
        damage=torch.tensor([[spell.damage]], dtype=torch.float32, device=device),
        crown_damage=torch.tensor(
            [[spell.crown_tower_damage]], dtype=torch.float32, device=device
        ),
        speed_units_per_tick=torch.tensor([[50000]], device=device),
        radius_units=torch.tensor(
            [[tiles_to_logic_units(spell.radius)]], device=device
        ),
        origin_units=torch.tensor(
            [[[tiles_to_logic_units(origin.x), tiles_to_logic_units(origin.y)]]],
            device=device,
        ),
        destination_units=destinations,
    )
    allocate_fast_grouped_casts_(pool, commands)
    all_ids = set(battle.entities)
    assert not battle._defer_projectile_impacts
    battle._run_object_phase(0.05, all_ids, all_ids)
    result = step_fast_grouped_projectiles_(
        gym,
        pool,
        entity_collision_radius_units=torch.tensor(
            [[tiles_to_logic_units(t.get_collision_radius()) for t in towers]],
            device=device,
        ),
        entity_is_air=torch.zeros((1, 6), dtype=torch.bool, device=device),
        entity_is_crown_tower=torch.ones((1, 6), dtype=torch.bool, device=device),
        entity_area_receivable=torch.ones((1, 1, 6), dtype=torch.bool, device=device),
    )
    assert gym.hp[0].cpu().tolist() == [t.hitpoints for t in towers]
    assert result.hit.sum() == 1
    for wave in range(3):
        scalar_ids = projectiles[wave * 10].damage_group_hit_entity_ids
        native_ids = set(pool.hit_stable_ids[0, 0, wave].cpu().tolist()) - {0}
        assert native_ids == scalar_ids
    assert projectiles[0].damage_group_hit_entity_ids == {target.id}
    assert projectiles[10].damage_group_hit_entity_ids == set()
    assert projectiles[20].damage_group_hit_entity_ids == set()
