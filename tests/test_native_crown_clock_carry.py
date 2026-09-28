"""Crown shots retain work beyond an interval boundary under slow effects."""

import json
from pathlib import Path

import pytest

from clasher.battle import BattleState


@pytest.mark.parametrize('fast_path', [False, True])
def test_king_slow_expiry_preserves_native_firing_phase(fast_path):
    # Reversed-1 right branch: timeline8235 at2130, then35ms work through2169.
    # The shot at2152 crosses9000 by5ms. Native retains that work and fires
    # again at2177, after the slow expires, rather than at2178.
    battle = BattleState(fast_path=fast_path)
    reference = json.loads(
        (Path(__file__).parent / 'fixtures/native_king_slow_carry_15_535_86.json').read_text()
    )
    king = next(e for e in battle.entities.values()
                if e.player_id == 1 and e.card_stats.name == 'KingTower')
    interval = reference['hit_interval_ms']
    king.attack_cooldown = (interval - reference['initial_timeline_ms'] % interval) / 1000
    shots = []
    for frame in reference['frames']:
        tick = frame['tick']
        king.attack_speed_debuff_multiplier = frame['hit_work_ms'] / 50
        king.advance_attack_clock(battle.dt, target_in_range=True)
        if king._attack_is_due():
            shots.append(tick)
            king._complete_attack_clock_cycle()
        if tick == 2152:
            assert king.attack_cooldown == pytest.approx(0.995)
        expected_remaining = interval - frame['timeline_ms'] % interval
        assert king.attack_cooldown == pytest.approx(expected_remaining / 1000), tick
    assert shots == [2152, 2177]
    assert king.attack_cooldown == pytest.approx(0.350)
