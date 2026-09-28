from __future__ import annotations

import random
from types import SimpleNamespace

import pytest
import torch

from clasher.arena import Position
from clasher.kinematics import logic_units_to_tiles, tiles_to_logic_units
from clasher.spells import ProjectileSpell
from clasher.torch_sim.simple_grouped_geometry import FastGroupedGeometry


def _device(name: str) -> str:
    if name == "mps" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    return name


def _spell(spread: int, radius: int) -> ProjectileSpell:
    return ProjectileSpell(
        name="Geometry probe",
        mana_cost=3,
        radius=logic_units_to_tiles(radius),
        damage=25,
        spread_radius=logic_units_to_tiles(spread),
        multiple_projectiles=10,
        damage_waves=3,
        damage_wave_interval=0.4,
        projectile_pattern="grouped_ring",
    )


class _FixedAngle:
    def __init__(self, angle: int) -> None:
        self.angle = angle
        self.calls = 0

    def randrange(self, stop: int) -> int:
        assert stop == 359
        self.calls += 1
        return self.angle


@pytest.mark.parametrize("device", ["cpu", "mps"])
@pytest.mark.parametrize("spread,radius", [(4000, 1500), (0, 1500), (997, 83)])
def test_every_member_angle_matches_scalar(
    device: str, spread: int, radius: int
) -> None:
    device = _device(device)
    geometry = FastGroupedGeometry.compile(
        pattern="grouped_ring",
        projectile_count=10,
        spread_radius_units=spread,
        projectile_radius_units=radius,
        device=device,
    )
    # Cover both seats and every member for each of the 359 legal angles.
    angles = torch.arange(359, device=device)[:, None].expand(359, 10)
    target = torch.tensor([7500, 21300], device=device).expand(359, 2)
    spell = _spell(spread, radius)
    for owner in (0, 1):
        actual = (
            geometry.destinations(
                angles=angles,
                target_units=target,
                owner=torch.full((359,), owner, device=device, dtype=torch.int8),
            )
            .cpu()
            .tolist()
        )
        expected = []
        for angle in range(359):
            rng = _FixedAngle(angle)
            points = spell._projectile_positions(
                SimpleNamespace(rng=rng),
                owner,
                Position(7.5, 21.3),
                10,
            )
            assert rng.calls == 10
            expected.append(
                [[tiles_to_logic_units(p.x), tiles_to_logic_units(p.y)] for p in points]
            )
        assert actual == expected


class _RecordingRandom(random.Random):
    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.angles: list[int] = []

    def randrange(self, stop: int) -> int:
        assert stop == 359
        value = super().randrange(stop)
        self.angles.append(value)
        return value


@pytest.mark.parametrize("device", ["cpu", "mps"])
@pytest.mark.parametrize("seed", [0, 1278961, 4294967295])
@pytest.mark.parametrize("owner", [0, 1])
def test_full_scalar_cast_targets_and_rng_unchanged(
    device: str, seed: int, owner: int
) -> None:
    device = _device(device)
    rng = _RecordingRandom(seed)
    battle = SimpleNamespace(
        rng=rng,
        next_entity_id=101,
        entities={},
        arena=SimpleNamespace(
            BLUE_KING_TOWER=Position(9, 3), RED_KING_TOWER=Position(9, 29)
        ),
    )
    spell = _spell(4000, 1500)
    assert spell.cast(battle, owner, Position(11.123, 18.456))
    assert len(rng.angles) == 30
    rng_state = rng.getstate()
    geometry = FastGroupedGeometry.compile(
        pattern="grouped_ring",
        projectile_count=10,
        spread_radius_units=4000,
        projectile_radius_units=1500,
        device=device,
    )
    actual = (
        geometry.destinations(
            angles=torch.tensor(rng.angles, device=device).reshape(3, 10),
            target_units=torch.tensor([11123, 18456], device=device).expand(3, 2),
            owner=torch.full((3,), owner, dtype=torch.int8, device=device),
        )
        .reshape(30, 2)
        .cpu()
        .tolist()
    )
    expected = [
        [
            tiles_to_logic_units(p.target_position.x),
            tiles_to_logic_units(p.target_position.y),
        ]
        for p in battle.entities.values()
    ]
    assert actual == expected
    assert rng.getstate() == rng_state


def test_rejects_unsupported_and_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        FastGroupedGeometry.compile(
            pattern="native_radial",
            projectile_count=10,
            spread_radius_units=4000,
            projectile_radius_units=1500,
        )
    with pytest.raises(ValueError, match="at least two"):
        FastGroupedGeometry.compile(
            pattern="grouped_ring",
            projectile_count=1,
            spread_radius_units=4000,
            projectile_radius_units=1500,
        )
    geometry = FastGroupedGeometry.compile(
        pattern="grouped_ring",
        projectile_count=10,
        spread_radius_units=4000,
        projectile_radius_units=1500,
    )
    inputs = {
        "angles": torch.zeros((1, 10), dtype=torch.int64),
        "target_units": torch.zeros((1, 2), dtype=torch.int32),
        "owner": torch.zeros(1, dtype=torch.int8),
    }
    for field, value in (
        ("angles", torch.full((1, 10), 359)),
        ("owner", torch.full((1,), 2)),
        ("target_units", torch.zeros((1, 2))),
    ):
        with pytest.raises(ValueError):
            geometry.destinations(**(inputs | {field: value}))
