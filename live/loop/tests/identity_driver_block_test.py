"""Verbatim packaged driver block: UI-before-decode, exact-logit logging, fail-closed exceptions, LL0 legacy."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import types
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent));import handread
ROOT=Path('/mpac/sdicks02/scratch/live-loop');R=ROOT/'packages/handsync-identity-r7'
p=HERE.parent/'drive.py';tree=ast.parse(p.read_text())
block=None
for parent in ast.walk(tree):
 body=getattr(parent,'body',None)
 if not isinstance(body,list):continue
 for i,n in enumerate(body):
  if isinstance(n,ast.Assign) and any(ast.unparse(t)=="rec['ts_ms']" for t in n.targets):
   end=next((j for j in range(i+1,len(body)) if isinstance(body[j],ast.Expr)
             and isinstance(body[j].value,ast.Call) and ast.unparse(body[j].value.func)=='ownplay.dedupe_own_events'),None)
   if end is not None:block=body[i:end]
assert block
module=ast.Module(body=[ast.For(target=ast.Name(id='_once',ctx=ast.Store()),iter=ast.List(elts=[ast.Constant(0)],ctx=ast.Load()),
    body=block+[ast.Assign(targets=[ast.Name(id='completed',ctx=ast.Store())],value=ast.Constant(True))],orelse=[])],type_ignores=[])
code=compile(ast.fix_missing_locations(module),str(p),'exec')
meta=json.loads((R/'hud-logits-s37-30.json').read_text());cache=np.load(R/'hud-logits-s37-30.npz');LG=cache['logits'][list(cache['indices']).index(686)]
class T:
 def __init__(self,a):self.a=a
 def __getitem__(self,i):return T(self.a[i])
 def float(self):return self
 def cpu(self):return self
 def numpy(self):return self.a
old=sys.modules.get('handui')
for mode in ('normal','rollback','ui_exception'):
 calls=[];logs=[]
 def slot_ui(frame):
  calls.append('ui')
  if mode=='ui_exception':raise RuntimeError('expected UI reader failure')
  return ['greyed','greyed','coloured','greyed']
 sys.modules['handui']=types.SimpleNamespace(slot_ui=slot_ui)
 def decode(*args,**kwargs):
  calls.append(('decode',kwargs))
  if mode=='normal':assert calls[0]=='ui'
  return handread.deck_constrained(*args,**kwargs)
 rec={'hand':{'cards':['Giant','Fireball','Valkyrie','Musketeer'],'probs':[.9]*4}}
 ns={'rec':rec,'ts_ms':1234.5,'HANDSYNC':mode!='rollback','raw':{'out':[None]*4+[T(LG[None])]},
     'rt':types.SimpleNamespace(R=types.SimpleNamespace(costs=meta['costs'])),'perc':types.SimpleNamespace(cards=meta['cards']),
     'deck':meta['deck'],'handread':types.SimpleNamespace(deck_constrained=decode),'f':object(),'row':{},'n':687,
     'log':lambda *a:logs.append(a),'completed':False}
 exec(code,ns)
 if mode=='ui_exception':
  assert not ns['completed'] and calls==['ui'] and len(logs)==2
  assert logs[0][1]['component']=='handui'
 elif mode=='normal':
  assert ns['completed'] and rec['hand']['cards'][2]=='Archers' and rec['hand']['ui_consistent']
  exact=np.asarray(json.loads(json.dumps(rec['hand']['model_logits'])),np.float32)
  assert exact.shape==LG.shape and exact.tobytes()==LG.astype(np.float32).tobytes()
 else:
  assert ns['completed'] and len(calls)==1 and calls[0]==('decode',{})
  assert rec['hand']['cards'][2]=='Valkyrie' and 'model_logits' not in rec['hand'] and 'ui' not in rec['hand']
 print('PASS actual driver block',mode)
if old is None:sys.modules.pop('handui',None)
else:sys.modules['handui']=old
# Honest config says exact HUD evidence only when enabled, with model vocabulary order.
kw=next(k for n in ast.walk(tree) if isinstance(n,ast.Call) for k in n.keywords if k.arg=='hand_decoder')
for mode in (True,False):
 config=eval(compile(ast.Expression(kw.value),str(p),'eval'),{'HANDSYNC':mode,'perc':types.SimpleNamespace(cards=meta['cards'])})
 assert config['cards']==meta['cards'] and bool(config['model_logits'])==mode
print('PASS decoder/logit provenance describes disabled rollback truthfully')
base=ast.parse((ROOT/'packages/handsync-availability-r6/live/loop/drive.py').read_text())
for name in ('LiveFrames','ReplayFrames','AdbTaps'):
 get=lambda t:ast.dump(next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name==name),include_attributes=False)
 assert get(tree)==get(base),name
assert not any(isinstance(n,ast.FunctionDef) and n.name=='grab_arena_bg' for n in ast.walk(tree))
print('PASS primary capture/replay/tap class AST unchanged; secondary grabber absent')
