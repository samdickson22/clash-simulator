import copy
from types import SimpleNamespace as NS

import pytest

from bot.pretrain_v1 import featurize as F
from bot.pretrain_v1 import sim_ours as S

DECK = ['Skeletons', 'Musketeer', 'IceGolem', 'Cannon', 'Fireball', 'Zap', 'IceSpirit', 'HogRider']


def battle(monkeypatch):
    monkeypatch.setattr(S, 'install_root_tracking', lambda _: None)
    own = NS(hand=DECK[:4], cycle_queue=DECK[4:], elixir=7.)
    class OwnHUDOnly:
        def __getitem__(self, seat):
            assert seat == 0, 'the enemy player object must never be read'
            return own
    entities = {}
    for seat in [0, 1]:
        for name, x, y, hp in [('Tower', 3.5, 5.5, 2534), ('Tower', 14.5, 5.5, 2534), ('KingTower', 9, 2.5, 4008)]:
            i = len(entities)+1
            if seat: x, y = 18-x, 32-y
            entities[i] = NS(id=i, player_id=seat, card_stats=NS(name=name), position=NS(x=x, y=y),
                             hitpoints=hp, max_hitpoints=hp, is_alive=True, entity_kind=1)
    entities[7] = NS(id=7, player_id=1, card_stats=NS(name='Skeleton'), position=NS(x=4, y=17),
                     hitpoints=100, max_hitpoints=100, is_alive=True, entity_kind=0,
                     is_visible_to=lambda _: True, _pv1_root_card='Skeletons')
    return NS(tick=90, players=OwnHUDOnly(), entities=entities), own


def test_own_hud_only_and_logged_frame_parity(monkeypatch):
    b, own = battle(monkeypatch)
    frames = S.OursFrames(b, 0, DECK, 11)
    (record, extras), line = frames.record()
    shadow, reason = S.record_from_line(line, S.new_builder(DECK))
    assert reason is None and shadow == (record, extras)
    feat = F.observe(record, extras, F.History())
    sh = F.observe(shadow[0], shadow[1], F.History())
    assert F.feature_bytes(feat) == F.feature_bytes(sh)
    before = frames.frame()
    own.elixir = 2
    assert frames.frame()['e'] != before['e']


def test_destroyed_tower_is_zero_not_stale_positive_hp(monkeypatch):
    b, _ = battle(monkeypatch)
    frames = S.OursFrames(b, 0, DECK, 11)
    frames.frame()
    del b.entities[1]
    found = [u for u in frames.frame()['u'] if u[0] == 2]
    assert len(found) == 1 and found[0][5] == 0


def test_hidden_entity_and_unknown_identity(monkeypatch):
    b, _ = battle(monkeypatch)
    frames = S.OursFrames(b, 0, DECK, 11)
    b.entities[7].is_visible_to = lambda _: False
    assert not any(u[0] == 8 for u in frames.frame()['u'])
    b.entities[7].is_visible_to = lambda _: True
    b.entities[7]._pv1_root_card = None
    with pytest.raises(F.FeatureError, match='creating card'):
        frames.frame()
    with pytest.raises(F.FeatureError, match='no live identity'):
        S.body_name('UnidentifiedBody', 'Skeletons')


def test_tower_attack_projectile_is_not_a_crown_tower(monkeypatch):
    b, _ = battle(monkeypatch)
    e = copy.copy(b.entities[1])
    e.id = 8; e.entity_kind = 2; e.position = NS(x=9., y=17.)
    e.is_visible_to = lambda _: True
    b.entities[8] = e
    frames = S.OursFrames(b, 0, DECK, 11)
    assert not any(u[0] == 9 for u in frames.frame()['u'])
    assert 9 not in frames.towers
