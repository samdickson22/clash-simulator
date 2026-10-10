"""Metadata-only tests; no policy, GPU, build or simulated game."""
import ast
from pathlib import Path
import pytest
import postkill_selected as s

def records():
    return {arm: {'teacher': {'metrics': {'play_recall': {'value': value}}}}
            for arm, value in zip(s.RECORDS, (.259, .235, .252, .256, .226))}

def test_completed_recipes_choose_x4_without_x5_x7():
    assert s.chosen_from_results(records()) == ['X1', 'X2', 'X4']

def test_missing_record_rejected():
    r = records(); r.pop('X6')
    with pytest.raises(AssertionError): s.chosen_from_results(r)

def test_family_variants_excluded_even_if_better():
    r = records(); r['X5'] = r['X4']
    with pytest.raises(AssertionError): s.chosen_from_results(r)

def test_tie_uses_numeric_order():
    r = records(); r['X4'] = r['X3']
    assert s.chosen_from_results(r) == ['X1', 'X2', 'X3']

def test_child_routes_are_selected_versions():
    root = Path(__file__).parent
    assert 'ops/postkill_block_worker_selected.py' in (root/'game_pool_postkill_selected.py').read_text()
    assert 'ops/game_worker_postkill_selected.py' in (root/'postkill_block_worker_selected.py').read_text()
    assert 'import k_postkill_selected as adapter' in (root/'game_worker_postkill_selected.py').read_text()
    for name in ('game_pool_postkill_selected', 'postkill_block_worker_selected', 'game_worker_postkill_selected', 'reduce_postkill_selected'):
        ast.parse((root/(name+'.py')).read_text())

def test_adapter_calls_unchanged_qualified_search(monkeypatch, tmp_path):
    import k_postkill_selected as adapter
    called = []
    original_label = adapter.original.labelled
    monkeypatch.setattr(adapter.original, 'run_case', lambda *args, **kwargs: called.append((args, kwargs)))
    adapter.run_case(tmp_path, 'X4', 0, smoke=False)
    assert called == [((tmp_path, 'X4', 0), {'smoke': False})]
    assert adapter.original.labelled is original_label
