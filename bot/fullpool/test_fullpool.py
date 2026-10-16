"""Unit tests (no runtime needed): python -m pytest -q bot/fullpool/test_fullpool.py"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from bot.fullpool import banks, belief, cards, decks
from bot.fullpool.cards import C56, CHAMPIONS, NEW, POOL

SCOPE = Path('/mpac/sdicks02/repos/clasher-cards/bot/cards/scope.py')
REPO = Path(__file__).resolve().parents[2]


def test_pool_matches_scope():
    path = REPO / 'bot/cards/scope.py' if (REPO / 'bot/cards/scope.py').exists() else SCOPE
    if not path.exists():
        pytest.skip('bot/cards/scope.py not available')
    spec = importlib.util.spec_from_file_location('scope', path)
    s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
    assert tuple(c for c in s.EXTRA_CARDS if c not in s.EXCLUDED) == NEW
    assert set(cards.EXCLUDED) == set(s.EXCLUDED)


def test_names():
    assert cards.engine_name('Mini P.E.K.K.A') == 'MiniPekka'
    assert cards.engine_name('Bandit') == 'Assassin' and cards.vocab_name('Assassin') == 'Bandit'
    assert cards.engine_name('DartGoblin') == 'BlowdartGoblin'
    assert cards.engine_name('Archer') == 'Archers'
    assert all(cards.proxy_card(c) in C56 for c in NEW)
    freq = json.loads((REPO / 'reports/live/loop/arena-card-freq.json').read_text())
    assert all(cards.engine_name(n) in POOL for a in freq['arenas'].values() for n in a['cards'])


def test_sampler_valid_deterministic():
    s = decks.Sampler.from_spec('fullpool:5')
    assert abs(sum(s.w.values()) - 1) < 1e-9 and min(s.w.values()) > 0
    ds = [s.deck(i) for i in range(300)]
    assert ds == [decks.Sampler.from_spec('fullpool:5').deck(i) for i in range(300)]
    assert all(decks.is_valid(d) for d in ds)
    assert decks.Sampler.from_spec('fullpool:6').deck(0) != ds[0] or decks.Sampler.from_spec('fullpool:6').deck(1) != ds[1]
    assert any(c in CHAMPIONS for d in ds for c in d)
    assert all(set(s.deck(i, c56_only=True)) <= set(C56) for i in range(50))
    assert all({'Pekka', 'Bomber'} <= set(s.deck(i, require=['Pekka', 'Bomber'])) for i in range(50))
    u = decks.Sampler.from_spec('fullpool-uniform:5')
    assert all(decks.is_valid(u.deck(i)) for i in range(50))


def test_sampler_weights_follow_observed():
    w, prov = decks.weights(freq='36bfa0cfc991')
    assert prov['observed_arenas'] == {'bone-pit': 2, 'goblin-stadium': 1}
    w2, prov2 = decks.weights()
    assert prov2['freq']['sha256'] == decks.FREQ[1] and abs(sum(w2.values()) - 1) < 1e-9
    assert w['GoblinCage'] > 10 * w['MegaKnight']          # observed vs floor-only
    assert w['BattleRam'] > w['MegaKnight']                  # next-arena unlock vs floor-only


def test_frozen_tables_match_names():
    for p in decks.FROZEN.glob('arena-card-freq-*.json'):
        assert decks.hashlib.sha256(p.read_bytes()).hexdigest().startswith(p.stem.rsplit('-', 1)[1])
        s = decks.Sampler.from_spec(f"fullpool:1:freq={p.stem.rsplit('-', 1)[1]}")
        assert decks.is_valid(s.deck(0))
    for b in banks.BANKS.values():
        if b['decks'].startswith('fullpool'):   # sampler banks pin a frozen freq table (x4s / e16bl are fixed lists)
            assert 'freq=' in b['decks'] and banks.sampler(banks.parse(b['decks'])[0])


def test_sampler_pin(monkeypatch, tmp_path):
    bad = tmp_path / 'f.json'
    bad.write_text('{}')
    monkeypatch.setenv('BOT_FULLPOOL_FREQ', f'{bad}@{"0" * 64}')
    with pytest.raises(ValueError, match='sha256'):
        decks.weights()


class FakeRT:
    R = type('R', (), dict(costs=dict.fromkeys(POOL, 3.)))()

    def x4s_decks(self):
        return [sorted(C56)[i * 8:(i + 1) * 8] for i in range(5)]


def test_cases():
    rt = FakeRT()
    from bot.players.ours import x4s_setup
    assert banks.case(rt, 7, 123) == x4s_setup(rt, 7, 123)
    c = banks.case(rt, 7, 123, 'fullpool:3')
    assert c == banks.case(rt, 7, 123, 'fullpool:3') and c['seat'] == 1 and c['seed'] == 130
    assert all(decks.is_valid(d) for d in c['decks'])
    o = banks.case(rt, 7, 123, 'fullpool:3:own=c56')
    assert set(o['decks'][o['seat']]) <= set(C56)
    assert sorted(o['decks'][1 - o['seat']]) == sorted(c['decks'][1 - c['seat']])
    banks.check_scope(rt, 'fullpool:3', 20)
    rt2 = FakeRT(); rt2.R = type('R', (), dict(costs=dict.fromkeys(C56, 3.)))()
    with pytest.raises(ValueError, match='outside this runtime'):
        banks.check_scope(rt2, 'fullpool:3', 20)


def test_banks_disjoint():
    from bot.exit.generate import check_bank
    spans = sorted((b['base'], b['games']) for b in banks.BANKS.values() if b['decks'] != 'x4s')
    others = [(1455777415631152, 10**5), (874184153281168, 10**8), (1462854985943728, 10**8), (4503604807370496, 10**5)]
    for (b1, n1) in spans + others:
        for (b2, n2) in spans + others:
            if (b1, n1) != (b2, n2) and b1 != b2:
                assert b1 + max(n1, 10**8) < b2 or b2 + max(n2, 10**8) < b1
    with pytest.raises(ValueError):
        check_bank(banks.BANKS['FP-FRESH1']['base'], 0, 10)
    check_bank(banks.BANKS['FP-TRAIN1']['base'], 0, 10**6)


def test_belief_prior():
    s = decks.Sampler.from_spec('fullpool:5')
    p = belief.prior_decks(s, 50)
    assert p == belief.prior_decks(s, 50) and sum(d['frequency'] for d in p['decks']) == 50
    q = belief.prior_decks(s, 50, require=['Tombstone', 'Knight'])
    assert all({'Tombstone', 'Knight'} <= set(d['cards']) for d in q['decks'])


def test_lopp_extend_append_only(tmp_path):
    from bot.fullpool.extend import extend_lopp
    from bot.search.lopp_feat import NumpyOpponent, DIM
    rng = np.random.default_rng(0)
    meta = {c: dict(token=10 + i, cost=float(i % 9 + 1)) for i, c in enumerate(sorted(C56) + sorted(NEW))}
    vocab = [0] + sorted(meta[c]['token'] for c in C56)
    H, E = 32, 4
    z = dict(emb=rng.normal(size=(57, E)).astype(np.float32), W1=rng.normal(size=(DIM, H)).astype(np.float32),
             b1=np.zeros(H, np.float32), W1c=rng.normal(size=(4 * E, H)).astype(np.float32),
             W2=rng.normal(size=(H, H)).astype(np.float32), b2=np.zeros(H, np.float32),
             wg=rng.normal(size=(H, 1)).astype(np.float32), bg=np.zeros(1, np.float32),
             Wv=rng.normal(size=(H, 57)).astype(np.float32), bv=rng.normal(size=57).astype(np.float32),
             Wt=rng.normal(size=(H, H)).astype(np.float32), bt=np.zeros(H, np.float32),
             tem=rng.normal(size=(57, H)).astype(np.float32), Wo=rng.normal(size=(H, 576)).astype(np.float32),
             bo=np.zeros(576, np.float32), meta_vocab=np.array(vocab, np.int64),
             meta_cost=np.array([0.] + [meta[c]['cost'] for c in sorted(C56, key=lambda c: meta[c]['token'])]),
             meta_tau=np.array(.2), meta_mu=np.zeros(DIM, np.float32), meta_sd=np.ones(DIM, np.float32))
    np.savez(tmp_path / 'm.npz', **z)
    r = extend_lopp(tmp_path / 'm.npz', tmp_path / 'mfp.npz', meta)
    assert r['vocab'] == 57 + len(NEW)
    m0, m1 = NumpyOpponent(tmp_path / 'm.npz'), NumpyOpponent(tmp_path / 'mfp.npz')
    X = rng.normal(size=(5, DIM)).astype(np.float32)
    C = rng.integers(0, 57, size=(5, 4))
    h0, h1 = m0.trunk(X, C), m1.trunk(X, C)
    assert np.array_equal(h0, h1)
    (g0, v0), (g1, v1) = m0.heads(h0), m1.heads(h1)
    assert np.array_equal(g0, g1) and np.array_equal(v0, v1[:, :57])
    new = NEW[0]
    i_new, i_proxy = m1.vocab[meta[new]['token']], m1.vocab[meta[cards.proxy_card(new)]['token']]
    assert np.array_equal(m1.w['emb'][i_new], m1.w['emb'][i_proxy]) and np.array_equal(v1[:, i_new], v1[:, i_proxy])
    assert m1.cost_of[meta[new]['token']] == meta[new]['cost']
