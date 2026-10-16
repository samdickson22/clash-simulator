"""Deterministic offline audit tests; no live player or policy inference."""
import hashlib
import json
import sys

import pytest

from bot.live import audit_plays as audit


@pytest.fixture(scope='module')
def rt():
    from bot.players.runtime import Runtime
    return Runtime()


@pytest.fixture
def run(tmp_path):
    directory = tmp_path / 's99-m01'
    directory.mkdir()
    deck = ['Knight', 'Archers', 'Minions', 'Arrows', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer']
    cfg = dict(deck=deck, translator=dict(cls='bot.live.translate.LiveTranslator',
               unknown_card='drop', plays_from='births'),
               session=dict(cls='bot.live.translate.LiveSession', seed=0, command_delay=27, expire=90))
    (directory / 'session-config.json').write_text(json.dumps(cfg))
    rows = []
    for tick in (90, 95, 100, 110, 120, 140, 160, 180):
        rows.append(dict(n=tick, tick=99999, ts_ms=1000 + tick * 50,
                         timestamp_ms=1000 + tick * 50, clock_s=180 - tick / 20, phase=1,
                         hand=dict(cards=deck[:4], next=deck[4]), elixir=10., towers=[],
                         units=[dict(cls='Knight', owner=1, x=4., y=25., score=1.)],
                         events=[dict(owner=1, card='Fireball', tick=tick, x=9., y=5.)]))
    (directory / 'perception.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    (directory / 'events.jsonl').write_text(json.dumps(dict(ev='match_start', ts_ms=1000, n=89)) + '\n')
    (directory / 'decisions.jsonl').write_text('')
    return directory


def marker(tmp_path, card):
    """Use real cards/clock, but replace tracker output with one marker deployment."""
    path = tmp_path / f'births_{card}.py'
    path.write_text(audit.DEFAULT_BIRTHS.read_text() + f'''
_OriginalTracker = UnitTracker
class UnitTracker(_OriginalTracker):
    def update(self, tick, units, tower_alive, unknown=()):
        self.stats['marker_tracker_used'] += 1
        return ([(None, (0., 0.)) for u in units],
                [(1, {card!r}, 3.25, 25.5, tick)] if tick == 100 else [])
''')
    return path


def replay(run, rt, paths=None, decks=None):
    return audit.audit([run.name], paths, runs_root=run.parent, rt=rt,
                       decks={'s99m01': dict(opp_deck=['Knight'])} if decks is None else decks)


def test_real_translator_filters_temporal_events_and_uses_session_clock(run, rt):
    report = replay(run, rt)
    result = report['runs'][0]['battles'][0]['trackers'][0]
    assert result['errors'] == []
    assert result['per_card'] == {'Knight': 1}  # Fireball temporal events are ignored in births mode
    assert len(result['derived_plays']) == 1
    assert result['plays'][0]['tick'] < 180  # metadata tick=99999 never reaches translator
    assert result['plays'][0]['off_deck'] is False
    assert result['off_deck_c56'] == 0
    assert result['translator_stats']['catchup_polls'] > 0


def test_births_override_off_deck_and_module_restoration(run, rt, tmp_path):
    from bot.live import births
    path = marker(tmp_path, 'Giant')
    report = replay(run, rt, [path])
    result = report['runs'][0]['battles'][0]['trackers'][0]
    assert result['errors'] == []
    assert result['per_card'] == {'Giant': 1}
    assert result['plays'][0] == dict(tick=100, seconds=5., card='Giant', public_card='Giant',
                                     x=3.25, y=25.5, off_deck=True, c56=True)
    assert result['off_deck'] == result['off_deck_c56'] == 1
    assert result['tracker_stats']['marker_tracker_used'] > 0
    assert report['trackers'][0]['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert sys.modules['bot.live.births'] is births


def test_two_births_cli_comparison(run, rt, tmp_path, monkeypatch, capsys):
    knight, giant = marker(tmp_path, 'Knight'), marker(tmp_path, 'Giant')
    # main calls audit without rt; wrap it to reuse our module-scoped resources.
    real_audit = audit.audit
    monkeypatch.setattr(audit, 'audit', lambda *a, **kw: real_audit(*a, **kw, rt=rt))
    monkeypatch.setattr(audit, 'load_decks', lambda: {'s99m01': dict(opp_deck=['Knight'])})
    output = tmp_path / 'out.json'
    assert audit.main([run.name, '--births', str(knight), '--births', str(giant),
                       '--runs-root', str(run.parent), '--json', str(output)]) == 0
    report = json.loads(output.read_text())
    comparison = report['runs'][0]['battles'][0]['comparison']
    assert [(r['total_plays'], r['off_deck'], r['off_deck_c56']) for r in comparison] == [(1, 0, 0), (1, 1, 1)]
    assert [[p['card'] for p in r['only_here']] for r in comparison] == [['Knight'], ['Giant']]
    text = capsys.readouterr().out
    assert 'b0: plays=1 off-deck=0' in text and 'b1: plays=1 off-deck=1' in text
    assert 'Only b0:' in text and 'Only b1:' in text


def test_identical_trackers_have_no_exclusive_plays(run, rt):
    report = replay(run, rt, [audit.DEFAULT_BIRTHS, audit.DEFAULT_BIRTHS])
    assert all(r['only_here'] == [] for r in report['runs'][0]['battles'][0]['comparison'])


def test_missing_deck_is_unknown(run, rt):
    report = replay(run, rt, decks={})
    result = report['runs'][0]['battles'][0]['trackers'][0]
    assert result['total_plays'] == 1
    assert result['off_deck'] is None and result['off_deck_c56'] is None
    assert result['plays'][0]['off_deck'] is None


def test_match_boundaries_reset_session_and_pauses_skip_records(run, rt):
    path = run / 'perception.jsonl'
    original = audit.jsonl(path)
    second = [dict(r, timestamp_ms=r['timestamp_ms'] + 20000, ts_ms=r['ts_ms'] + 20000,
                   n=r['n'] + 1000) for r in original]
    path.write_text(''.join(json.dumps(r) + '\n' for r in original + second))
    events = [dict(ev='match_start', ts_ms=1000), dict(ev='match_end', ts_ms=11000),
              dict(ev='match_start', ts_ms=21000), dict(ev='paused_by_user', ts_ms=21001),
              dict(ev='resumed_by_user', ts_ms=27000)]
    (run / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    report = replay(run, rt)
    first, second = [b['trackers'][0] for b in report['runs'][0]['battles']]
    assert first['errors'] == second['errors'] == []
    assert first['total_plays'] == second['total_plays'] == 1
    assert second['paused_records'] == 4
    assert second['effective_replay_config']['clock_anchor_ms'] == 21000


@pytest.mark.parametrize('fields', [4, 5])
def test_legacy_adapter_and_refuse_standin(run, rt, tmp_path, fields):
    source = audit.DEFAULT_BIRTHS.read_text() + '''
_OriginalCards, _OriginalTracker = CardBodies, UnitTracker
class CardBodies(_OriginalCards):
    def __init__(self, rt):
        super().__init__(rt)
        del self.oov
class UnitTracker(_OriginalTracker):
    def update(self, tick, units, tower_alive):
        assert all(len(u) == 5 for u in units)
        self.stats['legacy_used'] += 1
        return super().update(tick, units, tower_alive)
class ClockTracker:
    def __init__(self):
        self.anchor = None  # original LIVE glue had no callable anchor
'''
    if fields == 4:
        source = source.replace('assert all(len(u) == 5 for u in units)',
                                'for card, owner, x, y in units:\n            pass')
    path = tmp_path / 'legacy.py'
    path.write_text(source)
    report = replay(run, rt, [path])
    result = report['runs'][0]['battles'][0]['trackers'][0]
    assert result['errors'] == [] and result['total_plays'] == 1
    assert result['tracker_stats']['legacy_used'] > 0
    assert report['trackers'][0]['adapter'] == f'{audit.LEGACY}; unit_fields={fields}'
    cfg_path = run / 'session-config.json'
    cfg = json.loads(cfg_path.read_text())
    cfg['translator']['unknown_card'] = 'standin'
    cfg_path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='C56/drop only'):
        replay(run, rt, [path])


def test_comparison_is_a_multiset():
    p = dict(card='Knight', tick=100, x=3., y=25.)
    results = [dict(tracker='a', plays=[p, p], total_plays=2, off_deck=0, off_deck_c56=0),
               dict(tracker='b', plays=[p], total_plays=1, off_deck=0, off_deck_c56=0)]
    assert [r['only_here'] for r in audit.compare(results)] == [[p], []]
