import random

import pytest
import torch

from clasher.torch_sim.simple_cast_rng import CPUExactCastRNG


@pytest.mark.parametrize("device", ["cpu", "mps:0"])
def test_cast_draws_match_supplied_python_stream_and_consumption(device):
    if device == "mps:0" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    references = [random.Random(seed) for seed in (1278961, 17, 88)]
    references[0].gauss(0, 1)  # Preserve the cached Gaussian too.
    owner = CPUExactCastRNG(references)
    mask = torch.tensor([[True, True], [False, True], [False, False]], device=device)
    result = owner.draw_angles(mask)
    expected = torch.zeros((3, 2, 30), dtype=torch.int64)
    for row in range(3):
        for command in range(2):
            if bool(mask[row, command]):
                expected[row, command] = torch.tensor([references[row].randrange(359) for _ in range(30)])
        assert owner.state.python_state(row) == references[row].getstate()
    assert torch.equal(result.angles.cpu(), expected)
    assert result.mask_bytes_to_cpu == (6 if device != "cpu" else 0)
    assert result.angle_bytes_to_device == (1440 if device != "cpu" else 0)


def test_reset_fork_and_fanout_preserve_exact_states_without_aliases():
    references = [random.Random(9), random.Random(10)]
    owner = CPUExactCastRNG(references)
    child = owner.fork([1, 1, 0])
    child.draw_angles(torch.tensor([[True], [False], [False]]))
    assert child.state.python_state(1) == references[1].getstate()
    assert owner.state.python_state(1) == references[1].getstate()
    replacement = [random.Random(11), random.Random(12)]
    owner.reset_rows_(torch.tensor([True, False]), replacement)
    assert owner.state.python_state(0) == replacement[0].getstate()
    assert owner.state.python_state(1) == references[1].getstate()
    child.fanout_from_(owner)
    assert all(child.state.python_state(i) == replacement[0].getstate() for i in range(3))
    child.draw_angles(torch.tensor([[True], [False], [False]]))
    assert child.state.python_state(1) == replacement[0].getstate()
    assert owner.state.python_state(0) == replacement[0].getstate()


def test_invalid_cast_request_does_not_consume_randomness():
    reference = random.Random(42)
    owner = CPUExactCastRNG([reference])
    with pytest.raises(ValueError):
        owner.draw_angles(torch.ones((1, 2), dtype=torch.int64))
    with pytest.raises(ValueError):
        owner.draw_angles(torch.ones((1, 2), dtype=torch.bool), members=0)
    assert owner.state.python_state(0) == reference.getstate()


@pytest.mark.parametrize("device", ["cpu", "mps:0"])
def test_real_arrows_cast_matches_destinations_and_final_rng_for_both_seats(device):
    from clasher.arena import Position
    from clasher.battle import BattleState
    from clasher.dynamic_spells import create_spell_from_json
    from clasher.torch_sim.simple_grouped_geometry import FastGroupedGeometry

    if device == "mps:0" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    battles = [BattleState(), BattleState()]
    for battle in battles:
        battle.rng.seed(1279011)
    owner = CPUExactCastRNG([battle.rng for battle in battles])
    spell = create_spell_from_json(battles[0].card_loader.get_card("Arrows")._raw_entry,
                                   battles[0].card_loader.load_card_definitions())
    geometry = FastGroupedGeometry.compile(
        pattern=spell.projectile_pattern, projectile_count=spell.multiple_projectiles,
        spread_radius_units=round(spell.spread_radius * 1000),
        projectile_radius_units=round(spell.radius * 1000), device=device,
    )
    sampled = owner.draw_angles(torch.ones((2, 1), dtype=torch.bool, device=device))
    destinations = geometry.destinations(
        angles=sampled.angles.reshape(2, 3, 10),
        target_units=torch.tensor([3500, 25500], device=device).expand(2, 3, 2),
        owner=torch.arange(2, device=device)[:, None].expand(2, 3),
    ).reshape(2, 30, 2).cpu().tolist()
    for seat, battle in enumerate(battles):
        before = set(battle.entities)
        assert spell.cast(battle, seat, Position(3.5, 25.5))
        projectiles = [entity for key, entity in battle.entities.items() if key not in before]
        assert destinations[seat] == [[round(p.target_position.x * 1000),
                                       round(p.target_position.y * 1000)] for p in projectiles]
        assert owner.state.python_state(seat) == battle.rng.getstate()
