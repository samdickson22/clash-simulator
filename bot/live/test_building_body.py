"""Building-class detections keep their building body (CLASHER_LIVE_BUILDING_BODY, bot/live/translate.py
_building_body): the translator passes the card's building body as an observed-body constraint, so a hut whose box
jumps past `building_radius` after its first frame is never tracked as its own death child (s79-m05: the Goblin Hut
became a SpearGoblin troop for the whole battle).

    PYTHONPATH=. nice -n 19 python -m pytest -q bot/live/test_building_body.py      (frozen runtime, ~15 s setup)
"""
import pytest


@pytest.fixture(scope='module')
def cb():
    from bot.players.runtime import Runtime
    from bot.live.births import CardBodies
    return CardBodies(Runtime())


def run(cb, constrained):
    from bot.live.births import UnitTracker
    t = UnitTracker(cb)
    hut = [b for b, _ in cb.main['GoblinHut'] if b[1] == 1][0]
    bodies, plays = [], []
    for k, tick in enumerate(range(570, 900, 5)):
        x, y = (11.49, 23.26) if k == 0 else (11.58, 22.01)     # the s79-m05 boxes: 1.25 tiles apart
        u = ('GoblinHut', 1, x, y, .9) + ((None, hut) if constrained else ())
        got, p = t.update(tick, [u], {'left': True, 'right': True})
        bodies.append(got[0][0])
        plays += [q[1] for q in p if q[0] == 1]
    return hut, bodies, plays


def test_unconstrained_hut_jump_becomes_a_troop(cb):
    """The bug, documented: without the constraint the jumped hut is born as its own death child (a troop body)."""
    hut, bodies, _ = run(cb, False)
    assert bodies[0] == hut and any(b is not None and b[1] == 0 for b in bodies[1:])


def test_constrained_hut_stays_a_building_and_is_one_play(cb):
    hut, bodies, plays = run(cb, True)
    assert all(b == hut for b in bodies)
    assert plays == ['GoblinHut']
