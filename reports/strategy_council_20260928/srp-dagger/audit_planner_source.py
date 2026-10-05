"""Check the audited native opt-in leaves the selected Python planner unchanged."""
import ast
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
reference=Path.home()/'.cache/clasher-engine-speed/stage0-cython/src/clasher/rl/script_rollout_planner.py'
current=ROOT/'src/clasher/rl/script_rollout_planner.py'
old_bytes,new_bytes=reference.read_bytes(),current.read_bytes()
assert hashlib.sha256(old_bytes).hexdigest()=='69f15a118197a9812debde1d8756644d6c5d2908ba4633988383370d3a90d8e3'
assert hashlib.sha256(new_bytes).hexdigest()=='d624bb24d16be0d3f324500dfdf5c64dbc06a08f3cdeab974aab06c3bf090c59'
old,new=ast.parse(old_bytes),ast.parse(new_bytes)

def dump(node): return ast.dump(node,include_attributes=False)
def isdoc(node): return isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)
def cls(tree): return next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ScriptRolloutPlanner')
a,b=cls(old),cls(new)
assert [dump(n) for n in old.body if n is not a and not isdoc(n)] == [dump(n) for n in new.body if n is not b and not isdoc(n)]
assert (a.bases,a.keywords,a.decorator_list)==(b.bases,b.keywords,b.decorator_list)==([],[],[])
am={n.name:n for n in a.body if isinstance(n,ast.FunctionDef)}
bm={n.name:n for n in b.body if isinstance(n,ast.FunctionDef)}
assert set(bm)-set(am)=={'_init_native_backend','_import_native_root'}
assert not set(am)-set(bm)
assert [dump(n) for n in a.body if not isinstance(n,ast.FunctionDef) and not isdoc(n)] == [dump(n) for n in b.body if not isinstance(n,ast.FunctionDef) and not isdoc(n)]
false_tests={dump(ast.parse(s,mode='eval').body) for s in
    ("backend not in {'python', 'native'}", "backend == 'native'", "self.backend == 'native'")}
inert_assigns={dump(ast.parse(s).body[0]) for s in ('self.backend = backend','self._native_root = None')}

class PythonBranch(ast.NodeTransformer):
    def visit_If(self,node):
        if dump(node.test) in false_tests:
            assert not node.orelse
            return None
        return self.generic_visit(node)
    def visit_Assign(self,node):
        return None if dump(node) in inert_assigns else node
    def visit_Try(self,node):
        assert not node.handlers and not node.orelse
        assert len(node.finalbody)==1 and dump(node.finalbody[0]) in inert_assigns
        return [self.visit(n) for n in node.body]

for name,prior in am.items():
    candidate=copy.deepcopy(bm[name])
    if name=='__init__':
        assert candidate.args.kwonlyargs[-1].arg=='backend'
        assert isinstance(candidate.args.kw_defaults[-1],ast.Constant) and candidate.args.kw_defaults[-1].value=='python'
        candidate.args.kwonlyargs.pop();candidate.args.kw_defaults.pop()
    # Existing _packet/_model_action have necessary try/finally blocks, unchanged.
    if name in ('__init__','_rollout','select_action'):
        candidate=PythonBranch().visit(candidate)
    assert dump(prior)==dump(candidate),name
result=dict(reference_sha256=hashlib.sha256(old_bytes).hexdigest(),
    reviewed_sha256=hashlib.sha256(new_bytes).hexdigest(),
    python_method_asts_equal=sorted(am),
    proof_scope='Explicit backend=python; disabled native branches and unused native bookkeeping removed. All original methods and module imports match the preflight AST.')
(HERE/'planner-python-source-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,sort_keys=True))
