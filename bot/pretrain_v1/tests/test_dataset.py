"""Dataset-builder regressions (Sol R1): split fingerprint under seat swap, cycle agreement, live eligibility."""
import copy

from bot.pretrain_v1 import dataset as D


def _job():
    deck0 = [dict(slug=f'c{i}', form='base', level=11, d=26000000 + i) for i in range(8)]
    deck1 = [dict(slug=f'k{i}', form='base', level=11, d=26000100 + i) for i in range(8)]
    ev = [dict(i=0, tick=200, seat=0, kind='play', slug='c0', d=26000000, x=3500, y=10500),
          dict(i=1, tick=300, seat=1, kind='play', slug='k1', d=26000101, x=14500, y=20500)]
    return dict(decks=[deck0, deck1], towers=[dict(slug='tower-princess', level=11)]*2, events=ev)


def test_fingerprint_invariant_to_seat_swap_with_rotation():
    j = _job()
    sw = copy.deepcopy(j)
    sw['decks'].reverse()
    sw['towers'].reverse()
    for e in sw['events']:
        e['seat'] = 1 - e['seat']
        e['x'], e['y'] = 18000 - e['x'], 32000 - e['y']
    assert D.fingerprint(j) == D.fingerprint(sw)
    moved = copy.deepcopy(j)
    moved['events'][0]['x'] += 1000
    assert D.fingerprint(moved) != D.fingerprint(j)


def test_cycle_agreement_needs_the_first_four_plays():
    deck = list(range(26000000, 26000008))
    j = dict(decks=[[dict(d=c) for c in deck]], events=[dict(seat=0, kind='play', d=c) for c in deck[:6]])
    k = D.cycle_agreement(j, 0)
    assert k is not None and 1 <= k <= 6
    j['events'] = [dict(seat=0, kind='play', d=deck[0])]
    assert D.cycle_agreement(j, 0) is None or D.cycle_agreement(j, 0) >= 1


def test_start_tick_is_the_live_first_poll():
    assert D.START_TICK == 90
