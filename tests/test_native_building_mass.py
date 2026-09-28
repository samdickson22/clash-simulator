"""Native Cannon collision exposes building mass distinct from crown towers."""
import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.unit_traits import unit_mass

REFERENCE = json.loads((Path(__file__).parent / 'fixtures/native_building_mass_15_535_86.json').read_text())


@pytest.mark.parametrize('fast_path', [False, True])
def test_giant_displacement_by_new_cannon_uses_native_mass(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle._spawn_unit_at_position(
        Position(*(v / 1000 for v in REFERENCE['giant_xy'])), 0,
        battle.card_loader.get_card('Giant'), deploy_delay_override=0,
        snap_to_valid=False,
    )
    giant = max(battle.entities.values(), key=lambda e: e.id)
    cannon = battle._spawn_entity(
        Building, Position(*(v / 1000 for v in REFERENCE['cannon_xy'])), 1,
        battle.card_loader.get_card('Cannon'),
    )
    assert unit_mass(giant.card_stats) == REFERENCE['giant_mass']
    assert unit_mass(cannon.card_stats) == REFERENCE['cannon_mass']
    expected = {r['elapsed_tick']: r['xy'] for r in REFERENCE['frames']}
    while battle.tick < max(expected):
        battle.step()
        assert [round(giant.position.x * 1000), round(giant.position.y * 1000)] == expected[battle.tick]
