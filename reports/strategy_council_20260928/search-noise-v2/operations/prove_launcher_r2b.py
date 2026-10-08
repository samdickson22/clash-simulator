"""Execute the frozen launcher's actual main AST with no-op process/resource stubs.

No study game runs and no process/job receipt is created. Checks the adapter's
selected child arguments, and compares enumeration with the frozen worker.jobs.
"""
import argparse
import ast
import json
import sys
import time
from types import SimpleNamespace
from migration_r2b import HERE, OPS, ExecutionOnlyJSON, mapping, verified, write

verified()
sys.path.insert(0, str(HERE))
from cells import CELLS, H2H


def function(path, name, namespace):
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


worker_namespace = dict(CELLS=CELLS, H2H=H2H)
jobs = function(HERE / 'worker.py', 'jobs', worker_namespace)
expected = jobs(json.loads((HERE / 'schedule.json').read_text()))
assert len(expected) == 4992
proof = json.loads((OPS / 'migration-proof-r2b.json').read_text())
for key, part in proof['partition_inputs'].items():
    import hashlib
    selected = [(j, job) for j, job in enumerate(expected) if j % 248 == int(key)]
    assert [j for j, _ in selected] == part['job_ids']
    assert hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest() == part['frozen_input_sha256']


class FakePath:
    def __truediv__(self, name):
        return self

    def read_text(self):
        return '0'

    def exists(self):
        return False

    def write_text(self, text):
        pass


results = {}
for host in ('127x04', '127x08'):
    children = []
    launches = []

    class Process:
        def __init__(self, target, args):
            assert target == 'frozen_child'
            self.args = args
            self.pid = -1
            self.exitcode = 0

        def start(self):
            children.append(self.args)

        def is_alive(self):
            return False

        def join(self):
            pass

    facade = ExecutionOnlyJSON(mapping('launch'))
    namespace = dict(argparse=argparse, socket=SimpleNamespace(gethostname=lambda: host),
                     JOBS=FakePath(), HERE=HERE, json=facade, verify=lambda m: verified(),
                     subprocess=SimpleNamespace(check_output=lambda *a, **k: ''),
                     Resources=SimpleNamespace, DerivedPublicState=lambda *a: None,
                     multiprocessing=SimpleNamespace(get_context=lambda _: SimpleNamespace(Process=Process)),
                     child='frozen_child', time=time, write=lambda p, d: launches.append(d))
    namespace['Resources'] = lambda: SimpleNamespace(costs={})
    sys.argv = ['launch_node.py', '--attempt', 'r2b', '--concurrency', '48' if host == '127x04' else '80']
    function(HERE / 'launch_node.py', 'main', namespace)()
    assert facade.calls == 1
    indices = [args[0] for args in children]
    assert indices == proof['selected'][host]
    assert all(args[1] == 248 and args[4] is False for args in children)
    assert [w['index'] for w in launches[0]['workers']] == indices
    results[host] = dict(indices=indices, workers_argument=248, pilot_argument=False,
                         concurrency=launches[0]['concurrency'], child_calls=len(children))
write(OPS / 'launcher-dry-proof-r2b.json', dict(utc=time.time(), passed=True,
      method='actual frozen launch_node.main AST, no-op Process/Resources; actual frozen worker.jobs AST',
      results=results, frozen_worker_input_digests_match=True, games_run=0))
print(json.dumps(dict(passed=True, child_calls={h: r['child_calls'] for h, r in results.items()}, games_run=0)))
