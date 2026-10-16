"""A fixed population snapshot must survive later live-log updates."""
import json
from types import SimpleNamespace

from . import bank, profile


def test_explicit_population_snapshot_is_immutable_input(tmp_path, monkeypatch):
    deck = list(profile.LIVE_DECK)
    rt = SimpleNamespace(PRIOR={'decks': [{'cards': deck, 'frequency': 1}]},
                         R=SimpleNamespace(builder=SimpleNamespace(loader=SimpleNamespace(
                             get_card=lambda _: SimpleNamespace(rarity='common')))))
    row = dict(run='frozen', opp_trophies=750, opp_deck=deck)
    snapshot = tmp_path / 'snapshot.jsonl'
    snapshot.write_text(json.dumps(row) + '\n')
    live = tmp_path / 'reports/live/loop/opponent-decks.jsonl'
    live.parent.mkdir(parents=True)
    live.write_text(json.dumps(dict(row, run='new-live-row')) + '\n')
    monkeypatch.setattr(bank, 'REPO', tmp_path)
    path = tmp_path / 'cases.json'
    first = bank.build(rt, 1, 4, path, source=snapshot)
    live.write_text(json.dumps(dict(row, run='later-live-row')) + '\n')
    assert bank.build(rt, 1, 4, path, source=snapshot) == first
    assert first['source'] == 'snapshot.jsonl'
    assert {c['row_id'] for c in first['cases']} == {'frozen'}
