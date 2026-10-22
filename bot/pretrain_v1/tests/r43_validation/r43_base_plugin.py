"""Run selected new regressions against exact base function bodies, without editing source."""
import ast
import copy
from pathlib import Path
import subprocess
import pytest
from bot.pretrain_v1 import rl_driver as D

SOURCE = subprocess.check_output(['git', 'show', '50f83891b4411abfd54f17122a5556ade16129f0:bot/pretrain_v1/rl_driver.py'], text=True)
TREE = ast.parse(SOURCE)


def compiled(name, env):
    node = next(n for n in TREE.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(node)], type_ignores=[])),
                 '50f83891:rl_driver.py', 'exec'), env)
    return env[name]


@pytest.fixture(autouse=True)
def base_functions(request, monkeypatch):
    if 'cpu_driver' in request.fixturenames:
        fixture = request.getfixturevalue('cpu_driver')
        fixture.config['fixture_hang_seconds'] = 6
    env = dict(D.__dict__)
    old_send = compiled('send', env)
    old_receive = compiled('receive', env)
    if 'complete_receive_deadline' in request.node.name:
        monkeypatch.setattr(D, 'receive', old_receive)
    if 'actual_stalled_sender' in request.node.name:
        def compatible_send(connection, message, timeout=None, **kwargs):
            return old_send(connection, message)
        monkeypatch.setattr(D, 'send', compatible_send)
    if 'metadata_carries' in request.node.name:
        monkeypatch.setattr(D, 'Opponents', compiled('Opponents', env))
    if 'cpu_driver' in request.fixturenames:
        # Transport stays wire-compatible. Only the owning base driver body is
        # swapped, retaining the identical real CPU child/checkpoint regression.
        env = dict(D.__dict__)
        compiled('finish_worker_session', env)
        monkeypatch.setattr(D, '_run', compiled('_run', env))
