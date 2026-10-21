"""Fast checks of the pretrain-v1 featurizer contract (allow-list, history, geometry, encoding).

    python -m pytest -q bot/pretrain_v1/tests/test_featurize.py
"""
import copy

import pytest

from bot.pretrain_v1 import featurize as F

TOWERS = [dict(owner=o, kind=k, side=s, hp_frac=1.0, alive=True) for o, k, s in F.TOWER_ORDER]


def rec(tick, units=(), hand=('HogRider', 'Musketeer', 'Zap', 'Cannon'), nxt='Skeletons', elixir=5.0, towers=None):
    return dict(tick=tick, units=[dict(u) for u in units], towers=copy.deepcopy(towers or TOWERS),
                hand=dict(cards=list(hand), next=nxt), elixir=elixir, events=[])


def unit(card, body, owner, x, y, hp=1.0):
    return dict(card=card, **{'class': body}, cls=body, owner=owner, x=x, y=y, hp_frac=hp)


def test_allow_list_rejects_private_fields():
    h = F.History()
    for bad in (dict(opp_elixir=3.0), dict(opp_hand=['Zap']), dict(next_opp='Log')):
        r = rec(10)
        r.update(bad)
        with pytest.raises(F.FeatureError):
            F.observe(r, None, F.History())
    r = rec(10)
    r['units'] = [dict(unit('Knight', 'Knight', 1, 3, 20), target=[1, 2])]
    with pytest.raises(F.FeatureError):
        F.observe(r, None, h)
    r = rec(10)
    r['towers'][0]['level'] = 9
    with pytest.raises(F.FeatureError):
        F.observe(r, None, F.History())
    r = rec(10)
    r['events'] = [dict(owner=0, card='Zap', x=1, y=1, tick=1, derived=True)]
    with pytest.raises(F.FeatureError):
        F.observe(r, None, F.History())
    with pytest.raises(F.FeatureError):
        F.observe(rec(10), dict(first_seen=None, spells=None, opp_hand=[]), F.History())


def test_poll_key_is_the_only_logging_field():
    r = rec(10)
    r['poll'] = 10
    F.observe(r, None, F.History())
    r['wall'] = 1.0
    with pytest.raises(F.FeatureError):
        F.observe(r, None, F.History())


def test_deterministic_bytes():
    seq = [rec(5*i + 90, units=[unit('Knight', 'Knight', 1, 3 + .1*i, 20 - .2*i)]) for i in range(30)]
    a = [F.feature_bytes(F.observe(r, None, h)) for h in [F.History()] for r in seq]
    b = [F.feature_bytes(F.observe(r, None, h)) for h in [F.History()] for r in seq]
    assert a == b


def test_tick_must_advance():
    h = F.History()
    F.observe(rec(100), None, h)
    with pytest.raises(F.FeatureError):
        F.observe(rec(100), None, h)


def test_affordability_and_channel_mask():
    h = F.History()
    f = F.observe(rec(100, elixir=3.5), None, h)
    # HogRider 4 unaffordable, Musketeer 4 unaffordable, Zap 2 ok, Cannon 3 ok
    assert list(f['slot_ok']) == [False, False, True, True]
    h.submit(100, 2, 'Zap', 300)
    f = F.observe(rec(105, elixir=3.6), None, h)
    assert not f['slot_ok'].any() and f['glob'][F.G_BUSY] == 1
    # the card leaving the hand confirms the command and frees the channel
    f = F.observe(rec(110, hand=('HogRider', 'Musketeer', 'Skeletons', 'Cannon'), nxt='Fireball', elixir=1.7), None, h)
    assert f['glob'][F.G_BUSY] == 0 and f['glob'][F.G_N_OWN] == 1
    own = f['ev'][(f['ev'][:, F.V_PRESENT] == 1) & (f['ev'][:, F.V_OWNER] == 0)]
    assert len(own) == 1 and own[0, F.V_X] == 1250 and own[0, F.V_Y] == 1650     # tile 300 = col 12, row 16


def test_expiry_releases_channel():
    h = F.History()
    F.observe(rec(100), None, h)
    h.submit(100, 0, 'HogRider', 200)
    f = F.observe(rec(100 + F.EXPIRE + 5), None, h)
    assert f['glob'][F.G_BUSY] == 0 and f['glob'][F.G_REJ_LAST] == 0


def test_opponent_play_detection_primary_body_only():
    h = F.History()
    F.observe(rec(100), None, h)
    f = F.observe(rec(105, units=[unit('Witch', 'Witch', 1, 4, 24)]), None, h)
    assert f['glob'][F.G_N_OPP] == 1
    # the Witch's skeletons are descendants, not plays
    sk = [unit('Witch', 'Skeleton', 1, 4 + .3*i, 23) for i in range(3)]
    f = F.observe(rec(110, units=[unit('Witch', 'Witch', 1, 4, 23.5)] + sk), None, h)
    assert f['glob'][F.G_N_OPP] == 1
    # an own unit never reveals an opponent card
    f = F.observe(rec(115, units=[unit('HogRider', 'HogRider', 0, 4, 10)]), None, h)
    assert f['glob'][F.G_N_OPP] == 1 and f['glob'][F.G_N_REV] == 1


def test_carrier_detection_and_aim():
    h = F.History()
    F.observe(rec(100), dict(first_seen=[], spells=[]), h)
    sp = [(1, 'Fireball', 9.0, 25.0, 4.0, 6.5, 6)]
    f = F.observe(rec(105), dict(first_seen=[], spells=sp), h)
    assert f['glob'][F.G_N_OPP] == 1
    car = f['ent'][f['ent'][:, F.E_KIND] == 2]
    assert len(car) == 1 and car[0, F.E_AX] == 400 and car[0, F.E_AY] == 650
    ev = f['ev'][f['ev'][:, F.V_PRESENT] == 1]
    assert ev[0, F.V_AGE] == 6                       # play tick = tick - flown
    f = F.observe(rec(110), dict(first_seen=[], spells=[(1, 'Fireball', 8.0, 20.0, 4.0, 6.5, 11)]), h)
    assert f['glob'][F.G_N_OPP] == 1                 # same carrier: not a new play


def test_missing_extras_are_explicit():
    f = F.observe(rec(100, units=[unit('Knight', 'Knight', 1, 3, 20)]), None, F.History())
    assert f['glob'][F.G_X_UNITS] == 0 and f['ent'][0, F.E_AGE] == -1
    f = F.observe(rec(100, units=[unit('Knight', 'Knight', 1, 3, 20)]), dict(first_seen=[80], spells=None),
                  F.History())
    assert f['glob'][F.G_X_UNITS] == 1 and f['ent'][0, F.E_AGE] == 20
    # misaligned first_seen degrades to missing, never to a wrong age
    f = F.observe(rec(100, units=[unit('Knight', 'Knight', 1, 3, 20)]), dict(first_seen=[80, 81], spells=None),
                  F.History())
    assert f['glob'][F.G_X_UNITS] == 0


def test_entity_cap_is_a_refusal():
    us = [unit('Skeletons', 'Skeleton', 1, 9, 20) for _ in range(F.MAX_ENT + 1)]
    with pytest.raises(F.FeatureError):
        F.observe(rec(100, units=us), None, F.History())


def test_placement_geometry():
    cat = F.catalog()
    alive = (True,)*6
    ground = F.tile_mask(F.PLACE_CODES['ground'], alive)
    spell = F.tile_mask(F.PLACE_CODES['spell'], alive)
    enemy = F.tile_mask(F.PLACE_CODES['enemy'], alive)

    def at(m, c, r):
        return bool(m[r*F.W + c])
    assert at(ground, 9, 10) and not at(ground, 9, 20) and not at(ground, 9, 15)       # own half / enemy / river
    assert not at(ground, 3, 6) and not at(ground, 9, 3)                               # on own towers
    assert at(ground, 9, 0) and not at(ground, 2, 0)                                    # behind king vs fence
    assert at(spell, 9, 28) and not at(spell, 0, 14)                                    # spells anywhere but fences
    assert at(enemy, 9, 22) and not at(enemy, 3, 25)                                    # Miner: not on a tower
    pocket = F.tile_mask(F.PLACE_CODES['ground'], (True, True, True, True, False, True))
    assert at(pocket, 4, 18) and not at(pocket, 12, 18) and at(pocket, 3, 15)
    assert cat.place[cat.card('Miner')] == F.PLACE_CODES['enemy']
    assert cat.place[cat.card('Log')] == F.PLACE_CODES['territory']


def test_nearest_legal_tile():
    m = F.tile_mask(F.PLACE_CODES['ground'], (True,)*6)
    assert F.nearest_legal_tile(9.5, 10.5, m) == (10*F.W + 9, 0.0)
    t, d = F.nearest_legal_tile(9.5, 15.2, m)          # just over the river edge: nearest legal row 14
    assert t == 14*F.W + 9 and d == pytest.approx(.7)
    assert F.nearest_legal_tile(9.5, 20.5, m)[0] is None


def test_encoding_round_trip():
    for slot in range(4):
        for tile in (0, 17, 300, 575):
            a = F.encode(slot, tile)
            s, c, r = F.decode(a)
            assert (s, r*F.W + c) == (slot, tile)
    assert F.decode(F.NOOP) is None and F.NOOP == 2304


# -- regressions for Sol R1 (2026-10-21) ------------------------------------------------------------------------------
def test_mirror_cost_and_placement_follow_last_ordinary_card():
    h = F.History()
    hand = ('Golem', 'Mirror', 'Zap', 'Cannon')
    f = F.observe(rec(100, hand=hand, nxt='Log', elixir=9.0), None, h)
    assert not f['slot_ok'][1]                               # no predecessor: Mirror is not playable
    h.submit(100, 0, 'Golem', 200)
    f = F.observe(rec(105, hand=('Log', 'Mirror', 'Zap', 'Cannon'), nxt='Knight', elixir=1.1), None, h)
    assert f['hand'][1, F.H_COST] == 9 and not f['slot_ok'][1]  # Golem 8 + 1, unaffordable at 1.1
    assert f['hand'][1, F.H_PLACE] == F.PLACE_CODES['ground']
    f = F.observe(rec(110, hand=('Log', 'Mirror', 'Zap', 'Cannon'), nxt='Knight', elixir=9.5), None, h)
    assert f['slot_ok'][1]
    m = F.legal_tiles(f)[1]
    assert not m[20*F.W + 9]                                  # ground placement: no enemy-territory Mirror-Golem


def test_spell_body_episode_counts_once_and_is_uncertain():
    h = F.History()
    F.observe(rec(100), None, h)
    sk = lambda x: unit('Graveyard', 'Skeleton', 1, x, 8)
    F.observe(rec(105, units=[sk(3)]), None, h)
    F.observe(rec(110), None, h)                              # momentarily none
    f = F.observe(rec(190, units=[sk(4)]), None, h)           # same Graveyard still spawning
    assert f['glob'][F.G_N_OPP] == 1
    rev = f['rev'][f['rev'][:, F.R_PRESENT] == 1]
    assert rev[0, F.R_UNC] == 1


def test_first_poll_bodies_are_revealed_not_counted():
    f = F.observe(rec(90, units=[unit('Knight', 'Knight', 1, 3, 20)]), None, F.History())
    rev = f['rev'][f['rev'][:, F.R_PRESENT] == 1]
    assert f['glob'][F.G_N_OPP] == 0 and len(rev) == 1 and rev[0, F.R_N] == 0 and rev[0, F.R_UNC] == 1


def test_simultaneous_identical_carriers_count_twice():
    h = F.History()
    F.observe(rec(100), dict(first_seen=[], spells=[]), h)
    two = [(1, 'Fireball', 9.0, 25.0, 4.0, 6.5, 6), (1, 'Fireball', 9.2, 25.0, 4.0, 6.5, 6)]
    f = F.observe(rec(105), dict(first_seen=[], spells=two), h)
    assert f['glob'][F.G_N_OPP] == 2


def test_expiry_matches_live_session_default():
    assert F.EXPIRE == 90
