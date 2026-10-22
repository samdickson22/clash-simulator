"""Exercise the evaluator's actual audit boundary without an engine import."""
import ast
import json
import inspect
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot.pretrain_v1 import rl_evaluate as E, rl_schedule as S, probe_roots as P


def audit_boundary(context):
    tree = ast.parse(textwrap.dedent(inspect.getsource(E.evaluate)))
    # Run the complete actual branch, including its gate and evaluator call.
    nodes = [node for node in ast.walk(tree) if isinstance(node, ast.If)
             and "phase.startswith('dev')" in ast.unparse(node.test)]
    assert len(nodes) == 1
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 E.__file__, 'exec'), context)


@pytest.fixture
def context(tmp_path, monkeypatch):
    roots = {key: str(tmp_path/key) for key in ('defense', 'spell', 'mirror')}
    for value in roots.values():
        Path(value).mkdir()
    banks = {'audits': {}}
    for key, name in [('defense', 'events.json'), ('spell', 'opportunities.json')]:
        path = Path(roots[key])/name
        path.write_text('[]')
        banks['audits'][key] = dict(path=str(path), sha256=S.file_sha(path))
    seen, written = [], []
    def evaluate(model, **kwargs):
        seen.append((model, kwargs))
        return {'valid': 'audit result'}
    monkeypatch.setattr(P, 'evaluate', evaluate)
    return dict(S=S, P=P, C=SimpleNamespace(durable_json=lambda *args: written.append(args)),
                config={'audit_roots': roots}, banks=banks, model=object(), version=4,
                phase='dev-04', directory=tmp_path/'evaluation', out=tmp_path/'run',
                seen=seen, written=written)


@pytest.mark.parametrize('phase', ['dev-04', 'primary-final'])
def test_relocated_gate_and_evaluate_use_same_exact_pinned_files(context, phase):
    context['phase'] = phase
    audit_boundary(context)
    assert len(context['seen']) == 1
    model, kwargs = context['seen'][0]
    assert model is context['model']
    assert kwargs['roots'] == context['config']['audit_roots']
    assert kwargs['ckpt'] == str(context['out']/'checkpoints/update-04.pt')
    assert context['written'] == [(context['directory']/'roots.json', {'valid': 'audit result'})]


def test_default_root_gate_is_preserved(context, monkeypatch):
    for key, name in [('defense', 'DEF'), ('spell', 'SPELL'), ('mirror', 'MIRROR')]:
        monkeypatch.setattr(P, name, Path(context['config']['audit_roots'][key]))
    context['config'] = {}
    audit_boundary(context)
    assert context['seen'][0][1]['roots'] is None


@pytest.mark.parametrize('mutation', ['changed-bytes', 'wrong-file', 'swapped', 'wrong-roots'])
def test_corrupt_or_mismatched_audit_pins_fail_before_evaluation(context, mutation, tmp_path):
    ref = context['banks']['audits']['defense']
    if mutation == 'changed-bytes':
        Path(ref['path']).write_text('[{}]')
    elif mutation == 'wrong-file':
        other = tmp_path/'same-bytes-elsewhere.json'
        other.write_text('[]')
        ref.update(path=str(other), sha256=S.file_sha(other))
    elif mutation == 'swapped':
        context['banks']['audits']['defense'], context['banks']['audits']['spell'] = (
            context['banks']['audits']['spell'], ref)
    else:
        context['config']['audit_roots']['defense'] = str(tmp_path/'unregistered')
    with pytest.raises(ValueError):
        audit_boundary(context)
    assert not context['seen'] and not context['written']
