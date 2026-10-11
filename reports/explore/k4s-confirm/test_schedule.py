"""PREREG-K4S schedule tests (replaces T1 test_schedule.py; r3 §3.1, §3.4)."""
from collections import Counter
import pytest
from schedule import blocks, block, replacement, assign_hosts, expected_order, order_for, CORE, SUBSAMPLE, ARMS


def test_counts_interleave_and_cells():
    r = blocks(); assert len(r) == 3900
    for g in range(300):
        assert [x['population'] for x in r[13*g:13*g+13]] == ['primary']*10+['guard']*3
        assert [x['index'] for x in r[13*g:13*g+10]] == list(range(10*g, 10*g+10))
    assert Counter(x['cell'] for x in r if x['population'] == 'primary') == Counter(dict.fromkeys(range(50), 60))
    assert Counter(x['cell'] for x in r if x['population'] == 'guard') == Counter(dict.fromkeys(range(18), 50))
    assert len({(x['seat'], x['own_index'], x['opponent_index']) for x in r if x['population'] == 'primary'}) == 50
    assert len({(x['seat'], x['own_index'], x['opponent_index']) for x in r if x['population'] == 'guard'}) == 18


def test_rotation_every_cell_sees_all_eight():
    r = blocks()
    for pop, cells in (('primary', 50), ('guard', 18)):
        for c in range(cells):
            rot = Counter(x['rotation'] for x in r if x['population'] == pop and x['cell'] == c)
            assert set(rot) == set(range(8)) and max(rot.values())-min(rot.values()) <= 1
    assert block('primary', 49)['rotation'] == 0 and block('primary', 50)['rotation'] == 1 and block('primary', 400)['rotation'] == 0
    assert block('guard', 17)['rotation'] == 0 and block('guard', 18)['rotation'] == 1


def test_subsample_membership_and_insertion():
    r = blocks()
    assert sum(x['subsample'] for x in r if x['population'] == 'primary') == 600
    assert sum(x['subsample'] for x in r if x['population'] == 'guard') == 300
    for x in r:
        assert x['order'] == expected_order(x)
        if x['subsample']:
            assert len(x['order']) == 10 and set(x['order']) == set(ARMS)
            core = [a for a in x['order'] if a in CORE]
            assert core == list(CORE[x['rotation']:]+CORE[:x['rotation']])
            assert x['order'][3] == 'K4-140' and x['order'][7] == 'K4-120'
        else:
            assert x['order'] == list(CORE[x['rotation']:]+CORE[:x['rotation']])
    assert order_for(0, True) == ['K4-200', 'K4S-200', 'K4-180', 'K4-140', 'K4S-180', 'K4-160', 'K4S-160', 'K4-120', 'K4S-140', 'K4S-120']


def test_smoke_has_all_arms_and_distinct_rotations():
    s = blocks(smoke=True); assert len(s) == 8
    assert sorted(x['rotation'] for x in s) == list(range(8)) and all(len(x['order']) == 10 for x in s)


def test_replacement_inherits_cell_rotation_arm_set_and_chain():
    lost = block('primary', 555)  # subsample, rotation 3, cell 5
    r = replacement(lost, [])
    assert r['index'] == 3005 and r['cell'] == 5 and r['rotation'] == lost['rotation'] and r['order'] == lost['order'] and r['subsample']
    ledger = [dict(lost=lost, replacement=r)]
    nxt = replacement(r, ledger); assert nxt['index'] == 3055 and nxt['replaces'] == lost['id'] and nxt['order'] == lost['order']
    with pytest.raises(AssertionError): replacement(lost, ledger)
    g = replacement(block('guard', 20), []); assert g['index'] == 902 and g['cell'] == 2 and g['rotation'] == 1


def test_bank_exhaustion_and_population_caps():
    for pop, max_k in (('primary', 11), ('guard', 9)):
        ledger = []; lost = block(pop, 0)
        for k in range(max_k+1):
            r = replacement(lost, ledger); ledger.append(dict(lost=lost, replacement=r)); lost = r
        with pytest.raises(AssertionError, match='exhausted'): replacement(lost, ledger)
    for pop, cap in (('primary', 300), ('guard', 90)):
        ledger = [dict(lost=block(pop, i), replacement=dict(id=f'x-{i}')) for i in range(cap)]
        with pytest.raises(AssertionError, match='population'): replacement(block(pop, cap), ledger)


def test_each_cell_visits_every_host_balanced():
    for hosts in (('127x01', '127x03'), ('127x01', '127x03', '127x08'), ('127x01', '127x03', '127x04', '127x08')):
        rows = assign_hosts(blocks(), hosts)
        for pop, cells in (('primary', 50), ('guard', 18)):
            for c in range(cells):
                counts = Counter(r['host'] for r in rows if r['population'] == pop and r['cell'] == c)
                assert set(counts) == set(hosts) and max(counts.values())-min(counts.values()) <= 1


def test_canonical_descriptor_rejects_tampering():
    from schedule import canonical
    for d in blocks()[:40]+blocks(smoke=True):
        assert canonical(dict(d, host='127x03', dispatch=1)) == {k: v for k, v in d.items()}
    d = block('primary', 50)
    for bad in (dict(d, rotation=0, order=order_for(0, True)), dict(d, index=51), dict(d, seed=d['seed']+1), dict(d, cell=1),
                dict(d, subsample=False, order=order_for(1, False)), dict(d, replacement_k=0), dict(d, extra=1)):
        with pytest.raises(AssertionError): canonical(bad)
    r = replacement(block('guard', 20), [])
    assert canonical(r) == r
    for bad in (dict(r, replacement_k=1), dict(r, replaces='guard-0021'), dict(r, index=903), dict(r, rotation=0, order=order_for(0, True))):
        with pytest.raises(AssertionError): canonical(bad)
