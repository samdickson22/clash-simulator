import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import AreaEffect


@pytest.mark.parametrize("interval", [-0.001, 0.0])
def test_nonpositive_effect_interval_cannot_stall_update(interval):
    b = BattleState()
    area = AreaEffect(
        id=999,
        position=Position(8, 10),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=0,
        range=3,
        sight_range=3,
        duration=0.2,
        effect_tick_interval=interval,
    )
    calls = []

    def scan(dt, battle, **kwargs):
        calls.append(dt)
        # Bound the regression itself so the old implementation fails instead
        # of trapping a test worker in the same infinite loop.
        assert len(calls) <= 4, "effect deadline failed to advance"

    area._apply_continuous_effects = scan
    for _ in range(4):
        area.update(0.05, b)
    assert len(calls) == 3
    assert calls == [0.05] * 3
    assert not area.is_alive
