"""Count-only orchestration on non-reporting03; all raw games remain sealed."""
import subprocess,os,socket,signal,time,gzip,pickle
from pathlib import Path
from common import read,write,sha,job,plan,utc
from corpus import select
from pin import verify
j=job();assert socket.gethostname()=='127x03' and os.getpriority(os.PRIO_PROCESS,0)==19
cfg=plan();tiers=('K0c','S','K2','K4');source=read(j/'capture-source.json');verify(j)
assert source['reporting_hosts']==['127x01','127x08'] and socket.gethostname() not in source['reporting_hosts']
write(j/'corpus-launch.json',dict(utc=utc(),host=socket.gethostname(),nice=19,scheduler='SCHED_OTHER',game_class='qualification',capture_source=source,capture_source_sha256=sha(j/'capture-source.json'),runtime_pin_sha256=sha(j/'runtime-pin.json'),supervisor_pid=os.getpid(),supervisor_pgid=os.getpgrp(),worker_sha256=sha(j/'capture-worker.py'),supervisor_sha256=sha(__file__),initial_indices=list(range(3,11)),extension='one additional seed per insufficient tier up to63, based only on selection sufficiency',outcomes_sealed=True))
active={};completed={t:[] for t in tiers};nextindex={t:3 for t in tiers};ready=set();stop=False

def caught(*_):
 global stop
 stop=True
signal.signal(signal.SIGTERM,caught);signal.signal(signal.SIGINT,caught)
while len(ready)<4 or active:
 console=subprocess.check_output(['who'],text=True)
 if console.strip() or (j/'STOP').exists():stop=True
 for tier,row in list(active.items()):
  p,log,i=row;rc=p.poll()
  if rc is None:continue
  log.close();del active[tier]
  out=j/'captures'/f'corpus-{tier}-{i:04d}'
  if rc or not (out/'local-complete.json').exists():
   write(j/'corpus-failure.json',dict(utc=utc(),tier=tier,index=i,returncode=rc,health_only=True));stop=True
  else:completed[tier].append(i)
 if stop:
  for p,_,_ in active.values():
   try:os.killpg(p.pid,signal.SIGTERM)
   except ProcessLookupError:pass
  if not active:raise SystemExit(1)
 else:
  for slot,tier in enumerate(tiers):
   if tier in active or tier in ready:continue
   if len(completed[tier])>=8:
    paths=[j/'captures'/f'corpus-{tier}-{i:04d}'/'capture.pkl.gz' for i in completed[tier]]
    try:select(paths)
    except AssertionError:pass
    else:ready.add(tier);continue
   i=nextindex[tier]
   assert i<64,('corpus bank insufficient',tier)
   nextindex[tier]+=1;desc=j/'descriptors'/f'corpus-{tier}-{i:04d}.json';out=j/'captures'/desc.stem
   write(desc,dict(id=desc.stem,tier=tier,index=i,phase='corpus',game_class='qualification',host='127x03',seed=cfg['seed_ranges']['corpus']['base']+i))
   cores=','.join(map(str,range(slot*5,slot*5+5)));log=(j/'logs'/f'{desc.stem}.log').open('x')
   cmd=['taskset','-c',cores,'bash',str(j/'repo/reports/explore/t1/runtime.sh'),str(j/'capture-worker.py'),str(desc),str(out),cores]
   p=subprocess.Popen(cmd,stdout=log,stderr=log,start_new_session=True);active[tier]=(p,log,i)
 write(j/'corpus-progress.json',dict(utc=utc(),host='127x03',completed_games={t:len(v) for t,v in completed.items()},inflight=len(active),ready_tiers=sorted(ready),stop=stop,outcomes_sealed=True,health_only=True))
 time.sleep(5)
verify(j)
subprocess.run(['bash',str(j/'repo/reports/explore/t1/runtime.sh'),'reports/explore/t1/corpus.py','--captures',str(j/'captures'),'--out',str(j/'built-corpora')],check=True)
# Bind immutable launch and each original completion to the published selection.
receipt=j/'built-corpora/corpora.json';r=read(receipt)
r['capture_commit']=source['capture_commit'];r['capture_code_sha256']=source['capture_code_sha256'];r['capture_source_sha256']=sha(j/'capture-source.json');r['corpus_launch_sha256']=sha(j/'corpus-launch.json');r['source_completion_sha256']={str(p.relative_to(j)):sha(p) for p in sorted((j/'captures').glob('*/local-complete.json'))};r['capture_host']='127x03';r['capture_nice']=19;r['reporting_timing_overlap_on_same_host']=False
write(receipt,r)
from corpus import contract
from types import SimpleNamespace
rows=pickle.loads((j/'built-corpora/states.pkl').read_bytes());manifest=dict(corpus_receipt='corpora.json',files={'corpora.json':sha(receipt)},sets=dict(speed={tier:[row['id'] for row in rows if row['tier']==tier] for tier in tiers}))
contract().validate_capture_receipt(j/'built-corpora',manifest,SimpleNamespace(by_id={row['id']:row for row in rows}))
write(j/'CORPUS-BUILT.json',dict(utc=utc(),states_per_tier=300,tiers=4,corpora_receipt_sha256=sha(receipt),states_sha256=sha(j/'built-corpora/states.pkl'),outcomes_sealed=True))
