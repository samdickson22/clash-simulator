from types import SimpleNamespace

import numpy as np
import pytest

from bot.eval.reaction import ReactionRecorder, game_metrics
from bot.eval.summarize import reaction_summary
from bot.players.base import Decision, WAIT


@pytest.mark.parametrize('seat', [0, 1])
def test_latency_uses_accepted_plays_and_next_searched_decision_including_wait(seat):
    result = dict(play_log={seat: [], 1-seat: [
        (100, 'Giant', 0, True), (110, 'Giant', 0, False),
        (120, 'Archers', 0, True), (160, 'Giant', 0, True)]})
    dec = [dict(tick=100, stats=None, submitted=False),
           dict(tick=120, stats={'source': 'search'}, action=WAIT, submitted=False)]
    m = game_metrics(seat, result, [], dec)
    assert m == dict(reaction_p50_s=1., reaction_p90_s=1., enemy_plays=3,
                     reaction_events=2, giant_pushes=0, undefended_giant_pushes=0, undefended_share=0.)


def test_no_matched_search_is_null_but_enemy_count_includes_tail():
    m = game_metrics(0, dict(play_log={'0': [], '1': [(100, 'Giant', 0, True)]}), [], [])
    assert m['reaction_p50_s'] is None and m['reaction_p90_s'] is None
    assert m['reaction_events'] == 0 and m['enemy_plays'] == 1


def scene(defence_tick=None, defence_x=3, contact=True):
    perc = [dict(n=i, tick=100+i*5, units=[dict(owner=1, cls='Giant', x=3.5,
                 y=(14, 13, 12, 11, 10 if contact else 11)[i])], hand={}, elixir=6)
            for i in range(5)]
    dec = [] if defence_tick is None else [dict(n=0, tick=defence_tick,
           action=5*18+defence_x, submitted=True, stats={'source': 'search'}, card='Cannon')]
    return game_metrics(0, dict(play_log={0: [], 1: []}), perc, dec)


@pytest.mark.parametrize('tick,x,undefended', [(None, 3, 1), (115, 3, 0), (120, 3, 1), (115, 14, 1)])
def test_existing_giant_definition_requires_same_lane_defence_strictly_before_contact(tick, x, undefended):
    m = scene(tick, x)
    assert m['giant_pushes'] == 1
    assert m['undefended_giant_pushes'] == undefended
    assert m['undefended_share'] == undefended


def test_push_without_contact_stays_in_denominator():
    m = scene(contact=False)
    assert m['giant_pushes'] == 1 and m['undefended_share'] == 0


def test_recorder_preserves_decision_and_filters_other_seat():
    features = np.zeros((1, 6))
    features[0] = [.2, .4, 0, 0, 1, 0]
    obs = SimpleNamespace(entity_mask=np.array([True]), entity_features=features,
                          entity_ids=np.array([1]), hand_ids=np.array([1]*4),
                          global_features=np.array([0, 0, 0, 0, 0, .6]))
    builder = SimpleNamespace(token_names=['Tower', 'Giant'], card_name_for_token_id=lambda _: 'Giant')
    rt = SimpleNamespace(R=SimpleNamespace(builder=builder))
    d = Decision(WAIT, wait_ticks=20, stats={'source': 'search', 'completed': 4})
    player = SimpleNamespace(name='test', deadline_seconds=None, act=lambda _: d)
    rec = ReactionRecorder(rt, player, 1)
    view = SimpleNamespace(seat=0, tick=110, can_act=True, info=SimpleNamespace(packet=SimpleNamespace(observation=obs)))
    rec(view, d)
    assert not rec.perc
    view.seat = 1
    assert rec.act(view) is d
    assert rec.dec[0]['stats'] == d.stats and rec.dec[0]['submitted'] is False
    assert rec.perc[0]['units'][0]['cls'] == 'Giant'
    assert d.wait_ticks == 20


def test_summary_reports_game_median_coverage_and_stratified_bootstrap():
    # A single observation per opponent stays fixed in every within-opponent draw.
    rows = [dict(opponent='R3a', reaction_p50_s=1, enemy_plays=10, undefended_share=0),
            dict(opponent='strong', reaction_p50_s=3, enemy_plays=20, undefended_share=1),
            dict(opponent='old'), dict(opponent='tail', reaction_p50_s=None),
            dict(opponent='error', error='failed', reaction_p50_s=999)]
    out = reaction_summary(rows)
    assert out['reaction_p50_s'] == dict(n=2, missing=2, median=2, ci=(2, 2))
    assert out['enemy_plays']['median'] == 15
    assert out['undefended_share']['median'] == .5
    assert out['reaction_p90_s'] == dict(n=0, missing=4, median=None, ci=None)
    assert reaction_summary(rows) == out


def test_summary_bootstraps_medians_with_nonzero_uncertainty():
    rows = [dict(opponent='R3a', reaction_p50_s=x) for x in (1, 2, 9)]
    assert reaction_summary(rows)['reaction_p50_s'] == dict(n=3, missing=0, median=2, ci=(1, 9))
