"""The fast-prep fc cut caches stay bounded in a long-lived process and return the same text as an unbounded cache.
    python3 -m pytest -q bot/search/test_fastprep_cut_cache.py      (no runtime needed)

HP1 RL actors (2026-10-20) grew ~20 MiB of private memory per search game: _ConfigJson._cut (on rt, process-wide)
kept every cut config text, keyed by the cards and side-table entries of each root, and those keys keep changing
with the decks and the board. A dropped text is rebuilt byte for byte, so only memory and speed may change."""
import json

import pytest

import bot.cards.fc_cut as fc
import bot.search.lopp_fast as lf

N = 40
CONFIG = dict(
    arena=dict(width=18, height=32),
    cards={f'C{i}': dict(stats=dict(name=f'C{i}', hp=100 + i, death=f'D{i}')) for i in range(N)},
    death_children={f'D{i}': dict(units=[f'C{(i + 1) % N}'], count=i % 3 + 1) for i in range(N)},
)


def states(n):
    """n roots with distinct (hand + cycle, board) card sets, hence distinct cut keys."""
    out = []
    for g in range(n):
        own = [f'C{(g + k) % N}' for k in range(8)]
        opp = [f'C{(3 * g + k) % N}' for k in range(8)]
        board = [dict(stats=dict(name=f'C{(7 * g) % N}', hp=1))]
        out.append(dict(tick=g, players=[dict(hand=own[:4], cycle=own[4:]), dict(hand=opp[:4], cycle=opp[4:])],
                        entities=board, pending_casts=[], config=CONFIG))
    return out


def cuts(texts):
    return {t[t.index('"config": '):] for t in texts}


def run(n, cap, monkeypatch):
    monkeypatch.setattr(lf, 'CUT_TEXTS', cap)     # read when the caches are built
    shim = lf._ConfigJson(CONFIG, verify=False)
    shim.cut = True
    roots = states(n)
    texts = [shim.dumps(r) for r in roots]
    again = [shim.dumps(r) for r in roots[:5]]   # long evicted under a small cap: rebuilt
    return shim, texts, again


def check(shim, texts, again, ref_texts, cap):
    assert texts == ref_texts and again == ref_texts[:5]
    assert len(shim._cut) <= cap
    for t in texts:
        cfg = json.loads(t)['config']
        assert set(cfg['cards']) < set(CONFIG['cards']) and cfg['arena'] == CONFIG['arena']


def test_cut_texts_lru():
    c = lf._CutTexts(2)
    c['a'], c['b'] = 1, 2
    assert c['a'] == 1          # touch a: b is now the least recently used
    c['c'] = 3
    assert list(c) == ['a', 'c'] and 'b' not in c
    assert lf._CutTexts().cap == lf.CUT_TEXTS


def test_cards_cut_bounded_and_identical(monkeypatch):
    n = 4 * 8
    ref, ref_texts, _ = run(n, 10 ** 9, monkeypatch)
    assert len(ref._cut) == len(cuts(ref_texts)) > 8   # the unbounded cache keeps every distinct cut (the leak)
    shim, texts, again = run(n, 8, monkeypatch)
    check(shim, texts, again, ref_texts, cap=8)


@pytest.fixture
def side_cut(monkeypatch):
    """fc_cut.install() patches lopp_fast process-wide; restore it after the test."""
    for obj, name in ((lf._ConfigJson, 'dumps'), (lf.ConfigCache, '__init__'), (lf.ConfigCache, 'payload')):
        monkeypatch.setattr(obj, name, obj.__dict__[name])
    monkeypatch.setattr(lf, '_side_cut_installed', getattr(lf, '_side_cut_installed', False), raising=False)
    lf._side_cut_installed = False
    fc.install()


def test_side_cut_bounded_and_identical(side_cut, monkeypatch):
    n = 4 * 8
    ref, ref_texts, _ = run(n, 10 ** 9, monkeypatch)
    assert len(ref._cut) == len(cuts(ref_texts)) > 8 and len(ref._side._text) > 8
    shim, texts, again = run(n, 8, monkeypatch)
    check(shim, texts, again, ref_texts, cap=8)
    assert len(shim._side._text) <= 8
    assert all('death_children' in json.loads(t)['config'] for t in texts)


def test_level_cut_config_bounded_and_identical(monkeypatch):
    """bot.levels.configs.CutConfig (one per level root) keeps the same kind of texts."""
    from bot.levels.configs import CutConfig
    roots = states(4 * 8)

    def texts(cap):
        monkeypatch.setattr(lf, 'CUT_TEXTS', cap)
        cc = CutConfig(CONFIG)
        out = [cc.text(r['players'], r['entities'], r['pending_casts']) for r in roots]
        return cc, out + [cc.text(r['players'], r['entities'], r['pending_casts']) for r in roots[:5]]

    ref, ref_texts = texts(10 ** 9)
    assert len(ref._cut) == len(set(ref_texts)) > 8
    cc, out = texts(8)
    assert out == ref_texts and len(cc._cut) <= 8 and len(cc.side._text) <= 8
