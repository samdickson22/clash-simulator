import json

from bot.livediag import behaviour_diag as bd

TABLE = dict(card_cost={'Zap': 2.0, 'Fireball': 4.0, 'Barbarians': 5.0, 'Archers': 3.0, 'Giant': 5.0},
             card_unit_value={'Barbarians': 1.0, 'Archers': 1.5, 'Giant': 5.0},
             body_card={'Barbarian': 'Barbarians', 'Archer': 'Archers', 'Giant': 'Giant'},
             body_hp={'Barbarian': 716.0, 'Archer': 304.0, 'Giant': 3968.0}, card_hp={},
             spell={'Zap': dict(radius=2.5, damage=192.0), 'Fireball': dict(radius=2.5, damage=688.0)})


def table(tmp_path):
    p = tmp_path / 't.json'
    p.write_text(json.dumps(TABLE))
    return bd.Table(p)


def test_windows_and_casts(tmp_path):
    t = table(tmp_path)
    archers = [(10.0, 14.0, 1.5, 304.0), (10.5, 14.0, 1.5, 304.0), (11.0, 14.5, 1.5, 304.0)]
    barbs = [(14.0, 14.0, 1.0, 716.0), (14.5, 14.0, 1.0, 716.0), (15.0, 14.5, 1.0, 716.0), (14.5, 15.0, 1.0, 716.0),
             (15.0, 15.0, 1.0, 716.0)]
    polls = [(0, archers + barbs, ['Fireball', 'Giant'], 5.0),     # Fireball window (archers 4.5 elixir < 5: barbs 5)
             (10, archers + barbs, ['Fireball', 'Giant'], 5.0),    # same window (gap <= 20)
             (100, archers, ['Fireball', 'Giant'], 2.0),           # lethal: archers 4.5 < 5 -> no window at all
             (200, barbs, ['Zap', 'Giant'], 1.0),                  # Zap window (barbs), unaffordable -> short
             (300, [(9.0, 30.0, 5.0, 3968.0)], ['Zap'], 9.0)]      # single tank: no window
    plays = [(310, 'Zap', 9.0, 25.0)]                               # no unit within 2.5 of the target: tower-only
    m, pushes, giants = bd.game_metrics(polls, plays, t)
    assert m['missed_windows'] == 1 and m['short_windows'] == 1
    assert m['lethal_missed_windows'] == 0 and m['lethal_short_windows'] == 0
    assert m['spell_casts'] == 1 and m['tower_only_casts'] == 1 and m['swarm_casts'] == 0
    assert pushes == [5.0, 1.0]        # right lane (x >= 9) at t=0, again at t=200 (>= 100 ticks after t=100)


def test_cast_inside_window_is_taken(tmp_path):
    t = table(tmp_path)
    archers = [(10.0, 14.0, 1.5, 304.0), (10.5, 14.0, 1.5, 304.0), (11.0, 14.5, 1.5, 304.0), (10.2, 14.4, 1.5, 304.0)]
    m, _, _ = bd.game_metrics([(0, archers, ['Fireball'], 4.5)], [(15, 'Fireball', 10.5, 14.5)], t)
    assert m['taken_window_polls'] == 1 and m['lethal_taken_window_polls'] == 1 and m['missed_windows'] == 0
    assert m['swarm_casts'] == 1


def test_names(tmp_path):
    t = table(tmp_path)
    assert t.unit_info('barbarian') == (1.0, 716.0)
    assert t.unit_info('Archer') == (1.5, 304.0)
    assert t.unit_info('nothing') == (0.0, None)


def test_swarm_response_and_accounting(tmp_path):
    TABLE2 = dict(TABLE, card_cost=dict(TABLE['card_cost'], SpearGoblins=2.0, Log=2.0),
                  card_unit_value=dict(TABLE['card_unit_value'], SpearGoblins=0.6667),
                  spell=dict(TABLE['spell'], Log=dict(radius=1.95, damage=290.0)))
    p = tmp_path / 't2.json'
    p.write_text(json.dumps(TABLE2))
    t = bd.Table(p)
    assert t.swarm('SpearGoblins') and t.swarm('Barbarians') and not t.swarm('Giant')
    assert t.card('the-log') == 'Log' and t.card('spear-goblins') == 'SpearGoblins'
    opp = [(100, 'Barbarians'), (400, 'SpearGoblins'), (700, 'Giant')]
    assert bd.swarm_response(opp, [(150, 'Zap'), (600, 'Fireball')], t) == (2, 1)
    assert bd.swarm_response(opp, [(150, 'Giant')], t) == (0, 0)
    el = bd.elixir_accounting([(0, 'Giant'), (56 * 3, 'Zap'), (2400 + 28, 'Zap')], t)
    assert el[0] == 5.0 and abs(el[1] - 3.0) < 1e-9 and el[2] == 10.0
