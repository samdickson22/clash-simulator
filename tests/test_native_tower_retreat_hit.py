import json
from itertools import pairwise
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Projectile


@pytest.mark.parametrize("fast_path", [False, True])
def test_started_tower_hit_survives_native_knight_retreat(fast_path):
    reference = json.loads(
        (Path(__file__).parent / "fixtures/native_tower_retreat_hit_15_535_86.json").read_text()
    )
    battle = BattleState(fast_path=fast_path)
    tower = battle.entities[2]
    battle.entities = {tower.id: tower}
    battle._spawn_troop(Position(14.5, 17.5), 1, battle.card_loader.get_card("Knight"))
    knight = max(battle.entities.values(), key=lambda e: e.id)
    knight.deploy_delay_remaining = 0
    knight.placement_pending = False
    tower.target_id = knight.id
    tower._last_combat_target_id = knight.id
    tower._has_attacked_once = True
    tower._has_attacked_current_target = True
    tower.attack_cooldown = 0.8
    rows = reference["frames"]
    for previous, expected in pairwise(rows):
        # Combat reads the preceding boundary's position. Supplying this path
        # isolates attack retention from movement and collision differences.
        knight.position = Position(*(v / 1000 for v in previous["knight_xy"]))
        if fast_path:
            battle._refresh_fast_path_caches()
        before = set(battle.entities)
        tower.update_combat_component(battle.dt, battle)
        shots = [
            e for key, e in battle.entities.items()
            if key not in before and isinstance(e, Projectile)
        ]
        assert bool(shots) == (expected["tick"] == 3487), expected["tick"]
        assert (tower.target_id == knight.id) == expected["keeps_knight"], expected["tick"]
        if expected["keeps_knight"]:
            remaining = (800 - expected["timeline"] % 800) / 1000
            assert tower.attack_cooldown == pytest.approx(remaining), expected["tick"]
