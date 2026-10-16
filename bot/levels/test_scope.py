"""The scope is fixed before outcomes and identical for every experimental arm."""
import copy
from types import SimpleNamespace

import pytest

from .scope import digest, install, restricted


def test_restriction_preserves_order_weights_original_and_rejects_mutation(monkeypatch):
    monkeypatch.delenv('BOT_BELIEF_PRIOR', raising=False)
    prior = {'schema': 'test', 'decks': [
        {'cards': ['Knight', 'Archers'], 'frequency': 3},
        {'cards': ['Knight', 'Earthquake'], 'frequency': 5},
        {'cards': ['Tornado', 'Earthquake'], 'frequency': 2},
        {'cards': ['Archers', 'Knight'], 'frequency': 1}]}
    before = copy.deepcopy(prior)
    rt = SimpleNamespace(PRIOR=prior)
    receipt = install(rt)
    assert prior == before and rt.levels_original_prior == before
    assert rt.PRIOR['decks'] == [before['decks'][0], before['decks'][3]]
    assert receipt['omitted_decks'] == 2
    assert receipt['omitted_frequency'] == 7
    assert receipt['omitted_mass'] == pytest.approx(7 / 11)
    assert receipt['restricted_sha256'] == digest(rt.PRIOR)
    assert install(rt) == receipt
    rt.PRIOR['decks'][0]['frequency'] = 100
    assert rt.levels_original_prior == before
    with pytest.raises(ValueError, match='changed'):
        install(rt)


def test_restriction_cannot_empty_prior_or_ignore_external_override(monkeypatch):
    with pytest.raises(ValueError, match='nonempty'):
        restricted({'decks': [{'cards': ['Clone'], 'frequency': 1}]})
    monkeypatch.setenv('BOT_BELIEF_PRIOR', 'fullpool:1')
    with pytest.raises(ValueError, match='override'):
        install(SimpleNamespace(PRIOR={'decks': [{'cards': ['Knight'], 'frequency': 1}]}))
