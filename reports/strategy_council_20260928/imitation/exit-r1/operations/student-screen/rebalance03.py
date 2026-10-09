"""Hand off only unclaimed03 identities; let captured children finish untouched."""
import datetime,hashlib,json,os,signal,time
from pathlib import Path
job=Path('/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stat(pid):return Path(f'/proc/{pid}/stat').read_text()
def fields(s):return s[s.rfind(')')+2:].split()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.partial');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
snap=json.loads((job/'rebalance-03-claim-snapshot.json').read_text());pid=snap['manager_pid']
assert fields(stat(pid))[0]=='T'
active=set()
for v in snap['children'].values():
 c=v['cmdline']
 if '--mode' in c:active.add((c[c.index('--mode')+1],c[c.index('--arm')+1],int(c[c.index('--offset')+1])))
queues=[json.loads(p.read_text()) for p in sorted((job/'stage-queues/03').glob('*.json'))]
completed=set()
for q in queues:
 for task in q['tasks']:
  mode,arm,i=task
  p=job/'heldout'/f'game-{i:09d}'/'receipt.json' if mode=='teacher' else job/'stage-cases'/q['stage']/f'{mode}-{arm}-{i:04d}.json'
  if not p.exists():continue
  r=json.loads(p.read_text())
  if mode=='teacher':completed.add(tuple(task));continue
  assert r['terminal'] and r['freeze_sha256']==q['freeze_sha256'] and (r['mode'],r['arm'],r['index'])==tuple(task)
  completed.add(tuple(task))
alltasks={tuple(t) for q in queues for t in q['tasks']}
assert active<=alltasks
moved=[];hosts=['04','08']
for q in queues:
 pending=[t for t in q['tasks'] if tuple(t) not in completed|active]
 for n,h in enumerate(hosts):
  assigned=pending[n::2]
  if assigned:
   dest=job/'stage-queues-r2'/h/f'010-rebalanced-{q["stage"]}.json'
   write(dest,dict(q,host=h,tasks=assigned));moved+=assigned
write(job/'reporting-rebalance-transfer.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),snapshot_sha256=sha(job/'rebalance-03-claim-snapshot.json'),original_tasks=len(alltasks),completed_at_handoff=len(completed),captured_claims=len(active),moved=len(moved),moved_tasks=moved,retained_tasks=[list(t) for t in sorted(alltasks-{tuple(t) for t in moved})],destinations={h:sum(len(json.loads(p.read_text())['tasks']) for p in (job/'stage-queues-r2'/h).glob('*.json')) for h in hosts}))
print(json.dumps({'completed':len(completed),'captured':len(active),'moved':len(moved)}),flush=True)
while True:
 stats={k:stat(k) for k in snap['children'] if Path(f'/proc/{k}').exists()}
 assert len(stats)==len(snap['children']), 'captured child disappeared before accounting'
 if all(fields(s)[0]=='Z' for s in stats.values()):break
 time.sleep(2)
parent=stat(pid);f=fields(parent);hz=os.sysconf('SC_CLK_TCK')
assert all(int(fields(s)[49])==0 for s in stats.values()),'captured child failed'
old=json.loads((job/'reporting/staged-r1/progress.json').read_text())
manager=(int(f[11])+int(f[12]))/hz
children=(int(f[13])+int(f[14])+sum(int(fields(s)[11])+int(fields(s)[12]) for s in stats.values()))/hz
write(job/'reporting/staged-r1/exit.json',dict(host='127x03',complete=True,completed=len(alltasks)-len(moved),tasks=len(alltasks)-len(moved),failures=[],queue_sha256=old['queue_sha256'],elapsed_seconds=old['elapsed_seconds']+(time.time()-Path(job/'rebalance-03-claim-snapshot.json').stat().st_mtime),peak_owned_processes=old['peak_owned_processes'],minimum_mem_available_bytes=old['minimum_mem_available_bytes'],cores=list(range(56)),manager_cpu_seconds=manager,children_cpu_seconds=children,own_workers_vacated=True,stop_requested=False,claim_handoff=True,cpu_accounting='procstat ticks: parent self/reaped children plus unreaped captured children; no double counting',clock_ticks_per_second=hz,cpu_tick_rounding_bound_seconds=2*(2+len(stats))/hz))
write(job/'rebalance-03-retirement-accounting.json',dict(manager_procstat=parent,child_procstats=stats,manager_cpu_seconds=manager,children_cpu_seconds=children))
os.kill(pid,signal.SIGKILL)
print('all captured children finished cleanly; old paused manager retired',flush=True)
