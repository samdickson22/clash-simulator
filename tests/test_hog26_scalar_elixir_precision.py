import math
from fractions import Fraction
from types import SimpleNamespace

import pytest

from clasher.player import PlayerState


@pytest.mark.parametrize("balance", [4.0, math.nextafter(4.0, -math.inf),
                                     math.nextafter(4.0, math.inf), 3.9999999999999942])
def test_roundoff_at_exact_cost_is_affordable_and_never_negative(balance):
    player = PlayerState(0, elixir=balance, hand=["Fireball"])
    stats = SimpleNamespace(mana_cost=4)
    assert player.can_play_card("Fireball", stats)
    assert player.play_card("Fireball", stats)
    assert 0 <= player.elixir < 1e-9
    assert player.hand == [None]


def test_real_deficit_still_rejects_without_spending_or_cycling():
    player = PlayerState(0, elixir=4 - 1e-7, hand=["Fireball"])
    queue = tuple(player.cycle_queue)
    assert not player.play_card("Fireball", SimpleNamespace(mana_cost=4))
    assert player.elixir == 4 - 1e-7
    assert player.hand == ["Fireball"] and tuple(player.cycle_queue) == queue


def test_regeneration_and_spending_match_quantized_resource_timeline():
    player = PlayerState(0, elixir=0.0, hand=["Skeletons"])
    exact = Fraction(0)
    spent = 0
    for tick in range(1, 6001):
        rate = Fraction(14, 5) if tick < 2400 else Fraction(7, 5) if tick < 4800 else Fraction(93, 100)
        player.regenerate_elixir(.05, float(rate))
        exact = min(Fraction(10), exact + Fraction(int(Fraction(500) / rate), 10000))
        player.hand = ["Skeletons"]
        affordable = exact >= 1
        assert player.can_play_card("Skeletons", SimpleNamespace(mana_cost=1)) == affordable, tick
        if affordable:
            assert player.play_card("Skeletons", SimpleNamespace(mana_cost=1))
            exact -= 1
            spent += 1
        assert player.elixir >= 0
        assert abs(player.elixir - float(exact)) < 1e-9
    assert spent > 100
