"""Unit tests for the live-diag tail tokens in bot/search/lopp_fast.py (lb, bS<M>u<U>, bT<n>u<U>); no runtime needed.
    python3 -m pytest -q test_lopp_tail.py      (LOPP_FAST=path/to/lopp_fast.py; default: the sibling lopp_fast.py)"""
import ast, os, re
from pathlib import Path

SRC = Path(os.environ.get('LOPP_FAST', Path(__file__).with_name('lopp_fast.py'))).read_text()
WAIT = 2304


def _ns():
    """chunk_keys, wait_chunks, balanced_chunks, live_options extracted from the module source (no heavy imports)."""
    tree = ast.parse(SRC)
    want = {'chunk_keys', 'wait_chunks', 'balanced_chunks', 'live_options'}
    code = [ast.get_source_segment(SRC, n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want]
    ns = dict(WAIT=WAIT, re=re)
    exec('\n\n'.join(code), ns)
    assert want <= set(ns), want - set(ns)
    return ns


NS = _ns()
KEYS = [WAIT, 2401, 2402] + list(range(8))


def loads(parts, where, P):
    load = [0] * P
    n = 0
    for (cid, j), g in parts:
        if isinstance(cid, str):
            w = n % P
            n += 1
        else:
            w = where[cid, j]
        load[w] += len(g)
    return load


def test_balanced_same_keys_every_sample():
    for P, S in ((4, 1), (4, 2), (2, 1), (1, 1), (4, 3)):
        parts, where = NS['balanced_chunks'](KEYS, P, S)
        got = sorted((j, k) for (cid, j), g in parts for k in g)
        assert got == sorted((j, k) for j in range(S) for k in KEYS)


def test_balanced_critical_path():
    parts, where = NS['balanced_chunks'](KEYS, 4, 1)
    assert max(loads(parts, where, 4)) == 3            # default K1 P4: worker 0 runs 3 waits + 2 plays = 5
    parts, where = NS['balanced_chunks']([WAIT, 2401, 2402], 4, 1)
    assert max(loads(parts, where, 4)) == 1            # waits only: one wait per worker


def test_default_mapping_unchanged():
    # the non-lb path keeps (cid + j) % P for play chunks and the single waits chunk on worker j % P
    assert NS['chunk_keys'](KEYS, 4) == [('w', [WAIT, 2401, 2402]), (0, [0, 4]), (1, [1, 5]), (2, [2, 6]), (3, [3, 7])]
    assert "where = {(cid, j): (cid + j) % P for (cid, j), _ in parts if cid != 'w'}" in SRC
    assert "pool.submit(j % len(pool.conns), ('w', j), waits, j)" in SRC


def test_live_options():
    lo = NS['live_options']
    assert lo('K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res') == ('K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res', {})
    body, opts = lo('K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-bS16u10-bT4u10')
    assert body == 'K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res'
    assert opts == dict(balance=True, busy_scan=(16, 10), busy_cap=(4, 10))


def test_default_off_paths():
    # without tokens: top = arm top, scan_cap None, balance False
    assert "top, scan_cap = arm.get('top', 8), None" in SRC
    assert "pool_plays = plays if scan_cap is None else scan" in SRC
    assert "balance=getattr(self, 'balance', False)" in SRC
