"""One bounded30frame/oneCPU inference receipt; exact deployed ft-r6, no events/runtime/search/training."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys,time
import cv2
import numpy as np
import torch
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
cv2.setNumThreads(1);torch.set_num_threads(1);torch.set_num_interop_threads(1)
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent))
import handread,handui,canvas
from clasher.vision.l1_v4 import prepare_pixels
ROOT=Path('/mpac/sdicks02/scratch/live-loop');R=ROOT/'packages/handsync-identity-r7'
export=Path('/mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-ft-r6')
sha=hashlib.sha256((export/'frame.pt').read_bytes()).hexdigest()
assert sha=='650bd5cf5d6677de7da2837cee401ea66efa17f9791c4bdfa942636aa97e63da'
assert hashlib.sha256((export/'vocab.json').read_bytes()).hexdigest()=='ea43ae2e02c252e7cb412671f121bc880a2f2679fd8a00c8e99dcdc912ac111a'
model=torch.jit.load(str(export/'frame.pt'),map_location='cpu').eval()
cards=json.loads((export/'vocab.json').read_text())['cards']
D=list(map(json.loads,(ROOT/'runs/s37/decisions.jsonl').read_text().splitlines()))
refs={d['n']:d for d in D if (d.get('stats')or{}).get('tap_guard')}
keep=[144,154,193,287,401,514,584,696,860,1087,1196,1290,1646,1804,1888]
S={d['n']:d for d in D if d.get('submitted') and d['n'] in keep}
selected=sorted(set(refs)|set(S));assert len(selected)==30
DECK=json.loads((ROOT/'runs/s37/session-config.json').read_text())['deck']
COSTS=dict(Valkyrie=4,Archers=3,Minions=3,Cannon=3,Fireball=4,Giant=5,MiniPekka=4,Musketeer=4)
source=ROOT/'packages/handsync-availability-r6/live/loop/drive.py'
ns={'np':np,'cv2':cv2};node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='normalize')
exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),ns)
oldpath=ROOT/'evidence/r7-deployed-handread-20261016T113139Z/source/handread.py'
spec=importlib.util.spec_from_file_location('released_handread',oldpath);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
rows=[];logits=[];times=[]
with torch.inference_mode():
 for n in selected:
  imagepath=ROOT/f'runs/s37/video/{n:06d}.jpg';image=cv2.imread(str(imagepath));assert image is not None
  frame,white=ns['normalize'](canvas.to_android(image))
  arena,hud=prepare_pixels(canvas.canvas(frame))
  t=lambda x:torch.from_numpy(np.ascontiguousarray(x)).permute(2,0,1)[None].float().div(255)
  start=time.perf_counter();out=model(t(arena),t(hud));times.append((time.perf_counter()-start)*1000)
  lg=out[4][0].float().numpy();logits.append(lg)
  ui=handui.slot_ui(frame)
  baseline=old.deck_constrained(lg,cards,DECK)
  assert handread.deck_constrained(lg,cards,DECK)==baseline
  candidate=handread.deck_constrained(lg,cards,DECK,ui=ui,costs=COSTS)
  d=refs.get(n)or S[n];slot=(d['stats']['action'] if n in refs else d['action'])//576
  truth=('Valkyrie' if n==1082 else 'Archers') if n in refs else d['card']
  rows.append(dict(n=n,kind='refused' if n in refs else 'submitted',slot=slot,truth=truth,
    original_requested_action=d['stats']['action'] if n in refs else d['action'],ui=ui,baseline=baseline,candidate=candidate,
    image_sha256=hashlib.sha256(imagepath.read_bytes()).hexdigest(),white=white))
  print(n,truth,'old',baseline['cards'][slot],baseline['probs'][slot],
              'new',candidate['cards'][slot],candidate['probs'][slot],flush=True)
np.savez_compressed(R/'hud-logits-s37-30.npz',indices=np.array(selected),logits=np.array(logits))
(R/'hud-logits-s37-30.json').write_text(json.dumps(dict(model_path=str(export),frame_sha256=sha,
 vocab_sha256=hashlib.sha256((export/'vocab.json').read_bytes()).hexdigest(),cards=cards,deck=DECK,costs=COSTS,
 numerical_threads=1,max_frames=30,rows=rows,inference_ms=times,source_kind='decoded retained quality85 JPEG, not exact original uncompressed logits'),indent=2)+'\n')
print('receipt',R/'hud-logits-s37-30.json',flush=True)
