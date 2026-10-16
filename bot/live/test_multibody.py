"""Multi-body play counting: one deployment = ONE play (one elixir cost, one cycle step), never one per body; production
and death spawns are never plays; a label flip on a body already on the board is never a play (bot/live/births.py).

    PYTHONPATH=. nice -n 19 taskset -c 2-5 python -m pytest -q bot/live/test_multibody.py

Needs the frozen runtime (CLASHER_BOT_RUNTIME, ~15 s setup); no games are played. Synthetic perception records: the
opponent's units at their real body counts, spread like their formations, walking towards us, one record every 2-3
ticks with seeded detection misses and per-frame label noise inside the sprite family.
"""
import math
import random

import pytest

OWN = ['Knight', 'Archers', 'Giant', 'Musketeer', 'MiniPekka', 'Fireball', 'Arrows', 'Minions']


@pytest.fixture(scope='module')
def rt():
    from bot.players.runtime import Runtime
    return Runtime()


@pytest.fixture(scope='module')
def cb(rt):
    from bot.live.births import CardBodies
    return CardBodies(rt)


def ring(n, r, cx, cy, phase=0.):
    if n == 1:
        return [(cx, cy)]
    return [(cx + r*math.cos(phase + 2*math.pi*k/n), cy + r*math.sin(phase + 2*math.pi*k/n)) for k in range(n)]


class Scene:
    """Bodies [(id, labels, x, y, vx, vy, born, dies)] -> per-record unit tuples (card, owner=1, x, y, score)."""

    def __init__(self, seed=0, miss=.1, step=(2, 3)):
        self.bodies, self.rng, self.miss, self.step = [], random.Random(seed), miss, step

    def add(self, labels, pts, t0, *, vy=-.05, life=400, flip=0.):
        for x, y in pts:
            self.bodies.append(dict(labels=list(labels), x=x, y=y, vy=vy, t0=t0, t1=t0 + life, flip=flip))

    def run(self, tracker, until, tower_alive=None):
        plays, tick = [], 1
        while tick <= until:
            units = []
            for b in self.bodies:
                if not b['t0'] <= tick <= b['t1'] or self.rng.random() < self.miss:
                    continue
                y = b['y'] + b['vy']*(tick - b['t0'])
                lab = b['labels'][0] if self.rng.random() >= b['flip'] else self.rng.choice(b['labels'])
                units.append((lab, 1, b['x'], y, .9))
            _, p = tracker.update(tick, units, tower_alive or {'left': True, 'right': True})
            plays += [q for q in p if q[0] == 1]
            tick += self.rng.choice(self.step)
        return plays


def tracker(cb, **kw):
    from bot.live.births import UnitTracker
    return UnitTracker(cb, **kw)


# -- one deployment = one play, card inferred once from the burst ------------------------------------------------
@pytest.mark.parametrize('card,n,radius,labels,expect', [
    ('SkeletonArmy', 15, 2.3, ('SkeletonArmy', 'Skeletons'), 'SkeletonArmy'),   # wider than vote_tiles from its edge
    ('SkeletonArmy', 15, 2.3, ('Skeletons',), 'SkeletonArmy'),                  # every label wrong: count decides
    ('Skeletons', 3, .6, ('Skeletons', 'SkeletonArmy'), 'Skeletons'),
    ('Goblins', 4, .8, ('Goblins', 'GoblinGang'), 'Goblins'),
    ('GoblinGang', 6, 1.4, ('GoblinGang', 'Goblins'), 'GoblinGang'),
    ('GoblinGang', 6, 1.4, ('Goblins',), 'GoblinGang'),                         # 6 > Goblins' 4 bodies
    ('Minions', 3, .8, ('Minions', 'MinionHorde'), 'Minions'),
    ('MinionHorde', 6, 1.6, ('Minions',), 'MinionHorde'),                       # 6 > Minions' 3 bodies
    ('Bats', 5, 1.5, ('Bats',), 'Bats'),
    ('Archers', 2, 1., ('Archers',), 'Archers'),
    ('Wallbreakers', 2, .8, ('Wallbreakers',), 'Wallbreakers'),
    ('RoyalHogs', 4, 1.8, ('RoyalHogs',), 'RoyalHogs'),
    ('Rascals', 3, 2.2, ('Rascals',), 'Rascals'),
    ('Goblinstein', 2, 1., ('Goblinstein',), 'Goblinstein'),
    ('AngryBarbarians', 2, 1., ('AngryBarbarians',), 'AngryBarbarians'),
])
def test_one_deployment_is_one_play(cb, card, n, radius, labels, expect):
    for seed in range(4):
        s = Scene(seed)
        s.add(labels, ring(n, radius, 9., 22., phase=seed), 100, flip=.3 if len(labels) > 1 else 0.)
        plays = s.run(tracker(cb), 600)
        assert [p[1] for p in plays] == [expect], (seed, plays)
        x, y = plays[0][2:4]
        assert math.hypot(x - 9., y - 22.) < 1.5, plays          # at the formation centre, not its first body
        assert 100 <= plays[0][4] <= 106


def test_card_counts_come_from_one_deployment(cb):
    assert {c: cb.count[c] for c in ('Skeletons', 'SkeletonArmy', 'Goblins', 'GoblinGang', 'Minions', 'MinionHorde',
                                     'Bats', 'Archers', 'RoyalHogs', 'Rascals', 'Knight')} == dict(
        Skeletons=3, SkeletonArmy=15, Goblins=4, GoblinGang=6, Minions=3, MinionHorde=6, Bats=5, Archers=2,
        RoyalHogs=4, Rascals=3, Knight=1)
    fam = {f: sorted(m) for f, m in cb.families.items() if len(m) > 1}
    assert fam == {'FireSpirits': ['FireSpirits', 'FirespiritHut'], 'GoblinGang': ['GoblinGang', 'GoblinHut', 'Goblins'],
                   'MinionHorde': ['MinionHorde', 'Minions'], 'SkeletonArmy': ['SkeletonArmy', 'Skeletons']}


def test_burst_size_beats_labels_but_labels_choose_among_fitting_cards(cb):
    t = tracker(cb)
    from collections import Counter
    assert t.infer_card('SkeletonArmy', Counter(Skeletons=5.), 8) == 'SkeletonArmy'    # 8 bodies cannot be Skeletons
    assert t.infer_card('SkeletonArmy', Counter(SkeletonArmy=2.), 2) == 'SkeletonArmy'  # both fit: the burst's labels
    assert t.infer_card('SkeletonArmy', Counter(Skeletons=2.), 2) == 'Skeletons'
    assert t.infer_card('SkeletonArmy', Counter(), 2) == 'Skeletons'                    # body-level labels: smallest fit
    assert t.infer_card('MinionHorde', Counter(Minions=4.), 4) == 'MinionHorde'


def test_spawn_card_hint_decides(cb):
    s = Scene(1, miss=0.)
    s.add(('Skeletons',), ring(2, .5, 9., 22.), 100)
    from bot.live.births import UnitTracker
    t = UnitTracker(cb)
    plays, tick = [], 1
    while tick < 300:
        units = [(lab, 1, x, y + -.05*(tick - 100), .9, 'SkeletonArmy') for b in s.bodies if b['t0'] <= tick
                 for lab, x, y in [(b['labels'][0], b['x'], b['y'])]]
        plays += t.update(tick, units, {})[1]
        tick += 2
    assert [p[1] for p in plays] == ['SkeletonArmy']


# -- two deployments are two plays ---------------------------------------------------------------------------------
def test_same_card_twice_after_a_cycle_is_two_plays(cb):
    s = Scene(2)
    s.add(('Skeletons',), ring(3, .6, 4., 24.), 100, life=120)
    for k, c in enumerate(('Knight', 'Musketeer', 'Valkyrie', 'Giant')):    # four other plays: Skeletons cycles back
        s.add((c,), [(9. + 3*k, 26.)], 130 + 20*k, life=200)
    s.add(('Skeletons', 'SkeletonArmy'), ring(3, .6, 4.5, 24.5), 230, flip=.3)
    plays = s.run(tracker(cb), 600)
    assert [p[1] for p in plays].count('Skeletons') == 2, plays
    assert len(plays) == 6


def test_same_card_after_the_repeat_window_is_two_plays(cb):
    s = Scene(3)
    s.add(('Goblins',), ring(4, .8, 4., 24.), 100, life=150)
    s.add(('Goblins',), ring(4, .8, 14., 24.), 100 + 200)
    assert [p[1] for p in s.run(tracker(cb), 700)] == ['Goblins', 'Goblins']


def test_different_cards_side_by_side_are_two_plays(cb):
    s = Scene(4)
    s.add(('SkeletonArmy',), ring(15, 2.2, 6., 23.), 100)
    s.add(('Giant',), [(12.5, 24.)], 104)
    assert sorted(p[1] for p in s.run(tracker(cb), 500)) == ['Giant', 'SkeletonArmy']


# -- spawns and relabels are never plays ---------------------------------------------------------------------------
@pytest.mark.parametrize('seed', range(4))
def test_goblin_hut_spawns_are_not_plays(cb, seed):
    s = Scene(seed)
    s.add(('GoblinHut',), [(4.5, 26.5)], 100, vy=0., life=1200)
    for k in range(8):                 # one spear goblin every ~3 s, labelled as the hut or as goblins, walking off
        s.add(('GoblinHut', 'Goblins', 'GoblinGang'), [(4.5, 25.6)], 160 + 60*k, vy=-.05, life=150, flip=.5)
    assert [p[1] for p in s.run(tracker(cb), 1300)] == ['GoblinHut']


@pytest.mark.parametrize('seed', range(4))
def test_firespirit_hut_spawns_are_not_plays(cb, seed):
    s = Scene(seed)
    s.add(('FirespiritHut',), [(14.5, 26.5)], 100, vy=0., life=1200)
    for k in range(6):
        s.add(('FirespiritHut', 'FireSpirits'), [(14.5, 25.6)], 200 + 120*k, vy=-.12, life=60, flip=.5)
    assert [p[1] for p in s.run(tracker(cb), 1300)] == ['FirespiritHut']


def test_goblins_next_to_a_lost_hut_are_a_play(cb):
    s = Scene(12, miss=.05)
    s.add(('GoblinHut',), [(14.5, 19.5)], 100, vy=0., life=100)      # a building, then lost (destroyed or missed)
    s.add(('Goblins',), ring(4, .8, 14., 18.5), 600)                 # four goblins deployed at the bridge beside it
    assert [p[1] for p in s.run(tracker(cb), 900)] == ['GoblinHut', 'Goblins']


def test_hut_missed_for_20_s_is_not_replayed(cb):
    s = Scene(11, miss=.05)
    s.add(('GoblinHut',), [(4.5, 26.5)], 100, vy=0., life=60)         # seen, then lost by perception for 20 s
    s.add(('GoblinHut',), [(4.9, 26.1)], 560, vy=0., life=130)        # re-detected within its 30 s, jittered
    s.add(('GoblinHut', 'Goblins'), [(4.5, 25.6)], 580, vy=-.05, life=150, flip=.5)
    assert [p[1] for p in s.run(tracker(cb), 900)] == ['GoblinHut']


def test_hut_seen_past_its_lifetime_is_a_new_play(cb):
    s = Scene(11, miss=.05)
    s.add(('GoblinHut',), [(4.5, 26.5)], 100, vy=0., life=100)
    s.add(('GoblinHut',), [(4.9, 26.1)], 800, vy=0., life=300)        # 35 s after the first: a hut lives 30 s
    assert [p[1] for p in s.run(tracker(cb), 1200)] == ['GoblinHut', 'GoblinHut']


def test_golemites_are_not_plays(cb):
    s = Scene(7, miss=.05)
    s.add(('Golem',), [(9., 30.)], 100, vy=-.02, life=500)            # dies at y = 20 (our tower destroyed it early)
    s.add(('Golem',), ring(2, .7, 9., 20.), 602, vy=-.03, life=300)    # its two golemites (labelled Golem)
    assert [p[1] for p in s.run(tracker(cb), 1000)] == ['Golem']


def test_lone_leftover_relabelled_mid_fight_is_no_play(cb):
    s = Scene(8, miss=.15)
    s.add(('SkeletonArmy',), ring(15, 2.2, 9., 28.), 100, life=100)
    # one survivor (the ring's first body) keeps walking on the opponent side, its label a coin flip between the
    # two skeleton cards
    s.add(('SkeletonArmy', 'Skeletons'), [(9. + 2.2, 28. - .05*101)], 201, life=400, flip=.5)
    assert [p[1] for p in s.run(tracker(cb), 700)] == ['SkeletonArmy']


def test_swarm_lost_in_a_detection_gap_is_no_new_play(cb):
    s = Scene(9, miss=.05)
    s.add(('Minions',), ring(3, .8, 9., 26.), 100, life=60)
    s.add(('Minions', 'MinionHorde'), [(9.5, 26. - 6.)], 220, vy=-.04, life=200, flip=.3)    # 6 tiles on, 6 s later
    assert [p[1] for p in s.run(tracker(cb), 600)] == ['Minions']


def test_cross_family_relabel_of_a_body_is_no_play(cb):
    t, plays = tracker(cb), []
    for tick in range(100, 400, 3):
        lab = 'Valkyrie' if 200 <= tick < 215 else 'Knight'      # the Knight is read as a Valkyrie for 5 frames
        plays += t.update(tick, [(lab, 1, 9., 26. - .03*(tick - 100), .9)], {})[1]
    assert [p[1] for p in plays] == ['Knight']


# -- end to end: one elixir charge and one cycle step per deployment -------------------------------------------------
def test_translator_charges_one_play_per_deployment(rt):
    from bot.live.translate import LiveTranslator
    tr = LiveTranslator(rt, OWN)
    s = Scene(10, miss=.1)
    s.add(('SkeletonArmy', 'Skeletons'), ring(15, 2.2, 9., 23.), 300, flip=.3)
    s.add(('GoblinGang', 'Goblins'), ring(6, 1.4, 4., 25.), 700, flip=.3)
    tick, info = 250, None
    rng = random.Random(0)
    while tick < 1100:
        units = [dict(cls=lab, card=lab, owner=1, x=b['x'], y=b['y'] - .05*(tick - b['t0']), hp_frac=1., score=.9)
                 for b in s.bodies if b['t0'] <= tick <= b['t1'] and rng.random() > .1
                 for lab in [b['labels'][0] if rng.random() > .3 else rng.choice(b['labels'])]]
        info = tr.information(dict(tick=tick, units=units, towers=[], hand=dict(cards=OWN[:4], next=OWN[4]),
                                   elixir=5., events=[]))
        tick += 5
    assert [(e.name) for e in info.events] == ['SkeletonArmy', 'GoblinGang']
    m = tr._mirrors[1]
    assert list(m.queue)[-2:] == ['SkeletonArmy', 'GoblinGang'] and m.revealed == {'SkeletonArmy', 'GoblinGang'}
    assert [e['name'] for e in tr.public_events if e['seat'] == 1] == ['SkeletonArmy', 'GoblinGang']


# -- Sol review r1 reproducers (scratch/live-review/multibody-r1/test_review.py), verbatim scenes ---------------------
def exact(cb, s, until=1000):
    return [p[1] for p in s.run(tracker(cb), until)]


def clean():
    return Scene(0, miss=0., step=(2,))


def test_r1_real_goblins_beside_visible_hut(cb):
    s = clean()
    s.add(('GoblinHut',), [(4.5, 26.5)], 100, vy=0., life=1000)
    s.add(('Goblins',), ring(4, .6, 4.5, 24.5), 200, life=150)
    assert exact(cb, s) == ['GoblinHut', 'Goblins']


def test_r1_distinct_smaller_card_in_opposite_lane(cb):
    s = clean()
    s.add(('SkeletonArmy',), ring(15, 2.2, 4., 26.), 100, life=250)
    s.add(('Skeletons',), ring(3, .6, 14., 26.), 160, life=250)
    assert exact(cb, s) == ['SkeletonArmy', 'Skeletons']


def test_r1_building_replacement_after_valid_cycle(cb):
    s = clean()
    s.add(('Cannon',), [(4., 22.)], 100, vy=0., life=40)
    for k, c in enumerate(('Knight', 'IceSpirit', 'Skeletons', 'Goblins')):
        s.add((c,), [(12., 26.)], 220 + 100*k, life=40)
    s.add(('Cannon',), [(4., 22.)], 700, vy=0., life=100)
    assert exact(cb, s) == ['Cannon', 'Knight', 'IceSpirit', 'Skeletons', 'Goblins', 'Cannon']


def test_r1_real_fire_spirit_beside_visible_hut(cb):
    t, plays = tracker(cb), []
    for tick in range(100, 500, 2):
        units = [('FirespiritHut', 1, 4.5, 26.5, .9)]
        if 200 <= tick <= 280:
            units.append(('FireSpirits', 1, 4.5, 25. - .12*(tick-200), .9, 'FireSpirits'))
        plays += t.update(tick, units, {})[1]
    assert [p[1] for p in plays] == ['FirespiritHut', 'FireSpirits']


def test_r1_miner_does_not_absorb_later_knight(cb):
    s = clean()
    s.add(('Miner',), [(9., 29.)], 100, vy=-.4, life=60)
    s.add(('Miner',), [(9., 5.)], 162, vy=0., life=200)
    s.add(('Knight',), [(9., 29.)], 150, vy=-.03, life=200)
    assert sorted(exact(cb, s)) == ['Knight', 'Miner']


def test_r1_lost_fire_hut_retains_spawner_memory(cb):
    s = clean()
    s.add(('FirespiritHut',), [(4.5, 26.5)], 100, vy=0., life=60)
    s.add(('FireSpirits',), [(4.5, 25.)], 660, vy=-.12, life=80)
    assert exact(cb, s) == ['FirespiritHut']


# -- audit: every path that can suppress, absorb, revive or defer a birth (MULTIBODY.md table, one row each) ---------
def hinted(cb, scenes, until, hint_cards, after=0, first_only=False):
    """Scene bodies deployed from tick `after` whose label is in hint_cards carry it as spawn_card (provenance); with
    first_only, only on their first frame (a perception that infers the card once, at spawn)."""
    t, plays, tick = tracker(cb), [], 1
    s = scenes
    while tick <= until:
        units = []
        for b in s.bodies:
            if b['t0'] <= tick <= b['t1']:
                lab = b['labels'][0]
                u = (lab, 1, b['x'], b['y'] + b['vy']*(tick - b['t0']), .9)
                hint = lab in hint_cards and b['t0'] >= after and (not first_only or tick < b['t0'] + 2)
                units.append(u + ((lab,) if hint else ()))
        plays += [p[1] for p in t.update(tick, units, {})[1]]
        tick += 2
    return plays


# R1 death child
def test_audit_death_child_needs_proximity(cb):
    s = clean()
    s.add(('Golem',), [(9., 30.)], 100, vy=-.02, life=500)            # vanishes at y = 20
    s.add(('Golem',), [(11.5, 20.)], 602, vy=-.03, life=200)          # 2.5 tiles away: not its golemite
    assert exact(cb, s) == ['Golem', 'Golem']


def test_audit_death_child_needs_recency(cb):
    s = clean()
    s.add(('Golem',), [(9., 30.)], 100, vy=-.02, life=500)
    for k, c in enumerate(('Knight', 'IceSpirit', 'Skeletons', 'Goblins')):    # Golem cycles back
        s.add((c,), [(3. + 4*k, 27.)], 605 + 20*k, life=30)
    s.add(('Golem',), [(9., 20.)], 700, vy=-.03, life=200)            # 5 s after it vanished, where it vanished
    assert exact(cb, s) == ['Golem', 'Knight', 'IceSpirit', 'Skeletons', 'Goblins', 'Golem']


def test_audit_death_child_yields_to_provenance(cb):
    s = clean()
    s.add(('Golem',), [(9., 30.)], 100, vy=-.02, life=500)
    s.add(('Golem',), [(9.5, 20.)], 602, vy=-.03, life=200)
    assert hinted(cb, s, 1000, {'Golem'}, after=602) == ['Golem', 'Golem']


# R2 production spawn
def test_audit_spawn_needs_proximity(cb):
    s = clean()
    s.add(('FirespiritHut',), [(4.5, 26.5)], 100, vy=0., life=900)
    s.add(('FireSpirits',), [(8.5, 26.5)], 300, vy=-.12, life=80)     # 4 tiles from the hut: a play
    assert exact(cb, s) == ['FirespiritHut', 'FireSpirits']


def test_audit_spawn_needs_a_spawner_within_memory(cb):
    s = clean()
    s.add(('FirespiritHut',), [(4.5, 26.5)], 100, vy=0., life=60)
    s.add(('FireSpirits',), [(4.5, 25.)], 1700, vy=-.12, life=80)     # 77 s after its last sighting
    assert exact(cb, s, 2000) == ['FirespiritHut', 'FireSpirits']


def test_audit_spawn_needs_movement(cb):
    s = clean()
    s.add(('GoblinHut',), [(4.5, 26.5)], 100, vy=0., life=900)
    for k, c in enumerate(('Knight', 'IceSpirit', 'Skeletons', 'Minions')):    # the hut cycles back
        s.add((c,), [(10. + 2*k, 27.)], 200 + 40*k, life=30)
    s.add(('GoblinHut',), [(7.5, 26.5)], 400, vy=0., life=300)        # a second hut beside it stands still
    assert exact(cb, s) == ['GoblinHut', 'Knight', 'IceSpirit', 'Skeletons', 'Minions', 'GoblinHut']


# R3 leftover
def test_audit_leftover_has_a_time_bound(cb):
    s = clean()
    s.add(('Minions',), ring(3, .8, 9., 26.), 100, life=60)
    s.add(('Minions',), [(9.5, 18.)], 330, vy=-.04, life=200)         # 11.5 s later: beyond repeat_ticks
    assert exact(cb, s, 700) == ['Minions', 'Minions']


def test_audit_leftover_needs_continuity(cb):
    s = clean()
    s.add(('SkeletonArmy',), ring(15, 2.2, 4., 26.), 100, life=60)   # lost after 3 s on the left
    s.add(('Skeletons',), ring(3, .6, 14., 26.), 220, life=200)        # 3 s later on the right: not its bodies
    assert exact(cb, s, 600) == ['SkeletonArmy', 'Skeletons']


def test_audit_leftover_allows_a_cycled_card(cb):
    s = clean()
    s.add(('Skeletons',), ring(3, .6, 4., 24.), 100, vy=0., life=120)  # fighting in place, then lost
    for k, c in enumerate(('Knight', 'Musketeer', 'Valkyrie', 'Giant')):
        s.add((c,), [(9. + 3*k, 26.)], 130 + 20*k, life=200)
    s.add(('Skeletons',), ring(2, .5, 4., 21.5), 240, life=200)       # 2 bodies within reach of the lost ones
    assert exact(cb, s, 600) == ['Skeletons', 'Knight', 'Musketeer', 'Valkyrie', 'Giant', 'Skeletons']


def test_audit_leftover_yields_to_provenance(cb):
    s = clean()
    s.add(('Minions',), ring(3, .8, 9., 26.), 100, life=60)
    s.add(('Minions',), [(9.5, 20.)], 220, vy=-.04, life=200)
    assert hinted(cb, s, 600, {'Minions'}, after=220) == ['Minions', 'Minions']


# R4 revival
def test_audit_revival_yields_to_provenance(cb):
    s = clean()
    s.add(('Cannon',), [(4., 22.)], 100, vy=0., life=40)
    s.add(('Cannon',), [(4., 22.)], 580, vy=0., life=100)             # remembered (not live) by now
    assert hinted(cb, s, 800, {'Cannon'}, after=580) == ['Cannon', 'Cannon']
    assert hinted(cb, s, 800, {'Cannon'}, after=580, first_only=True) == ['Cannon', 'Cannon']


# R5 duplicate
def test_audit_duplicate_needs_no_bigger_burst(cb):
    s = clean()
    s.add(('Skeletons',), ring(3, .5, 9., 25.), 100, life=300)
    s.add(('SkeletonArmy',), ring(15, 2., 9., 22.5), 120, life=300)   # 1 s later, touching: a second deployment
    assert exact(cb, s, 600) == ['Skeletons', 'SkeletonArmy']


def test_audit_duplicate_needs_adjacency(cb):
    s = clean()
    s.add(('SkeletonArmy',), ring(15, 2.2, 4., 26.), 100, life=250)
    s.add(('Skeletons',), ring(3, .6, 14., 26.), 120, life=250)       # 1 s later, the other lane
    assert exact(cb, s) == ['SkeletonArmy', 'Skeletons']


# R6 late body of a deployment never tracked on its own
def test_audit_late_body_needs_room(cb):
    s = clean()
    s.add(('SkeletonArmy',), ring(15, 2.2, 6., 26.), 100, life=300)  # all 15 tracked
    s.add(('Skeletons',), [(8.6, 21.)], 200, vy=-.05, life=200)       # one more skeleton beside it: a new card
    assert exact(cb, s, 600) == ['SkeletonArmy', 'Skeletons']


def test_audit_late_body_needs_adjacency(cb):
    s = clean()
    s.add(('SkeletonArmy',), ring(14, 2.2, 6., 26.), 100, life=300)  # 14 of 15 seen
    s.add(('Skeletons',), [(14., 21.)], 200, vy=-.05, life=200)       # a lone skeleton across the arena
    assert exact(cb, s, 600) == ['SkeletonArmy', 'Skeletons']


def test_audit_late_body_yields_to_provenance(cb):
    s = clean()
    s.add(('SkeletonArmy',), ring(14, 2.2, 6., 26.), 100, life=300)
    s.add(('Skeletons',), [(8.5, 21.)], 200, vy=-.05, life=200)
    assert hinted(cb, s, 600, {'Skeletons'}, after=200) == ['SkeletonArmy', 'Skeletons']


# R7 tunnel deferral
def test_audit_tunnel_has_a_time_bound(cb):
    s = clean()
    s.add(('Miner',), [(9., 29.)], 100, vy=-.2, life=600)             # never stops: emitted after tunnel_ticks
    assert exact(cb, s, 600) == ['Miner']


# R8 cross-family relabel continuation
def test_audit_relabel_needs_proximity(cb):
    t, plays = tracker(cb), []
    for tick in range(100, 400, 3):
        units = [('Knight', 1, 9., 26. - .03*(tick - 100), .9)] if tick < 200 else []
        if tick >= 200:
            units.append(('Valkyrie', 1, 11., 23., .9))                # 2 tiles from the vanished Knight
        plays += t.update(tick, units, {})[1]
    assert [p[1] for p in plays] == ['Knight', 'Valkyrie']


def test_audit_relabel_yields_to_provenance(cb):
    t, plays = tracker(cb), []
    for tick in range(100, 400, 3):
        units = [('Knight', 1, 9., 26. - .03*(tick - 100), .9)] if tick < 200 else \
            [('Valkyrie', 1, 9., 23., .9) + (('Valkyrie',) if tick < 203 else ())]    # card inferred once, at spawn
        plays += t.update(tick, units, {})[1]
    assert [p[1] for p in plays] == ['Knight', 'Valkyrie']


# R9 closed-cluster absorption; R10 open-cluster joining across families
def test_audit_double_detection_is_one_play(cb):
    t, plays = tracker(cb), []
    for tick in range(100, 300, 3):
        units = [('Knight', 1, 9., 26. - .03*(tick - 100), .9)]
        if 112 <= tick <= 118:
            units.append(('Valkyrie', 1, 9.2, 26.1 - .03*(tick - 100), .9))   # the same body, a second label
        plays += t.update(tick, units, {})[1]
    assert [p[1] for p in plays] == ['Knight']


def test_audit_card_deployed_behind_another_is_a_play(cb):
    s = clean()
    s.add(('Giant',), [(9., 24.)], 100, vy=-.03)
    s.add(('Musketeer',), [(9., 25.5)], 120, vy=-.03)                # 1.5 tiles behind, 1 s later
    assert exact(cb, s, 500) == ['Giant', 'Musketeer']


def test_audit_two_cards_deployed_together_are_two_plays(cb):
    s = clean()
    s.add(('Giant',), [(9., 24.)], 100, vy=-.03)
    s.add(('Musketeer',), [(10.5, 24.)], 100, vy=-.03)               # the same frame, 1.5 tiles apart
    assert sorted(exact(cb, s, 500)) == ['Giant', 'Musketeer']


# R11 deploy zone; R12 confirmation
def test_audit_deploy_zone_opens_when_our_tower_falls(cb):
    t, plays = tracker(cb), []
    for tick in range(100, 300, 3):
        plays += t.update(tick, [('Knight', 1, 4., 12. - .03*(tick - 100), .9)], {'left': False, 'right': True})[1]
    assert [p[1] for p in plays] == ['Knight']
    t, plays = tracker(cb), []
    for tick in range(100, 300, 3):
        plays += t.update(tick, [('Knight', 1, 4., 12. - .03*(tick - 100), .9)], {'left': True, 'right': True})[1]
    assert plays == []


def test_audit_one_frame_is_no_play_two_frames_are(cb):
    t = tracker(cb)
    assert t.update(100, [('Knight', 1, 9., 26., .9)], {})[1] == [] and all(
        not t.update(k, [], {})[1] for k in range(103, 200, 3))
    t, plays = tracker(cb), []
    for tick, units in ((100, [('Knight', 1, 9., 26., .9)]), (103, [('Knight', 1, 9., 25.9, .9)])) + \
            tuple((k, []) for k in range(106, 200, 3)):
        plays += t.update(tick, units, {})[1]
    assert [p[1] for p in plays] == ['Knight']


# R14 champion relocation
def test_audit_champion_relocated_by_its_ability_is_no_play(cb):
    s = clean()
    s.add(('MightyMiner',), [(4., 22.)], 100, vy=-.03, life=150)
    s.add(('MightyMiner',), [(14., 20.)], 260, vy=-.03, life=200)     # Explosive Escape: the other lane
    assert exact(cb, s, 600) == ['MightyMiner']


def test_audit_champion_after_a_cycle_is_a_play(cb):
    s = clean()
    s.add(('MightyMiner',), [(4., 22.)], 100, vy=-.03, life=150)
    for k, c in enumerate(('Knight', 'Musketeer', 'Valkyrie', 'Giant')):
        s.add((c,), [(3. + 4*k, 27.)], 260 + 20*k, life=100)
    s.add(('MightyMiner',), [(14., 20.)], 360, vy=-.03, life=200)
    assert exact(cb, s, 700) == ['MightyMiner', 'Knight', 'Musketeer', 'Valkyrie', 'Giant', 'MightyMiner']


# -- public API (bot/live/revealed.py and others may rely on these; MULTIBODY.md) --------------------------------------
def _army_frames():
    s = Scene(3)
    s.add(('SkeletonArmy', 'Skeletons'), ring(15, 2.2, 6., 24.), 100, flip=.3)
    s.add(('GoblinGang', 'Goblins'), ring(6, 1.4, 13., 25.), 140, flip=.3)
    s.add(('GoblinHut',), [(3.5, 28.5)], 60, vy=0., life=900)
    frames, tick = [], 1
    while tick <= 400:
        units = []
        for b in s.bodies:
            if b['t0'] <= tick <= b['t1'] and s.rng.random() >= s.miss:
                lab = b['labels'][0] if s.rng.random() >= b['flip'] else s.rng.choice(b['labels'])
                units.append((lab, 1, b['x'], b['y'] + b['vy']*(tick - b['t0']), .9))
        frames.append((tick, units))
        tick += s.rng.choice(s.step)
    return frames


def test_snapshot_restore_is_deterministic(cb):
    frames = _army_frames()
    a, b = tracker(cb), tracker(cb)
    for k, (tick, units) in enumerate(frames):
        snap = b.snapshot()
        b.update(tick, units[:-1] if units else units, {})            # a different update, then thrown away
        b.restore(snap)
        ra, rb = a.update(tick, units, {}), b.update(tick, units, {})
        assert ra == rb and a.last_tracks == b.last_tracks and a.stats == b.stats, tick
    assert [p for p in a.history] == [p for p in b.history]


def fingerprint(t):
    tr = lambda x: (x.id, x.x, x.y, x.last, x.body, tuple(sorted(x.labels.items())), x.resolved, x.state)
    return ([tr(x) for x in t.live], [tr(x) for x in t.dead],
            [(c['t0'], c['card'], sorted(c['members']), sorted(c['votes'].items())) for c in t.clusters],
            [(p['card'], p['t0'], sorted(p['ids'])) for p in t.played], list(t.history), t.n, sorted(t.stats.items()))


def test_resolve_is_read_only_and_matches_update(cb):
    frames = _army_frames()
    t = tracker(cb)
    for tick, units in frames:
        snap = fingerprint(t)
        res = t.resolve(units, tick)
        assert fingerprint(t) == snap
        t.update(tick, units, {})
        assert [None if r is None else r.id for r in res] == \
            [None if r is None or r.id not in {x.id for x in res if x} else i for r, i in zip(res, t.last_tracks)]
    ids = [i for i in t.last_tracks if i is not None]
    idents = [t.identity(i) for i in ids]
    assert {x.card for x in idents if x.card} <= {'SkeletonArmy', 'GoblinGang', 'GoblinHut'}
    assert {x.state for x in idents} <= {'played', 'spawn', 'child', 'leftover', 'pending', 'none'}
    army = [x for x in idents if x.fam == 'SkeletonArmy']
    assert army and all(x.card == 'SkeletonArmy' for x in army)        # Skeletons labels, Army deployment


def test_forget_card_drops_its_tracks_for_good(cb):
    frames = _army_frames()
    t = tracker(cb)
    for tick, units in frames[:90]:
        t.update(tick, units, {})
    assert any(h[2] == 'GoblinGang' for h in t.history)
    n = t.forget_card(1, 'GoblinGang')
    assert n > 0 and not [x for x in t.live + t.dead if x.resolved == 'GoblinGang']
    tick, units = frames[90]
    res = t.resolve(units, tick)
    assert not [r for r in res if r is not None and r.card == 'GoblinGang']
    assert any(p['card'] == 'GoblinGang' for p in t.played) or any(h[2] == 'GoblinGang' for h in t.history)


def test_bodies_of_and_family_of(cb):
    assert cb.family_of('Skeletons') == cb.family_of('SkeletonArmy') == 'SkeletonArmy'
    assert cb.family_of('Knight') == 'Knight'
    hut = cb.bodies_of('GoblinHut')
    assert len(hut) == 2 and {k for _, k in hut} == {0, 1}                # the hut (building) + its spear goblin
    assert cb.bodies_of('GoblinGang') >= {b for b in cb.bodies_of('Goblins')}


def test_body_is_backward_compatible(cb):
    t = tracker(cb)
    t.update(100, [('GoblinHut', 1, 4.5, 26.5, .9)], {})
    t.update(103, [('GoblinHut', 1, 4.5, 26.5, .9)], {})
    body, main = t._body('Goblins', 1, 4.5, 25.4, 106)
    assert main is False and body in cb.children['GoblinHut']             # a spawn beside its hut
    body, main = t._body('Knight', 1, 9., 25., 106)
    assert main is True and body == cb.main['Knight'][0][0]


def test_identity_keeps_the_deployment_card_for_the_track_life(cb):
    # a SkeletonArmy labelled Skeletons, alive 6 s, one body lost for 4 s and revived: identity stays SkeletonArmy
    t = tracker(cb)
    pts = ring(15, 2.2, 9., 26.)
    for tick in range(100, 221, 2):
        y = lambda py: py - .03*(tick - 100)
        units = [('Skeletons', 1, px, y(py), .9) for k, (px, py) in enumerate(pts) if not (k == 0 and 140 <= tick < 220)]
        t.update(tick, units, {})
    revived = t.stats['revived']
    k0 = t.last_tracks[0]
    assert revived >= 1 and t.identity(k0).card == 'SkeletonArmy' and t.identity(k0).state == 'played'
    assert next(x for x in t.live if x.id == k0).deploy == 'SkeletonArmy'
    assert {t.identity(i).card for i in t.last_tracks} == {'SkeletonArmy'}


def test_identity_played_only_for_emitted_plays(cb):
    t = tracker(cb)
    s = clean()
    s.add(('GoblinHut',), [(4.5, 26.5)], 100, vy=0., life=700)
    s.add(('GoblinHut', 'Goblins'), [(4.5, 25.6)], 300, vy=-.05, life=150)       # a spawn walking off
    s.add(('Minions',), ring(3, .8, 12., 26.), 100, life=60)
    s.add(('Minions',), [(12.5, 18.5)], 220, vy=-.04, life=200)                   # a leftover, past revival
    plays = [p[1] for p in s.run(t, 400)]
    assert plays == ['GoblinHut', 'Minions']
    states = {(i.fam, i.state) for i in (t.identity(x.id) for x in t.live + t.dead)}
    spawn = [t.identity(x.id) for x in t.live + t.dead if x.spawn]
    assert spawn and all(i.state == 'spawn' and i.card == 'GoblinHut' for i in spawn)
    left = [t.identity(x.id) for x in t.live + t.dead if x.fam == 'MinionHorde' and x.first >= 220]
    assert left and all(i.state == 'leftover' and i.card == 'Minions' for i in left)


def test_spawn_never_joins_its_spawners_open_cluster(cb):
    # (test_live births case) a hut seen twice, then 3 s later again with its first spear goblin beside it: the hut's
    # cluster closes only now and must stay a GoblinHut (the spawn is not part of its burst)
    t, plays = tracker(cb), []
    for tick, units in ((630, [('GoblinHut', 1, 4.5, 26.5, .9)]), (635, [('GoblinHut', 1, 4.5, 26.5, .9)]),
                        (700, [('GoblinHut', 1, 4.5, 26.5, .9), ('GoblinHut', 1, 4.0, 25.0, .9)]),
                        (705, [('GoblinHut', 1, 4.5, 26.5, .9), ('GoblinHut', 1, 4.0, 24.8, .9)])):
        plays += t.update(tick, units, {})[1]
    assert [(p[1], p[4]) for p in plays] == [('GoblinHut', 630)]


# -- Sol review r2 reproducers (scratch/live-review/multibody-r2/tree/test_review_r2.py), verbatim -------------------
import time as _time_r2
import numpy as np
from bot.live.births import UnitTracker
time = _time_r2


def feed_r2(t, frames):
    plays=[]
    for tick, units in frames:
        plays += t.update(tick, units, {})[1]
    return [p[1] for p in plays]


def test_r2_hint_overrides_open_cross_family_join(cb):
    t=UnitTracker(cb)
    frames=[(k,[('Giant',1,9.,25.,.9),('Musketeer',1,9.5,25.,.9,'Musketeer')]) for k in range(100,151,2)]
    assert sorted(feed_r2(t,frames)) == ['Giant','Musketeer']


def test_r2_hint_overrides_open_same_family_join(cb):
    t=UnitTracker(cb)
    frames=[(k,[('SkeletonArmy',1,9.,25.,.9,'SkeletonArmy'),('Skeletons',1,9.5,25.,.9,'Skeletons')]) for k in range(100,151,2)]
    assert sorted(feed_r2(t,frames)) == ['SkeletonArmy','Skeletons']


def test_r2_promoted_second_hut_remains_a_spawner(cb):
    s=clean()
    s.add(('GoblinHut',),[(4.5,26.5)],100,vy=0.,life=500)
    for k,c in enumerate(('Knight','IceSpirit','Skeletons','Minions')):
        s.add((c,),[(10.+2*k,27.)],200+40*k,life=30)
    s.add(('GoblinHut',),[(7.5,26.5)],400,vy=0.,life=500)
    # Outside the first hut's radius, beside the second hut. It walks away.
    s.add(('Goblins',),[(8.5,25.5)],700,vy=-.05,life=100)
    t=UnitTracker(cb)
    plays=[p[1] for p in s.run(t,1000)]
    assert plays == ['GoblinHut','Knight','IceSpirit','Skeletons','Minions','GoblinHut']


def test_r2_closed_absorption_updates_late_body_capacity(cb):
    s=clean()
    s.add(('SkeletonArmy',),ring(14,2.2,6.,26.),100,vy=0.,life=400)
    # The 15th body really belongs to the Army and is absorbed by the closed cluster.
    s.add(('SkeletonArmy',),[(8.5,26.)],120,vy=0.,life=400)
    # The 16th body is a separately deployed Skeletons card, partially detected.
    s.add(('Skeletons',),[(8.5,24.)],200,vy=0.,life=200)
    t=UnitTracker(cb)
    plays=[p[1] for p in s.run(t,500)]
    assert plays == ['SkeletonArmy','Skeletons']


def test_r2_late_body_yields_after_cycle(cb):
    s=clean()
    s.add(('SkeletonArmy',),ring(12,2.2,6.,26.),100,vy=0.,life=400)
    for k,c in enumerate(('Knight','IceSpirit','Minions','Goblins')):
        s.add((c,),[[(12.,27.),(15.,27.),(12.,30.),(15.,30.)][k]],120+20*k,life=18)
    s.add(('SkeletonArmy',),[(8.5,24.)],220,vy=0.,life=200)
    t=UnitTracker(cb)
    assert [p[1] for p in s.run(t,500)] == ['SkeletonArmy','Knight','IceSpirit','Minions','Goblins','SkeletonArmy']


def test_r2_forget_does_not_restore_card_from_closed_cluster(cb):
    t=UnitTracker(cb)
    assert feed_r2(t,[(k,[('Cannon',1,4.,22.,.9)]) for k in range(100,113,2)]) == ['Cannon']
    old=t.last_tracks[0]
    assert t.forget_card(1,'Cannon') == 1
    t.update(114,[('Cannon',1,4.,22.,.9)],{})
    assert t.identity(old) is None
    assert t.identity(t.last_tracks[0]).card is None  # new birth must vote on its card


def test_r2_forget_removes_votes_of_deleted_pending_members(cb):
    t=UnitTracker(cb)
    t.update(100,[('Skeletons',1,9.,25.,.9),('SkeletonArmy',1,9.5,25.,.9,'SkeletonArmy')],{})
    assert t.forget_card(1,'SkeletonArmy') == 1
    plays=feed_r2(t,[(k,[('Skeletons',1,9.,25.,.9)]) for k in range(102,121,2)])
    assert plays == ['Skeletons']


def test_r2_memory_bound_checked_before_matching(cb):
    t=UnitTracker(cb)
    assert feed_r2(t,[(k,[('Knight',1,4.,22.,.9)]) for k in range(100,113,2)]) == ['Knight']
    t.update(160,[],{})
    assert t.dead
    resolved=t.resolve([('Knight',1,4.,22.,.9)],1000)
    plays=feed_r2(t,[(k,[('Knight',1,4.,22.,.9)]) for k in range(1000,1021,2)])
    assert (resolved,plays) == ([None],['Knight'])


@pytest.mark.parametrize('new_card',['Tesla','BombTower','InfernoTower'])
def test_r2_building_replaced_by_different_card(cb,new_card):
    s=clean(); s.add(('Cannon',),[(4.,22.)],100,vy=0.,life=40)
    s.add((new_card,),[(4.,22.)],300,vy=0.,life=100)
    assert [p[1] for p in s.run(UnitTracker(cb),600)] == ['Cannon',new_card]


@pytest.mark.parametrize('lane',[4.,14.])
@pytest.mark.parametrize('start',[140,180,220])
def test_r2_opposite_lane_smaller_swarm(cb,lane,start):
    s=clean(); s.add(('SkeletonArmy',),ring(15,2.2,lane,26.),100,life=250)
    s.add(('Skeletons',),ring(3,.6,18.-lane,26.),start,life=250)
    assert [p[1] for p in s.run(UnitTracker(cb),700)] == ['SkeletonArmy','Skeletons']


def test_r2_snapshot_after_forget_and_resolve(cb):
    t=UnitTracker(cb)
    feed_r2(t,[(k,[('GoblinHut',1,4.,26.,.9),('Knight',1,12.,26.,.9)]) for k in range(100,115,2)])
    t.forget_card(1,'GoblinHut'); snap=t.snapshot(); before=fingerprint(t)
    units=[('Goblins',1,4.,24.,.9),('Knight',1,12.,25.9,.9)]
    resolved=t.resolve(units,116)
    assert before == fingerprint(t)
    a=t.update(116,units,{}); after=fingerprint(t)
    t.restore(snap)
    assert before == fingerprint(t)
    assert a == t.update(116,units,{}) and after == fingerprint(t)
    assert all(r is None or r.id == tid for r,tid in zip(resolved,t.last_tracks))


def test_r2_empty_unknown_duplicate_backward_ticks(cb):
    t=UnitTracker(cb)
    for k in (100,100,90,110):
        assert t.update(k,[],{}) == ([],[])
    out,plays=t.update(112,[('Unknown',1,4.,22.,.9)],{})
    assert not plays and t.last_tracks == [None]
    # A nonmonotonic frame must not move an established track's last-seen time backwards.
    assert feed_r2(t,[(k,[('Knight',1,4.,22.,.9)]) for k in range(120,133,2)]) == ['Knight']
    # Replaying an older frame sequence must not emit this same deployment twice.
    assert feed_r2(t,[(k,[('Knight',1,4.,22.,.9)]) for k in range(20,51,2)]) == []


def test_r2_40_body_five_minute_cost_and_growth(cb):
    t=UnitTracker(cb); sn=[]; up=[]; re=[]
    for frame in range(3000):
        tick=2*frame+1
        # Forty steady bodies, split owners, dense within each family.
        units=[('SkeletonArmy',owner,3.+(j%5)*.5,20.+(j//5)*.5,.9) for owner in (0,1) for j in range(20)]
        a=time.perf_counter(); snap=t.snapshot(); b=time.perf_counter()
        r=t.resolve(units,tick); c=time.perf_counter()
        t.update(tick,units,{}); d=time.perf_counter()
        sn.append((b-a)*1000); re.append((c-b)*1000); up.append((d-c)*1000)
        assert all(x is None or x.id == tid for x,tid in zip(r,t.last_tracks))
    print('PERF p50/p95 ms:',{k:np.percentile(v,[50,95]).tolist() for k,v in [('snapshot',sn),('resolve',re),('update',up)]})
    print('GROWTH live/dead/clusters/played/history/n:',len(t.live),len(t.dead),len(t.clusters),len(t.played),len(t.history),t.n)
    assert len(t.live)==40 and len(t.dead)==0 and t.n==40


def test_r2_spawn_wait_does_not_absorb_a_later_deployment(cb):
    s=clean()
    s.add(('GoblinHut',),[(4.5,26.5)],100,vy=0.,life=900)
    for k,c in enumerate(('Knight','IceSpirit','Skeletons','Minions')):
        s.add((c,),[(10.+2*k,27.)],200+40*k,life=30)
    s.add(('GoblinHut',),[(7.5,26.5)],400,vy=0.,life=500)
    s.add(('Goblins',),ring(4,.6,8.5,24.5),430,life=200)
    t=UnitTracker(cb)
    assert [p[1] for p in s.run(t,800)] == ['GoblinHut','Knight','IceSpirit','Skeletons','Minions','GoblinHut','Goblins']


def test_r2_public_state_for_duplicate_is_not_played(cb):
    t=UnitTracker(cb)
    frames=[]
    for k in range(100,130,2):
        units=[('Knight',1,9.,26.,.9)]
        if 112 <= k: units.append(('Valkyrie',1,9.2,26.1,.9))
        frames.append((k,units))
    assert feed_r2(t,frames) == ['Knight']
    # This second detector box was suppressed as a duplicate, not an emitted deployment.
    assert t.identity(t.last_tracks[1]).state != 'played'


def test_r2_known_spell_without_body_is_ignored(cb):
    t=UnitTracker(cb)
    for k in range(100,150,2):
        assert t.update(k,[('Fireball',1,9.,26.,.9)],{})[1] == []
        assert t.last_tracks == [None]


def test_r2_nan_coordinates_do_not_poison_valid_frames(cb):
    t=UnitTracker(cb)
    for k in range(100,150,2):
        t.update(k,[('Knight',1,float('nan'),26.,.9),('Unknown',1,9.,float('nan'),.9)],{})
    assert feed_r2(t,[(k,[('Knight',1,4.,22.,.9)]) for k in range(150,175,2)]) == ['Knight']


def test_r2_live_golem_does_not_hide_a_cycled_second_golem(cb):
    s=clean()
    s.add(('Golem',),[(4.,26.)],100,vy=0.,life=800)
    for k,c in enumerate(('Knight','IceSpirit','Skeletons','Goblins')):
        s.add((c,),[(12.,26.)],220+100*k,life=40)
    s.add(('Golem',),[(5.5,26.)],700,vy=-.03,life=100)
    t=UnitTracker(cb)
    assert [p[1] for p in s.run(t,1000)] == ['Golem','Knight','IceSpirit','Skeletons','Goblins','Golem']


@pytest.mark.parametrize('old_n,new_pts',[(14,[(8.5,26.)]),(12,[(8.5,26.),(8.8,26.),(8.5,25.7)])])
def test_r2_late_capacity_full_followup_burst(cb,old_n,new_pts):
    s=clean()
    s.add(('SkeletonArmy',),ring(old_n,2.2,6.,26.),100,vy=0.,life=400)
    s.add(('SkeletonArmy',),new_pts,120,vy=0.,life=400)
    s.add(('Skeletons',),ring(15-old_n,.3,8.5,24.),200,vy=0.,life=200)
    t=UnitTracker(cb)
    assert [p[1] for p in s.run(t,500)] == ['SkeletonArmy','Skeletons']


@pytest.mark.parametrize('card',['Tombstone','BarbarianHut','GoblinCage','GoblinBrawler'])
def test_r2_requested_oov_spawners_are_not_in_frozen_runtime(cb,card):
    assert not cb.is_card(card)
    t=UnitTracker(cb)
    assert feed_r2(t,[(k,[(card,1,4.,26.,.9)]) for k in range(100,150,2)]) == []
    assert t.last_tracks == [None]


def test_r2_five_minute_churn_is_bounded(cb):
    t=UnitTracker(cb)
    cards=['Knight','Musketeer','Valkyrie','Giant','IceSpirit','Firecracker','HogRider','Prince']
    maximum=0
    for frame in range(3000):
        tick=2*frame+1
        # Four short deployments per 10 s, old deployments vanish; forty visible bodies.
        card=cards[(frame//50)%len(cards)]
        units=[(card,owner,2.+10*((frame//50)%2)+(j%5)*.6,20.+(j//5)*.6,.9) for owner in (0,1) for j in range(20)]
        t.update(tick,units,{})
        maximum=max(maximum,len(t.live)+len(t.dead))
    print('CHURN peak tracks/final live/dead/clusters/played/history/n:',maximum,len(t.live),len(t.dead),len(t.clusters),len(t.played),len(t.history),t.n)
    assert maximum <= 200 and len(t.clusters) <= 40 and len(t.played) <= 8


def test_forget_takes_the_forgotten_labels_votes_along(cb):
    # one pending cluster read as SkeletonArmy (confident) and Skeletons (weak); SkeletonArmy is forgotten (e.g. an
    # eviction): the remaining bodies must decide on their own votes
    t, plays = UnitTracker(cb), []
    for k in range(100, 108, 2):
        plays += t.update(k, [('SkeletonArmy', 1, 9.5, 25., .95), ('Skeletons', 1, 9., 25., .6)], {})[1]
    assert t.forget_card(1, 'SkeletonArmy') == 1
    for k in range(108, 130, 2):
        plays += t.update(k, [('Skeletons', 1, 9., 25., .6)], {})[1]
    assert [p[1] for p in plays] == ['Skeletons']


# -- fuzzer-found (bot/live/multibody_fuzz.py, minimized) ----------------------------------------------------------------
@pytest.mark.parametrize('champion', ['ArcherQueen', 'Goblinstein', 'MightyMiner'])
def test_fuzz_champion_redeployed_after_a_cycle(cb, champion):
    from bot.live.multibody_fuzz import check
    deployments = [(1, champion, 100, 14., 27., 290), (1, 'Knight', 140, 4., 27., 220),
                   (1, 'Archers', 180, 9., 27., 260), (1, 'MiniPekka', 220, 14., 28., 300),
                   (1, 'Cannon', 260, 9., 22., 860), (1, champion, 300, 4., 27., 460)]
    frames = [(t, [(card, owner, bx, by - (0 if card == 'Cannon' else .04)*(t - born), .95)
                   for owner, card, born, x, y, dies in deployments if born <= t < dies
                   for bx, by in ring(cb.count[card], .5, x, y)]) for t in range(100, 381, 2)]
    result = check({'frames': frames, 'truth': [d[:5] for d in deployments]}, cb)
    assert not result['violations'] and result['ok'], result['description']


def test_fuzz_spawn_cluster_never_takes_a_deployment(cb):
    # a FirespiritHut's fresh spirit opens a (spawn) cluster; a second hut deployed 2.7 tiles away 9 ticks later is
    # its own play, not the spirit's "burst"
    s = clean()
    s.add(('FirespiritHut',), [(12.9, 22.6)], 100, vy=0., life=900)
    for k, c in enumerate(('Knight', 'IceSpirit', 'Skeletons', 'Minions')):
        s.add((c,), [(3. + 2*k, 27.)], 200 + 40*k, life=30)
    s.add(('FirespiritHut',), [(12.4, 23.3)], 592, vy=-.05, life=60)        # its spawn, labelled as the hut
    s.add(('FirespiritHut',), [(13.6, 25.6)], 601, vy=0., life=300)        # the second hut
    plays = s.run(tracker(cb), 900)
    assert [p[1] for p in plays] == ['FirespiritHut', 'Knight', 'IceSpirit', 'Skeletons', 'Minions', 'FirespiritHut']
    hut = plays[-1]                                                         # at its own place and time, not the spawn's
    assert hut[4] >= 601 and math.hypot(hut[2] - 13.6, hut[3] - 25.6) < .5, hut


def test_waiting_spawn_takes_no_further_spawns(cb):
    # the hut could have cycled (4 plays), so a still spawn waits for movement; the hut's next spawn 1 s later must
    # not join that waiting cluster (two bodies would look like a deployment)
    s = clean()
    s.add(('GoblinHut',), [(4.5, 26.5)], 100, vy=0., life=900)
    for k, c in enumerate(('Knight', 'IceSpirit', 'Skeletons', 'Minions')):
        s.add((c,), [(10. + 2*k, 27.)], 200 + 40*k, life=30)
    s.add(('GoblinHut',), [(4.5, 25.6)], 400, vy=0., life=30)              # a spawn standing through deploy time
    s.add(('GoblinHut',), [(4.9, 25.6)], 420, vy=-.05, life=100)           # the next spawn, walking off
    s.add(('GoblinHut',), [(4.5, 25.6)], 430, vy=-.05, life=100)           # the first one leaves
    assert exact(cb, s, 800) == ['GoblinHut', 'Knight', 'IceSpirit', 'Skeletons', 'Minions']
