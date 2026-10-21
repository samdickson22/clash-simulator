"""bot.simfid.rebuild: source parsing, level rejection, form/support classification, cycle inference, scoring.

    PYTHONPATH=<engine src>:. CLASHER_ROOT=<engine root> python -m pytest -q bot/simfid/test_rebuild.py
The engine-backed tests skip when no `clasher` package is importable.
"""
import itertools
from collections import deque

import pytest

from bot.simfid import rebuild as R

DECK_A = ['knight', 'archers', 'fireball', 'zap', 'giant', 'musketeer', 'cannon', 'skeletons']
DECK_B = ['hog-rider', 'the-log', 'ice-spirit', 'ice-golem', 'valkyrie', 'tesla', 'arrows', 'goblins']


def payload(team=None, opp=None, events=(), result='victory', levels=16, towers=('tower-princess', 'tower-princess'),
            tower_levels=(16, 16)):
    def player(deck, tower, tl):
        return dict(deck=[dict(card_key=k, level=levels if isinstance(levels, int) else levels.get(k, 16)) for k in deck],
                    tower_card=dict(card_key=tower, level=tl),
                    final_tower_hitpoints=dict(king=7000, princess_left=0, princess_right=4000))
    evs = []
    for i, (tick, side, key, x, y) in enumerate(events):
        if key.startswith('ability:'):
            evs.append(dict(kind='activate_ability', side=side, replay_tick_20hz=tick, source_index=i,
                            ability_source_candidates=key[8:].split(','), card_key=None, coordinates=None))
        else:
            evs.append(dict(kind='play_card', side=side, replay_tick_20hz=tick, source_index=i, card_key=key,
                            coordinates=dict(native_world_units=dict(x=x, y=y))))
    return dict(battle=dict(game_mode='Ranked', battle_type='pathOfLegend', result=result,
                            team=dict(crowns=1, players=[player(team or DECK_A, towers[0], tower_levels[0])]),
                            opponent=dict(crowns=0, players=[player(opp or DECK_B, towers[1], tower_levels[1])])),
                events=evs, replay=dict(duration=dict(timeline_seconds=180.0)))


def test_split_form():
    assert R.split_form('knight-ev1') == ('knight', 'evo')
    assert R.split_form('archer-queen-hero') == ('archer-queen', 'hero')
    assert R.split_form('the-log') == ('the-log', 'base')


def test_parse_orders_events_and_maps_sides():
    m = R.parse(payload(events=[(300, 'opponent', 'hog-rider', 9500, 20500), (200, 'team', 'knight', 9500, 8500),
                                (200, 'opponent', 'ability:knight-hero', None, None)]))
    assert [(e.tick, e.side, e.kind) for e in m.events] == [(200, 0, 'play'), (200, 1, 'ability'), (300, 1, 'play')]
    assert m.winner == 0 and m.crowns == (1, 0)
    assert m.final_hp[0] == (7000, 0, 4000)


def test_parse_rejects_play_outside_deck():
    with pytest.raises(R.Reject, match='play-outside-deck'):
        R.parse(payload(events=[(200, 'team', 'hog-rider', 9500, 8500)]))


def test_levels_reject_incomplete_never_default():
    rarity = {'Knight': 'Common', 'RoyalGhost': 'Legendary'}.get
    m = R.parse(payload(levels={**{k: 16 for k in DECK_A}, 'zap': 0}))
    with pytest.raises(R.Reject, match='level-incomplete'):
        R.levels(m, lambda n: 'Common')
    m = R.parse(payload(tower_levels=(16, 0)))
    with pytest.raises(R.Reject, match='level-incomplete'):
        R.levels(m, lambda n: 'Common')
    # a Legendary below its first displayed level (9) cannot be a displayed level
    m = R.parse(payload(levels={**{k: 16 for k in DECK_A}, 'zap': 5}))
    with pytest.raises(R.Reject, match='level-invalid'):
        R.levels(m, lambda n: 'Legendary' if n == 'Zap' else 'Common')
    m = R.parse(payload(levels={**{k: 14 for k in DECK_A}, 'zap': 9}, tower_levels=(15, 11)))
    cards, towers = R.levels(m, rarity)
    assert cards[0]['Zap'] == 9 and cards[0]['Knight'] == 14 and towers == [15, 11]


def test_classify_tiers_and_prefix():
    names = set(R.SLUG_TO_ENGINE.values())
    m = R.parse(payload())
    assert R.classify(m, names)['tier'] == 'faithful-supported'
    team = ['knight-ev1'] + DECK_A[1:]
    m = R.parse(payload(team=team, events=[(250, 'team', 'archers', 9500, 8500), (400, 'team', 'knight', 9500, 8500)]))
    c = R.classify(m, names)
    assert c['tier'] == 'base-form-substitution' and c['faithful_prefix_end_tick'] == 400 and c['evo_cards'] == ['knight']
    m = R.parse(payload(towers=('tower-princess', 'dagger-duchess')))
    c = R.classify(m, names)
    assert c['tower_troops'] == ['dagger-duchess'] and c['faithful_prefix_end_tick'] == 0
    m = R.parse(payload(events=[(500, 'team', 'ability:monk', None, None)]))
    assert R.classify(m, names, frozenset({'archer-queen'}))['faithful_prefix_end_tick'] == 500
    m = R.parse(payload(team=['mirror'] + DECK_A[1:]))
    assert R.classify(m, names - {'Mirror'})['tier'] == 'unsupported-card'


def brute(seq, deck):
    """Reference: simulate every (hand, queue) with an explicit 4-slot hand and refill."""
    out = []
    for hand in itertools.combinations(deck, 4):
        for queue in itertools.permutations([c for c in deck if c not in hand]):
            h, q, ok = list(hand), deque(queue), True
            for c in seq:
                if c not in h:
                    ok = False
                    break
                h[h.index(c)] = q.popleft()
                q.append(c)
            if ok:
                out.append((hand, queue))
    return out


def test_infer_cycle_matches_reference_and_rejects():
    deck = list('abcdefgh')
    seq = list('aebfcgdhae')
    got = R.infer_cycle(seq, deck)
    assert got == brute(seq, deck)
    assert all(len(set(h)) == 4 and set(h) | set(q) == set(deck) for h, q in got)
    # 'a' replayed after only 3 other plays: impossible in the ordinary cycle
    assert R.infer_cycle(list('abcda'), deck) == []
    # the full sequence, not only first use, constrains: a first-use-consistent opening hand {a,b,c,e} with queue
    # (d,f,g,h) fails at the replay of 'a' (it is 5th in the queue after 'b','c','e','d' leave)
    seq = list('abcedfgha')
    got = R.infer_cycle(seq, deck)
    assert got == brute(seq, deck) and (tuple('abce'), tuple('dfgh')) in got
    assert R.infer_cycle(list('abcedfgahb'), deck) == brute(list('abcedfgahb'), deck)
    assert R.cycle_summary(got)['n'] == len(got) > 0


def test_first_use_order():
    assert R.first_use_order(list('caac'), list('abcdefgh')) == (('c', 'a', 'b', 'd'), ('e', 'f', 'g', 'h'))


def test_score_lane_invariant():
    m = R.parse(payload())
    m.final_hp = [(7000, 0, 4000), (0, 3000, 2000)]
    eng = dict(terminal=True, winner=0, crowns=(1, 0), hp=[(7000, (0, 4000)), (0, (0, 0))])
    s = R.score(m, eng)
    assert s['winner'] and s['crowns'] and s['six_hp'] and sum(s['hp_abs_err']) == 0
    eng['hp'][0] = (7000, (100, 4000))
    s = R.score(m, eng)
    assert not s['six_hp'] and sum(s['hp_abs_err']) == 100


def test_native50_rule_is_documented_rule():
    # 20 evenly spaced indices of a 5,000-row pool (study.py prepare); rows 0 and 526 are named in levelled_order.py
    idx = [round(i * 4999 / 19) for i in range(20)]
    assert idx[0] == 0 and idx[2] == 526 and idx[-1] == 4999


# -- engine-backed -------------------------------------------------------------------------------------------------
clasher = pytest.importorskip('clasher.battle')


def test_engine_strict_injection_counts_and_no_forcing():
    events = [(150, 'team', 'knight', 9500, 8500), (160, 'opponent', 'goblins', 9500, 22500),
              # 'cannon' is in team's queue under the inferred plan only after 4 plays: strict tier must reject it
              (170, 'team', 'giant', 9500, 8500)]
    m = R.parse(payload(events=events))
    r = R.simulate(m, R.CONFIGS['main'])
    assert r['status'] == 'ran'
    c = r['commands']
    assert c['injected'] + c.get('elixir', 0) + c.get('not_in_hand', 0) + c.get('placement', 0) == 3
    assert r['engine']['terminal'] and r['level_map']['towers'] == [16, 16]


def test_engine_tick_offset_and_slack():
    # two expensive plays 1 tick apart: strict rejects the second for elixir, slack 40 cannot reach 5 elixir either
    events = [(100, 'team', 'giant', 9500, 8500), (101, 'team', 'musketeer', 9500, 8500)]
    m = R.parse(payload(events=events))
    strict = R.simulate(m, R.Config('t', slack=0))
    assert strict['commands'].get('elixir') == 1
    slack = R.simulate(m, R.Config('t', slack=40))
    assert slack['commands'].get('elixir') == 1
    slack = R.simulate(m, R.Config('t', slack=400))
    assert slack['commands'].get('injected') == 2 and slack['wait_ticks']['n'] == 1
