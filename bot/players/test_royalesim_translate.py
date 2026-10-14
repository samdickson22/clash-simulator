"""Translator tests: RoyaleSim rows -> our v5 public packet.

    CLASHER_BOT_RUNTIME=... bot/players/run.sh -m pytest -q bot/players/test_royalesim_translate.py

Needs the frozen runtime (builder, templates) and royalesim; ~20 s for Runtime setup.
"""
import copy
import json

import numpy as np
import pytest

from bot.players.royalesim_adapter import action_to_command

SUB = 18000


@pytest.fixture(scope='module')
def rt():
    from bot.players.runtime import Runtime
    return Runtime()


@pytest.fixture(scope='module')
def vocab(rt):
    from bot.players.royalesim_vocab import load
    return load(rt)


@pytest.fixture(scope='module')
def world(rt, vocab):
    import royalesim as rs
    from bot.players.royalesim_vocab import rsim_battle
    from bot.players.royalesim_translate import Translator
    b = rsim_battle()
    catalogue = json.loads(b.catalogue_json())
    tr = Translator(rt, vocab, catalogue)
    tr.bind(b)
    ids = {row[0]: i for i, row in enumerate(catalogue)}
    types = {n: i for i, n in enumerate(json.loads(b.unit_types_json()))}
    return dict(tr=tr, ids=ids, types=types, F={f: i for i, f in enumerate(rs.ENTITY_FIELDS)})


def entity(w, uid, team, kind, unit_type, card, x, y, hp, max_hp, facing=(0, 256), flags=0, tower_slot=-1):
    F = w['F']
    row = [0]*len(F)
    row[F['uid']], row[F['team']], row[F['kind']] = uid, team, kind
    row[F['card_id']] = w['ids'][card] if card else -1
    row[F['tower_slot']] = tower_slot
    row[F['x']], row[F['y']] = round(x*SUB), round(y*SUB)
    row[F['hp']], row[F['max_hp']] = hp, max_hp
    row[F['facing']] = list(facing)
    row[F['status_flags']] = flags
    row[F['level']] = 11
    row[F['mount_uid']] = -1
    row[F['buffs']] = []
    row[F['unit_type']] = w['types'][unit_type]
    return row


def towers(w, blue_left=3052):
    return [entity(w, 0, 0, 2, 'KingTower', None, 9, 3, 4824, 4824, tower_slot=0),
            entity(w, 2, 0, 3, 'PrincessTower', None, 3.5, 6.5, blue_left, 3052, tower_slot=1),
            entity(w, 4, 0, 3, 'PrincessTower', None, 14.5, 6.5, 3052, 3052, tower_slot=2),
            entity(w, 1, 1, 2, 'KingTower', None, 9, 29, 4824, 4824, tower_slot=0),
            entity(w, 3, 1, 3, 'PrincessTower', None, 14.5, 25.5, 3052, 3052, tower_slot=2),
            entity(w, 5, 1, 3, 'PrincessTower', None, 3.5, 25.5, 3052, 3052, tower_slot=1)]


def player(team, tower_hp, hand=(0, 1, 2, 3), elixir=5000):
    return dict(team=team, elixir_milli=elixir, hand=list(hand), hand_costs=[3, 3, 3, 3], mirror_target=-1,
                deck=list(range(8)), forms=[0]*8, pending_cost=0, pending=[], evo=[], abilities=[], next_card=4,
                crowns=0, tower_hp=list(tower_hp), tower_max_hp=[4824, 3052, 3052], king_active=False)


@pytest.fixture
def state(world):
    w = world
    ents = towers(w, blue_left=1526) + [
        entity(w, 10, 0, 0, 'Knight', 'Knight', 4.5, 10.5, 883, 1766, facing=(0, 256)),
        entity(w, 11, 1, 1, 'Cannon', 'Cannon', 9.0, 22.0, 700, 700, facing=(0, -256)),
        entity(w, 13, 1, 0, 'Miner', 'Miner', 9.5, 12.5, 1000, 1000, flags=1),       # underground
        entity(w, 15, 1, 0, 'Ghost', 'Ghost', 12.5, 14.5, 500, 500, flags=2),        # invisible
    ]
    spells = [[0, w['ids']['Fireball'], 0, round(9*SUB), round(8*SUB), round(9*SUB), round(20*SUB), 0, 0, 0, 0, 3]]
    projectiles = [[1, round(9.5*SUB), round(20*SUB), round(4.5*SUB), round(11*SUB), 10, 0, w['ids']['Musketeer']],
                   [0, round(9*SUB), round(5*SUB), round(9*SUB), round(12*SUB), 13, 0, -1]]   # blue king shot
    return dict(tick=1000, tick_ms=50, regular_ticks=3600, overtime_ticks=2400, elixir_rate=1, overtime=False,
                game_over=False, winner=-1,
                players=[player(0, [4824, 1526, 3052]), player(1, [4824, 3052, 3052], hand=(5, 6, 7, 0), elixir=9000)],
                entities=ents, spells=spells, projectiles=projectiles)


OWN = dict(elixir=5.0, hand=['Knight', 'Archers', 'Giant', 'Fireball'], cycle=['Musketeer', 'Arrows', 'Zap', 'Log'],
           refill=0)
PLAYS = {0: [(900, 'Fireball')], 1: [(950, 'Musketeer'), (980, 'Cannon')]}


def rows(packet, rt):
    o = packet.observation
    names = rt.R.builder.token_names
    out = []
    for i in np.flatnonzero(o.entity_mask):
        f = o.entity_features[i]
        out.append(dict(name=names[int(o.entity_ids[i])], kind=int(np.argmax(f[4:9])), own=bool(f[2] > .5),
                        x=float(f[0])*18, y=float(f[1])*32, hp=float(f[9]), mx=float(f[27]), my=float(f[28]),
                        level=int(o.entity_levels[i])))
    return out


def find(rs, name, **kw):
    hits = [r for r in rs if r['name'] == name and all(r[k] == v for k, v in kw.items())]
    assert len(hits) == 1, (name, kw, [r for r in rs if r['name'] == name])
    return hits[0]


def test_action_to_command_matches_our_decode_and_seat_flip(rt):
    from clasher.rl.action_space import DiscreteTileActionSpace   # noqa: F401  (runtime import path)
    a = 1*576 + 10*18 + 4
    assert action_to_command(a, 0) == (0, 1, round(4.5*SUB), round(10.5*SUB))
    assert action_to_command(a, 1) == (1, 1, round((17-4+.5)*SUB), round((31-10+.5)*SUB))


def test_seat0_rows_positions_kinds_and_hidden_enemies(rt, world, state):
    r = rows(world['tr'].observation(state, 0, OWN, PLAYS), rt)
    knight = find(r, 'Knight')
    assert knight['own'] and knight['kind'] == 0 and knight['hp'] == pytest.approx(.5)
    assert (knight['x'], knight['y']) == pytest.approx((4.5, 10.5), abs=1e-4)
    assert (knight['mx'], knight['my']) == pytest.approx((0, 1))
    cannon = find(r, 'Cannon')
    assert not cannon['own'] and cannon['kind'] == 1 and (cannon['x'], cannon['y']) == pytest.approx((9, 22), abs=1e-4)
    assert not any(x['name'] in ('Miner', 'Ghost') for x in r), 'underground/invisible enemies must be hidden'
    fireball = find(r, 'Fireball')
    assert fireball['kind'] == 2 and fireball['own'] and (fireball['mx'], fireball['my']) == pytest.approx((0, 1))
    shot = find(r, 'MusketeerProjectile')
    assert shot['kind'] == 2 and not shot['own']
    assert sum(x['kind'] == 1 and x['name'] in ('KingTower', 'Tower') for x in r) == 6
    assert find(r, 'Tower', own=True, x=pytest.approx(3.5, abs=1e-4))['hp'] == pytest.approx(.5)
    assert find(r, 'Knight')['level'] == 11
    assert len([x for x in r if x['kind'] == 2 and x['name'] in ('KingTower', 'Tower')]) == 1, 'king shot row'


def test_seat1_view_is_the_180_degree_rotation(rt, world, state):
    r0 = rows(world['tr'].observation(state, 0, OWN, PLAYS), rt)
    r1 = rows(world['tr'].observation(state, 1, OWN, PLAYS), rt)
    knight = find(r1, 'Knight')
    assert not knight['own'] and (knight['x'], knight['y']) == pytest.approx((18-4.5, 32-10.5), abs=1e-4)
    assert (knight['mx'], knight['my']) == pytest.approx((0, -1))
    cannon = find(r1, 'Cannon')
    assert cannon['own'] and (cannon['x'], cannon['y']) == pytest.approx((9, 10), abs=1e-4)
    assert find(r1, 'Miner')['own'] and find(r1, 'Ghost')['own'], 'own hidden units stay visible to their owner'
    fireball = find(r1, 'Fireball')
    assert not fireball['own'] and (fireball['mx'], fireball['my']) == pytest.approx((0, -1))
    assert len(r1) == len(r0) + 2


def test_globals_lanes_hand_history(rt, world, state):
    b = rt.R.builder
    p0 = world['tr'].observation(state, 0, OWN, PLAYS).observation
    p1 = world['tr'].observation(state, 1, OWN, PLAYS).observation
    g0, g1 = p0.global_features, p1.global_features
    assert g0[0] == pytest.approx(1000*.05/300) and g0[2] == 0 and g0[4] == 0
    assert g0[5] == pytest.approx(.5)
    assert g0[8] == pytest.approx(.5) and g0[9] == 1 and g0[10] == 1          # own left (x<9) at half
    assert g1[12] == pytest.approx(.5) and g1[11] == 1                        # seat 1 sees it as enemy RIGHT
    assert g0[17] == 1
    assert list(p0.hand_ids) == [b.token_id(n) for n in OWN['hand'] + OWN['cycle'][:1]]
    assert list(p0.opponent_history_ids[:2]) == [b.token_id('Cannon'), b.token_id('Musketeer')]
    assert p0.opponent_history_ages[0] == pytest.approx(20*.05/60)
    assert list(p1.opponent_seen_card_ids[:2]) == [b.token_id('Fireball'), 0]
    assert p0.own_last_play.card_name == 'Fireball' and p1.own_last_play.card_name == 'Cannon'


def test_opponent_private_record_never_changes_the_view(rt, world, state):
    """Fair information: the opponent's hand, next card, deck, pending, elixir are not read."""
    base = world['tr'].observation(state, 0, OWN, PLAYS)
    poisoned = copy.deepcopy(state)
    them = poisoned['players'][1]
    them.update(elixir_milli=123, hand=[9, 9, 9, 9], next_card=11, deck=[1]*8, pending=[[0, 3, 1, 1, 5, 3]],
                pending_cost=3, hand_costs=[9, 9, 9, 9])
    other = world['tr'].observation(poisoned, 0, OWN, PLAYS)
    for f in ('entity_ids', 'entity_features', 'hand_ids', 'global_features', 'opponent_history_ids',
              'opponent_seen_card_ids', 'entity_levels'):
        assert np.array_equal(getattr(base.observation, f), getattr(other.observation, f)), f


def test_phase_flags_follow_our_engine_tick_alignment(rt, world, state):
    from differential import initial
    b = initial()
    tr = world['tr']
    s = copy.deepcopy(state)
    for boundary in (2400, 3600, 4800):
        while b.tick < boundary - 3:
            if b.fast_forward_idle_ticks(boundary - 3 - b.tick) == 0:
                b.step()
        for _ in range(6):
            s['tick'] = b.tick
            g = tr.globals(s, 0, OWN)
            assert (g[2], g[3], g[4]) == (float(b.double_elixir), float(b.triple_elixir), float(b.overtime)), b.tick
            b.step()


def test_real_battle_rows_follow_the_deploy_and_mirror_between_seats(rt, vocab):
    from bot.players.royalesim_match import RsimMatch
    decks = [['Knight', 'Archers', 'Giant', 'Musketeer', 'Fireball', 'Arrows', 'Log', 'Skeletons']]*2
    m = RsimMatch(rt, vocab, decks, seed=7)
    m.b.step([], 100); m.refresh()
    tile = 8*18 + 4                       # own frame col 4, row 8
    out = m.execute([(0, 0*576 + tile, 'Knight'), (1, 1*576 + tile, 'Archers')])
    assert [ok for ok, _ in out] == [True, True]
    m.b.step([], 3); m.refresh()
    for seat in (0, 1):
        r = rows(m.information(seat).packet, rt)
        own = [x for x in r if x['own'] and x['kind'] == 0]
        assert {x['name'] for x in own} == {'Knight' if seat == 0 else 'Archer'}
        for x in own:                     # still deploying: at the tapped tile in the own frame
            assert abs(x['x'] - 4.5) < 1.1 and abs(x['y'] - 8.5) < 1.1
    r0, r1 = rows(m.information(0).packet, rt), rows(m.information(1).packet, rt)
    k0, k1 = find(r0, 'Knight'), find(r1, 'Knight')
    assert (k0['x'], k0['y']) == pytest.approx((18-k1['x'], 32-k1['y']), abs=1e-4)
    assert m.tr.stats == {} and m.own[0].mismatch == {}
