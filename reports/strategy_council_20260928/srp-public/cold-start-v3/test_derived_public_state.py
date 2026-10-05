"""Unit checks for exact public deductions; no engine access in the module."""
import json
import numpy as np
from derived_public_state import DerivedPublicState
from support import TRAIN_DECKS


def fixture():
    prior=json.loads(TRAIN_DECKS.read_text())
    # Cost values do not affect the pure cycle checks below.
    costs={name:1 for name in prior['cards']}
    prior['decks']=prior['decks'][:1]
    return prior,costs


def test_elixir_exact_integer_frames_and_clamp():
    prior,costs=fixture(); b=DerivedPublicState(prior,costs)
    b.update(10,())
    assert b.elixir_units==60000+10*178
    b.update(2400,()); assert b.elixir_units==100000
    card=prior['decks'][0]['cards'][0]
    b.update(2400,((2400,card),)); assert b.elixir_units==90000
    b.update(2401,((2400,card),)); assert b.elixir_units==90357


def test_hand_and_cycle_resolve_before_all_cards_seen_when_deck_is_known():
    prior,costs=fixture(); b=DerivedPublicState(prior,costs)
    assert b.derived()['hand'] is None
    deck=prior['decks'][0]['cards']
    history=[]
    for i,card in enumerate(deck[:4]):
        history.append((i*30,card))
        b.update(i*30+25,tuple(history))
    derived=b.derived()
    assert set(derived['hand'])==set(deck[4:])
    assert derived['cycle']==tuple(deck[:4])
    assert derived['next_card']==deck[0]
    # Fully determined semantic state does not sample hidden identities/cycle.
    class NoRandom:
        def random(self): raise AssertionError('sampled an already derived state')
    sampled=b.sample(NoRandom())
    assert set(sampled['hand'])==set(deck[4:])
    assert sampled['cycle']==deck[:4]


def test_all_eight_seen_resolves_and_preserves_repeated_play_order():
    prior,costs=fixture(); b=DerivedPublicState(prior,costs)
    deck=prior['decks'][0]['cards']; history=[]
    for i,card in enumerate(deck+deck[:3]):
        history.append((i*30,card)); b.update(i*30+25,tuple(history))
        if i>=7:
            d=b.derived()
            assert d['cycle']==tuple(x[1] for x in history[-4:])
            assert set(d['hand'])==set(deck)-set(d['cycle'])


def test_sample_fixes_each_derivable_position():
    prior,costs=fixture(); b=DerivedPublicState(prior,costs)
    card=prior['decks'][0]['cards'][0]
    b.update(25,((0,card),))
    d=b.derived()
    assert d['cycle_positions_known'][-1]
    for seed in range(10):
        s=b.sample(np.random.default_rng(seed))
        assert s['cycle'][-1]==card
        assert card not in s['hand']


def test_impossible_history_fails_closed():
    import pytest
    prior,costs=fixture(); b=DerivedPublicState(prior,costs)
    card=prior['decks'][0]['cards'][0]
    with pytest.raises(ValueError,match='no deck/order'):
        b.update(5,((0,card),(5,card)))


def test_unrevealed_identity_samples_respect_conditioned_deck_prior():
    prior=json.loads(TRAIN_DECKS.read_text())
    b=DerivedPublicState(prior,{name:1 for name in prior['cards']})
    b.update(25,((0,'Giant'),))
    allowed={frozenset(d['cards']) for d in prior['decks'] if 'Giant' in d['cards']}
    seen=set()
    for seed in range(40):
        state=b.sample(np.random.default_rng(seed))
        deck=frozenset(state['hand']+state['cycle'])
        assert deck in allowed
        assert state['cycle'][-1]=='Giant' and 'Giant' not in state['hand']
        seen.add(deck)
    assert len(seen)>1
