import ast, datetime, inspect, json, os, pathlib, sys, textwrap
D=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(D/'patched'))
sys.path.append('/mpac/sdicks02/scratch/live-loop/venv/lib/python3.12/site-packages')
from bot.players import runtime
# Public resources only. Remove only the three policy-loading statements from
# the exact frozen Runtime initializer, leaving source files untouched.
source=textwrap.dedent(inspect.getsource(runtime.Runtime.__init__))
node=ast.parse(source)
removed=[]
def policy_statement(n):
 s=ast.get_source_segment(source,n)
 return ('from imitation.model import load_policy' in s or
         'self.POLICY = load_policy' in s or 'assert self.POLICY.model.temperatures' in s)
kept=[]
for n in node.body[0].body:
 if policy_statement(n): removed.append(ast.get_source_segment(source,n))
 else: kept.append(n)
assert len(removed)==3,removed
node.body[0].body=kept
ns=dict(runtime.__dict__)
exec(compile(ast.fix_missing_locations(node),runtime.__file__,'exec'),ns)
runtime.Runtime.__init__=ns['__init__']
blocked=[]
def guard(frame,event,arg):
 if event!='call': return
 name=frame.f_code.co_name; path=frame.f_code.co_filename
 if name in {'play_match','short_game','_play_with','load_policy','load_student'} or (name=='load' and '/torch/serialization.py' in path):
  blocked.append(dict(name=name,path=path)); raise RuntimeError('Model-free guard: '+name+' '+path)
sys.setprofile(guard)
print(json.dumps(dict(cwd=os.getcwd(),affinity=sorted(os.sched_getaffinity(0)),nice=os.nice(0),removed_policy_load=removed)),flush=True)
import pytest
phase=sys.argv[1]
assert phase in ('focused','full')
receipt=json.loads((D/'selection.json').read_text())
args=receipt[phase]
rc=pytest.main(['-q','-p','no:cacheprovider','--basetemp='+str(D/(phase+'-pytest-tmp'))]+args)
sys.setprofile(None)
(D/(phase+'-effective-env.json')).write_text(json.dumps(dict(os.environ),indent=2))
(D/(phase+'-model-free.json')).write_text(json.dumps(dict(removed_policy_load=removed,blocked_calls=blocked,returncode=rc),indent=2))
raise SystemExit(rc)
