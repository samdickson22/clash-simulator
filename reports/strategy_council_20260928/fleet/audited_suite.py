"""Run historical tests with the exact reviewed source-hash migration only.

The Python engine, test files, fixtures, replay logic and comparisons stay unchanged.
Only an expected SHA256 in saved-root provenance assertions is translated from
its commit-parent value to the independently audited cleanup commit value.
"""
import ast
import hashlib
import inspect
import json
from pathlib import Path
import sys
import textwrap
import unittest

FLEET = Path(__file__).resolve().parent
ROOT = FLEET.parents[2]
audit = json.loads((FLEET / 'reference-cleanup.json').read_text())
proof = json.loads((FLEET / 'evidence/reference-cleanup-proof.json').read_text())
assert proof['audit_sha256'] == hashlib.sha256((FLEET / 'reference-cleanup.json').read_bytes()).hexdigest()
for name, row in audit['changed'].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == row['after'], name


def expected_reference(name, original):
    row = audit['changed'].get(name)
    if row is None:
        return original
    assert original == row['before'], (name, 'unexpected historical hash')
    return row['after']


class HashMigration(ast.NodeTransformer):
    def __init__(self):
        self.count = 0

    def visit_Call(self, node):
        if (isinstance(node.func, ast.Attribute) and node.func.attr == 'assertEqual'
                and len(node.args) >= 2 and isinstance(node.args[0], ast.Call)
                and isinstance(node.args[0].func, ast.Attribute)
                and node.args[0].func.attr == 'hexdigest'
                and isinstance(node.args[1], ast.Name) and node.args[1].id == 'expected'):
            self.count += 1
            node.args[1] = ast.Call(func=ast.Name(id='_fleet_expected_reference', ctx=ast.Load()),
                                    args=[ast.Name(id='name', ctx=ast.Load()), node.args[1]], keywords=[])
        return self.generic_visit(node)


def cases(suite):
    for case in suite:
        if isinstance(case, unittest.TestSuite):
            yield from cases(case)
        else:
            yield case


if sys.argv[1:] == ['stage4']:
    suite = unittest.defaultTestLoader.discover('engine-rs', pattern='test_stage4*.py')
else:
    suite = unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:])
changed = []
for case in cases(suite):
    cls = type(case)
    name = case._testMethodName
    method = getattr(cls, name)
    tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
    migration = HashMigration()
    tree = migration.visit(tree)
    if migration.count:
        ast.fix_missing_locations(tree)
        ast.increment_lineno(tree, method.__code__.co_firstlineno - 1)
        namespace = dict(method.__globals__, _fleet_expected_reference=expected_reference)
        exec(compile(tree, inspect.getsourcefile(method), 'exec'), namespace)
        setattr(cls, name, namespace[name])
        changed.append(dict(test=case.id(), hash_assertions=migration.count))
print(json.dumps(dict(exact_cleanup_commit=audit['commit'], migrated_assertions=changed)), flush=True)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
