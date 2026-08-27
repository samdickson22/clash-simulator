from __future__ import annotations

import inspect
import json
from dataclasses import fields, replace
from pathlib import Path

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.catalog import MECHANIC_OPCODE, TensorCardCatalog
from clasher.torch_sim.simple_effects import FAST_STATUS_SLOW, FAST_STATUS_STUN
from clasher.torch_sim.simple_impulse import compute_fast_radial_impulse
from clasher.torch_sim.simple_triggered_impacts import (
    FAST_CENTER_SELF,
    FAST_CENTER_TARGET,
    FAST_ORIGIN_EFFECT,
    FAST_ORIGIN_MECHANIC,
    FAST_ORIGIN_RAW_PROJECTILE,
    FAST_RECIPIENT_SELF,
    FAST_TRIGGER_ATTACK_COMMIT,
    FAST_TRIGGER_DEATH,
    FAST_TRIGGER_DEPLOY_COMPLETE,
    FAST_TRIGGER_IMPACT,
    FastTriggeredImpactCatalog,
    FastTriggeredImpactEvents,
    FastTriggeredImpactTargets,
    clone_fast_triggered_events,
    resolve_fast_triggered_impacts,
    triggered_commands_to_effect_state,
    triggered_commands_to_impulse_inputs,
)

CARDS = (
    "Bowler",
    "ElectroWizard",
    "Fireball",
    "Firecracker",
    "IceGolemite",
    "IceWizard",
    "MegaKnight",
    "Rocket",
    "Snowball",
    "Tornado",
)


def _device(requested: str) -> str:
    if requested == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return requested


def _catalog(
    device: str = "cpu",
) -> tuple[TensorCardCatalog, FastTriggeredImpactCatalog]:
    loader = CardDataLoader()
    source = TensorCardCatalog.compile(loader, CARDS, device=device)
    return source, FastTriggeredImpactCatalog.compile(source, loader)


def _rows(
    source: TensorCardCatalog,
    catalog: FastTriggeredImpactCatalog,
    name: str,
) -> list[dict[str, object]]:
    card_id = source.name_to_id[name]
    count = int(catalog.descriptor_count[card_id].item())
    names = (
        "trigger",
        "center",
        "recipient",
        "origin",
        "origin_opcode",
        "damage",
        "radius_units",
        "status_kind",
        "status_duration_ticks",
        "lifetime_ticks",
        "damage_interval_ticks",
        "initial_damage_delay_ticks",
        "max_damage_hits",
        "max_status_scans",
        "hits_air",
        "hits_ground",
        "affects_hidden",
        "tower_damage_multiplier",
        "building_damage_multiplier",
        "impulse_units",
        "impulse_push_speed_factor",
        "impulse_attract_percentage",
        "impulse_interval_ticks",
        "impulse_scan_count",
    )
    return [
        {field: getattr(catalog, field)[card_id, slot].item() for field in names}
        for slot in range(count)
    ]


@pytest.mark.parametrize("requested_device", ("cpu", "cuda"))
def test_live_serialized_trigger_profiles_compile_exactly(
    requested_device: str,
) -> None:
    source, catalog = _catalog(_device(requested_device))

    for name in CARDS:
        card_id = source.name_to_id[name]
        assert bool(catalog.supported[card_id])
        assert not bool(catalog.malformed[card_id])
        assert not bool(catalog.duplicate[card_id])

    firecracker = _rows(source, catalog, "Firecracker")
    assert firecracker == [
        {
            **firecracker[0],
            "trigger": FAST_TRIGGER_ATTACK_COMMIT,
            "center": FAST_CENTER_TARGET,
            "recipient": FAST_RECIPIENT_SELF,
            "origin": FAST_ORIGIN_MECHANIC,
            "origin_opcode": MECHANIC_OPCODE["AttackRecoil"],
            "damage": 0.0,
            "radius_units": 0,
            "impulse_units": 1000,
        }
    ]

    bowler = _rows(source, catalog, "Bowler")[0]
    assert bowler["trigger"] == FAST_TRIGGER_IMPACT
    assert bowler["center"] == FAST_CENTER_TARGET
    assert bowler["origin"] == FAST_ORIGIN_RAW_PROJECTILE
    assert bowler["damage"] == 289.0
    assert bowler["radius_units"] == 1800
    assert bowler["impulse_units"] == 1000
    assert bowler["hits_air"] is False
    assert bowler["hits_ground"] is True

    projectile_expectations = {
        "Fireball": (688.0, 2500, 1000, 172.0),
        "Snowball": (179.0, 2500, 1800, 45.0),
        "Rocket": (1484.0, 2000, 1800, 342.0),
    }
    for name, (damage, radius, push, tower_damage) in projectile_expectations.items():
        row = _rows(source, catalog, name)[0]
        assert row["trigger"] == FAST_TRIGGER_IMPACT
        assert row["origin"] == FAST_ORIGIN_EFFECT
        assert row["damage"] == damage
        assert row["radius_units"] == radius
        assert row["impulse_units"] == push
        assert float(row["tower_damage_multiplier"]) * damage == pytest.approx(
            tower_damage, abs=1e-4
        )
    snowball = _rows(source, catalog, "Snowball")[0]
    assert snowball["status_kind"] == FAST_STATUS_SLOW
    assert snowball["status_duration_ticks"] == 60

    tornado = _rows(source, catalog, "Tornado")[0]
    assert tornado["trigger"] == FAST_TRIGGER_IMPACT
    assert tornado["damage"] == 84.0
    assert tornado["radius_units"] == 5500
    assert tornado["lifetime_ticks"] == 21
    assert tornado["damage_interval_ticks"] == 11
    assert tornado["initial_damage_delay_ticks"] == 11
    assert tornado["max_damage_hits"] == 1
    assert tornado["impulse_push_speed_factor"] == 100
    assert tornado["impulse_attract_percentage"] == 360
    assert tornado["impulse_scan_count"] == 20
    assert float(tornado["tower_damage_multiplier"]) * 84.0 == pytest.approx(25.0)

    electro = _rows(source, catalog, "ElectroWizard")[0]
    ice = _rows(source, catalog, "IceWizard")[0]
    assert (electro["trigger"], electro["center"]) == (
        FAST_TRIGGER_DEPLOY_COMPLETE,
        FAST_CENTER_SELF,
    )
    assert (electro["damage"], electro["radius_units"]) == (192.0, 3000)
    assert (electro["status_kind"], electro["status_duration_ticks"]) == (
        FAST_STATUS_STUN,
        10,
    )
    assert float(electro["tower_damage_multiplier"]) == 0.0
    assert (ice["damage"], ice["radius_units"]) == (84.0, 3000)
    assert (ice["status_kind"], ice["status_duration_ticks"]) == (
        FAST_STATUS_SLOW,
        50,
    )

    mega = _rows(source, catalog, "MegaKnight")
    assert len(mega) == 2
    assert {int(row["radius_units"]) for row in mega} == {1000, 2200}
    appearance = next(row for row in mega if row["damage"] == 430.0)
    character_push = next(row for row in mega if row["damage"] == 0.0)
    assert appearance["impulse_units"] == 1000
    assert character_push["impulse_units"] == 1000
    assert all(row["trigger"] == FAST_TRIGGER_DEPLOY_COMPLETE for row in mega)

    ice_golem = _rows(source, catalog, "IceGolemite")
    assert len(ice_golem) == 2
    nova = next(row for row in ice_golem if row["damage"] == 84.0)
    chill = next(row for row in ice_golem if row["status_kind"] == FAST_STATUS_SLOW)
    assert nova["trigger"] == FAST_TRIGGER_DEATH
    assert (nova["radius_units"], nova["hits_air"], nova["hits_ground"]) == (
        2000,
        True,
        True,
    )
    assert chill["status_duration_ticks"] == 40
    assert chill["lifetime_ticks"] == 20
    assert chill["affects_hidden"] is True


def _event_fixture(
    source: TensorCardCatalog,
    device: torch.device,
) -> FastTriggeredImpactEvents:
    events = FastTriggeredImpactEvents.empty(1, max_events=4, device=device)
    events.active[0] = True
    events.card_id[0] = torch.tensor(
        [
            source.name_to_id["Firecracker"],
            source.name_to_id["Bowler"],
            source.name_to_id["Tornado"],
            source.name_to_id["ElectroWizard"],
        ],
        device=device,
    )
    events.trigger[0] = torch.tensor(
        [
            FAST_TRIGGER_ATTACK_COMMIT,
            FAST_TRIGGER_IMPACT,
            FAST_TRIGGER_IMPACT,
            FAST_TRIGGER_DEPLOY_COMPLETE,
        ],
        dtype=torch.int8,
        device=device,
    )
    events.source_owner[0] = 0
    events.source_entity_id[0] = torch.tensor(
        [11, 12, 0, 14], dtype=torch.int64, device=device
    )
    events.target_entity_id[0] = torch.tensor(
        [21, 22, 0, 0], dtype=torch.int64, device=device
    )
    events.source_x_units[0] = torch.tensor(
        [1000, 0, 9000, 8000], dtype=torch.int32, device=device
    )
    events.source_y_units[0] = 1000
    events.target_x_units[0] = torch.tensor(
        [2000, 30_000, 10_000, 7000], dtype=torch.int32, device=device
    )
    events.target_y_units[0] = 1000
    events.self_x_units[0] = torch.tensor(
        [1000, 0, 9000, 7000], dtype=torch.int32, device=device
    )
    events.self_y_units[0] = 1000
    events.repeat_count[0, 2] = 2
    return events


def _targets(device: torch.device) -> FastTriggeredImpactTargets:
    shape = (1, 6)
    return FastTriggeredImpactTargets(
        active=torch.ones(shape, dtype=torch.bool, device=device),
        stable_id=torch.tensor(
            [[11, 21, 22, 31, 32, 33]], dtype=torch.int64, device=device
        ),
        owner=torch.tensor([[0, 1, 1, 1, 1, 1]], dtype=torch.int8, device=device),
        x_units=torch.tensor(
            [[1000, 32_000, 32_400, 11_000, 15_600, 10_000]],
            dtype=torch.int32,
            device=device,
        ),
        y_units=torch.full(shape, 1000, dtype=torch.int32, device=device),
        collision_radius_units=torch.tensor(
            [[500, 500, 500, 500, 200, 500]], dtype=torch.int32, device=device
        ),
        base_speed_units_per_tick=torch.tensor(
            [[90, 60, 90, 60, 120, 0]], dtype=torch.int32, device=device
        ),
        is_air=torch.tensor(
            [[False, False, False, False, True, False]],
            dtype=torch.bool,
            device=device,
        ),
        is_building=torch.tensor(
            [[False, False, False, False, False, True]],
            dtype=torch.bool,
            device=device,
        ),
        area_receivable=torch.ones(shape, dtype=torch.bool, device=device),
        effect_receivable_affects_hidden=torch.ones(
            shape, dtype=torch.bool, device=device
        ),
        max_displacement_units=torch.full(shape, -1, dtype=torch.int32, device=device),
    )


@pytest.mark.parametrize("requested_device", ("cpu", "cuda"))
def test_fixed_resolution_geometry_effect_and_impulse_adapters(
    requested_device: str,
) -> None:
    device = torch.device(_device(requested_device))
    source, catalog = _catalog(str(device))
    events = _event_fixture(source, device)
    preserved = clone_fast_triggered_events(events)

    commands = resolve_fast_triggered_impacts(catalog, events)
    effects = triggered_commands_to_effect_state(commands)
    impulse_inputs = triggered_commands_to_impulse_inputs(commands, _targets(device))
    result = compute_fast_radial_impulse(impulse_inputs)
    replay_commands = resolve_fast_triggered_impacts(
        catalog, clone_fast_triggered_events(events)
    )
    replay_effects = triggered_commands_to_effect_state(replay_commands)
    replay_result = compute_fast_radial_impulse(
        triggered_commands_to_impulse_inputs(replay_commands, _targets(device))
    )

    assert commands.active.sum().item() == 4
    assert effects.active.sum().item() == 3
    active_damage = effects.damage[effects.active].tolist()
    assert active_damage == [289.0, 84.0, 192.0]
    # Firecracker recoils one tile away from its committed target.
    assert result.dx_units[0, 0].item() == -1000
    # Bowler hits a ground target at 5,000 and includes target hitbox geometry;
    # the ground target at 7,700 is outside 1,800 + 500. The air target is not
    # eligible even though its hitbox touches the circle.
    assert result.dx_units[0, 1].item() == 1000
    assert result.dx_units[0, 2].item() == 0
    # Two Tornado scans pull a speed-60 target by 2 * trunc(60 * 360%).
    assert result.dx_units[0, 3].item() == -432
    # The 5.5-tile radius plus hitbox includes the speed-120 air target.
    assert result.dx_units[0, 4].item() == -864
    # Buildings receive damage/status through FastEffectState but never move.
    assert result.dx_units[0, 5].item() == 0
    assert not result.dy_units.any()
    for field in fields(effects):
        if field.name != "device":
            assert torch.equal(
                getattr(effects, field.name), getattr(replay_effects, field.name)
            )
    assert torch.equal(result.dx_units, replay_result.dx_units)
    assert torch.equal(result.dy_units, replay_result.dy_units)
    assert torch.equal(result.affected, replay_result.affected)

    coincident_targets = _targets(device)
    coincident_targets.x_units[0, 0] = events.target_x_units[0, 0]
    coincident = compute_fast_radial_impulse(
        triggered_commands_to_impulse_inputs(commands, coincident_targets)
    )
    assert coincident.dx_units[0, 0].item() == 0
    assert coincident.dy_units[0, 0].item() == 0

    for field in fields(events):
        assert torch.equal(getattr(events, field.name), getattr(preserved, field.name))


def test_cpu_replay_is_exact_and_wrong_triggers_or_ids_fail_closed() -> None:
    source, catalog = _catalog()
    events = _event_fixture(source, torch.device("cpu"))
    replay = clone_fast_triggered_events(events)
    events.trigger[0, 1] = FAST_TRIGGER_DEATH
    events.card_id[0, 3] = catalog.card_capacity + 99

    first = resolve_fast_triggered_impacts(catalog, events)
    second = resolve_fast_triggered_impacts(
        catalog, clone_fast_triggered_events(events)
    )
    original = resolve_fast_triggered_impacts(catalog, replay)

    for field in fields(first):
        assert torch.equal(getattr(first, field.name), getattr(second, field.name))
    assert first.active.sum().item() == 2
    assert original.active.sum().item() == 4


def test_duplicate_recognized_mechanic_fails_card_closed() -> None:
    source, _ = _catalog()
    card_id = source.name_to_id["Firecracker"]
    opcode = torch.cat(
        (source.mechanic_opcode, torch.zeros_like(source.mechanic_opcode[:, :1])),
        dim=1,
    )
    opcode[card_id, -1] = MECHANIC_OPCODE["AttackRecoil"]
    parameters = torch.cat(
        (
            source.mechanic_parameters,
            torch.full_like(source.mechanic_parameters[:, :1], torch.nan),
        ),
        dim=1,
    )
    parameters[card_id, -1] = source.mechanic_parameters[card_id, 0]
    nested = torch.cat(
        (
            source.mechanic_nested_payload,
            torch.zeros_like(source.mechanic_nested_payload[:, :1]),
        ),
        dim=1,
    )
    duplicate_source = replace(
        source,
        mechanic_opcode=opcode,
        mechanic_parameters=parameters,
        mechanic_nested_payload=nested,
    )

    catalog = FastTriggeredImpactCatalog.compile(duplicate_source, CardDataLoader())

    assert bool(catalog.duplicate[card_id])
    assert bool(catalog.malformed[card_id])
    assert not bool(catalog.supported[card_id])
    assert int(catalog.descriptor_count[card_id]) == 0
    assert not catalog.trigger[card_id].any()
    assert not catalog.damage[card_id].any()
    assert not catalog.impulse_units[card_id].any()


def test_nested_source_mismatch_and_expansion_overflow_fail_closed() -> None:
    source, _ = _catalog()
    card_id = source.name_to_id["IceGolemite"]
    nested = source.mechanic_nested_payload.clone()
    death_area_slots = (
        source.mechanic_opcode[card_id] == MECHANIC_OPCODE["DeathAreaEffect"]
    )
    nested[card_id, death_area_slots] = False
    malformed_source = replace(source, mechanic_nested_payload=nested)
    catalog = FastTriggeredImpactCatalog.compile(malformed_source, CardDataLoader())
    assert bool(catalog.malformed[card_id])
    assert not bool(catalog.supported[card_id])
    assert int(catalog.descriptor_count[card_id]) == 0

    good_source, good_catalog = _catalog()
    events = _event_fixture(good_source, torch.device("cpu"))
    commands = resolve_fast_triggered_impacts(good_catalog, events)
    with pytest.raises(ValueError, match="expanded impulse pool"):
        triggered_commands_to_impulse_inputs(
            commands,
            _targets(torch.device("cpu")),
            max_expanded_impulses=1,
        )


def test_full_enabled_corpus_has_no_false_malformed_or_duplicate_profiles() -> None:
    manifest = json.loads(
        Path("training_decks/simple_gym_supported_v1.json").read_text()
    )
    names = manifest["support_profile"]["supported_public_cards"]
    loader = CardDataLoader()
    source = TensorCardCatalog.compile(loader, names)

    catalog = FastTriggeredImpactCatalog.compile(source, loader)

    assert not catalog.malformed.any()
    assert not catalog.duplicate.any()
    assert int(catalog.supported.sum()) == 11
    assert int(catalog.descriptor_count.sum()) == 13


def test_runtime_paths_have_no_host_sync_compaction_or_card_dispatch() -> None:
    for function in (
        resolve_fast_triggered_impacts,
        triggered_commands_to_effect_state,
        triggered_commands_to_impulse_inputs,
    ):
        source = inspect.getsource(function)
        for forbidden in (
            ".item(",
            ".tolist(",
            ".cpu(",
            ".nonzero(",
            "argsort(",
            "topk(",
        ):
            assert forbidden not in source
        for card_name in CARDS:
            assert card_name not in source
