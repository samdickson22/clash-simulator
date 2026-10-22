"""Interrupted-owner and concurrent-publication regressions. No subprocesses are started."""
import ast
import gc
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT/'reports/bot/pretrain-v1/sweep'


def load(name):
    spec = importlib.util.spec_from_file_location('test_'+name, SCRIPTS/f'{name}.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_interrupted_owner_cannot_duplicate_empty_output(tmp_path, monkeypatch):
    import pytest
    f = load('followup_08'); b = load('sweep_08')
    out, old = tmp_path/'out', tmp_path/'old'; old.mkdir()
    for size in ['S', 'M']:
        (old/f'peaks-{size}.json').write_text(json.dumps(dict(train=10, select=5)))
    monkeypatch.setattr(f, 'OUT', out); monkeypatch.setattr(f, 'OLD', old)
    monkeypatch.setattr(f.os, 'uname', lambda: SimpleNamespace(nodename='127x08'))
    monkeypatch.setattr(f, 'sha', lambda _: 'reviewed-runtime')
    spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _: None))
    monkeypatch.setattr(f.importlib.util, 'spec_from_file_location', lambda *args: spec)
    monkeypatch.setattr(f.importlib.util, 'module_from_spec', lambda _: b)
    launches = []
    class OwnerLost(BaseException): pass
    def launch(*args):
        launches.append(args[0])
        assert (out/'intent-M50.json').exists()  # Prove intent precedes detached spawn.
        def wait(): raise OwnerLost()
        return SimpleNamespace(pid=123, wait=wait)
    monkeypatch.setattr(b, 'launch', launch)
    with pytest.raises(OwnerLost): f.main()
    gc.collect()
    with pytest.raises(FileExistsError): f.main()
    assert launches == ['M50'] and not (out/'M50').exists()


def test_ready_reader_sees_no_partial_gate(tmp_path, monkeypatch):
    import os
    tree = ast.parse((SCRIPTS/'prepare_next_snapshot.py').read_text())
    code = next(n.value.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'verifier' for t in n.targets))
    d = {'files': {}, 'batches': 83, 'matches': 1, 'rows': 2}
    gate = tmp_path/'STORE-READY.json'
    real_link = os.link
    seen = []
    def interleave(src, dst):
        seen.append(gate.exists())
        assert json.loads(Path(src).read_text()) == d
        real_link(src, dst)
        assert json.loads(gate.read_text()) == d
    monkeypatch.setattr(os, 'link', interleave)
    monkeypatch.setattr(sys, 'argv', ['verifier', str(tmp_path)])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(d)))
    exec(compile(code, 'actual-ready-verifier', 'exec'), {})
    assert seen == [False]
    # Existing gates are never overwritten by a conflicting snapshot.
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(dict(d, matches=2))))
    import pytest
    with pytest.raises(AssertionError, match='another snapshot'):
        exec(compile(code, 'actual-ready-verifier', 'exec'), {})
    assert json.loads(gate.read_text()) == d
