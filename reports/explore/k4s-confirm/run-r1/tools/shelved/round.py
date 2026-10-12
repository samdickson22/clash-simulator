"""K4S runner r1: one frozen-T1 replacement cycle (coordinator Option A afe83faa + standing policy P2 adc12f36).

Replaces tools/round.sh (Sol review r1 REJECT). Every remote step runs under `bash -euo pipefail`, every check raises,
and every step writes a hash-bound receipt under run-r1/rounds/rN/ that the next step requires. Nothing is ever killed
except through the frozen owned STOP / STOP-COPY tokens. Game files are only hashed by the frozen replace.py; no
outcome field is read. Steps (run by hand, in order, checking each output):
  round.py stop      N            # owned STOP on both hosts of the active phase; prove supervisor + every worker group gone
  round.py drain     N            # every completed block ACK-durable+returned on 05; STOP-COPY; copier exited+revoked
  round.py inventory N            # bound hub view; frozen replace.py on a working ledger; validate; publish
  round.py stage     N            # fresh namespace k4s-confirm-replacement-rN; fresh qualification (detached)
  round.py finalize  N            # qualification, runtime==smoke runtime, carry-over, 03 idle pin, dispatch, auth, barrier
  round.py pretrigger N HOST      # one ordinary login to refresh a stale motd stamp; wait for root checks to exit
  round.py prelaunch N [--builder released|timeout|na]   # timers, stamps, maintenance quiet, escalation gates
  round.py launch    N            # copier then frozen launch.sh per host; confirm admission + launch receipt
History of this run's phases (namespace, phase, dispatch sha) lives in rounds/history.json; round N's source is
history[-1] (the phase that is active when the round starts).
"""
import argparse,collections,datetime,glob,hashlib,json,os,re,shlex,shutil,subprocess,sys,time
from pathlib import Path
L=Path('/mpac/sdicks02/k4s-runner/run-r1');W=Path('/mpac/sdicks02/repos/clasher-k4s-run');K=W/'reports/explore/k4s-confirm'
sys.path.insert(0,str(K))
from schedule import canonical  # frozen
ROOT={'127x03':'/mpac/sdicks02/jobs/clasher','127x04':'/mpac/sdicks02/jobs-k4s'};HOSTS=('127x03','127x04');CORE={'127x03':62,'127x04':63}
SMOKE_NS='k4s-confirm-r1'
FROZEN_K4S='416f6e51e32e1900faaf8ceaf329287475a6a621fb1dc2d1b6def50ebb528ed1'
SMOKE={'127x03':dict(SMOKE_PASS='d3ed1c61092633bc57c8b7814f8f76829fd013720f1536e0cd926322fc8fc722',admission='e338db63456772b930334dfb898839380b8c9180da35252c04c4c9f0d71eb24f'),
       '127x04':dict(SMOKE_PASS='5c4b7606a79b18614b9d25759ab7f7d2b686bd9cbc47767121e786bf94318a0b',admission='9c4d636f13a141b3399eb0307f4edfc7af2407af37fc27dbe24d154929af9c1c')}
PREREG='reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md';PREREG_SHA='9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a'
IDLE03=dict(pid=2180947,start_ticks=139691386,cmdline_prefix='16152ceb')
CAPS=dict(primary=150,guard=45);KLIM=dict(primary=9,guard=7)   # Option A escalation: 50% of caps; k at limit-2
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10']

def utc():return subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,indent=1)+'\n');t.replace(p)
def fail(msg):raise SystemExit('ROUND FAIL: '+msg)
def remote(h,script,timeout=600):
 assert h in HOSTS
 p=subprocess.run(SSH+[h,'bash -euo pipefail -s'],input='set -euo pipefail\n'+script,capture_output=True,text=True,timeout=timeout)
 if p.returncode!=0:fail(f'{h} remote rc {p.returncode}: {p.stderr.strip()[-800:]}')
 return p.stdout
def remote_json(h,path):return json.loads(remote(h,f'cat {shlex.quote(path)}'))
def rdir(N):d=L/'rounds'/f'r{N}';d.mkdir(parents=True,exist_ok=True);return d
def need(N,step):
 p=rdir(N)/f'{step}.json'
 if not p.exists():fail(f'missing prerequisite receipt {p}')
 return read(p)
def history():return read(L/'rounds'/'history.json')
def job(h,ns):return f'{ROOT[h]}/{ns}'
def py(h,code):return remote(h,"python3 - <<'PYEOF'\n"+code+"\nPYEOF\n")

def group_live(h,pgids):
 """Live (non-zombie) members of the given process groups on h; read-only."""
 if not pgids:return {}
 out=remote(h,'ps -eo pgid=,pid=,stat= || true')
 live=collections.defaultdict(list)
 for line in out.split('\n'):
  f=line.split()
  if len(f)==3 and int(f[0]) in pgids and not f[2].startswith('Z'):live[int(f[0])].append(int(f[1]))
 return dict(live)

def cmd_stop(N):
 src=history()[-1];ns,ph,dsha=src['namespace'],src['phase'],src['dispatch_sha256']
 if (rdir(N)/'stop.json').exists():fail('stop receipt exists')
 rec=dict(utc=utc(),round=N,namespace=ns,phase=ph,dispatch_sha256=dsha,hosts={})
 for h in HOSTS:
  J=job(h,ns);launch=remote_json(h,f'{J}/{ph}/launch.json')
  if launch['host']!=h or launch['dispatch_sha256']!=dsha:fail(f'{h} launch binding {launch}')
  remote(h,f'test ! -e {J}.STOP; date -u +%FT%T.%3NZ > {J}.STOP')
 for h in HOSTS:
  J=job(h,ns);launch=remote_json(h,f'{J}/{ph}/launch.json');sup=launch['supervisor_pid']
  adm=remote_json(h,f'{J}/owned-supervisor-admission.json')
  if adm['supervisor']['pid']!=sup:fail(f'{h} supervisor admission pid mismatch')
  pg=[adm['supervisor']['pgid']]+[g['pgid'] for g in adm['worker_groups']]
  for _ in range(300):
   if not group_live(h,set(pg)):break
   time.sleep(1)
  live=group_live(h,set(pg))
  if live:fail(f'{h} owned groups still live after STOP: {live}')
  ex=remote_json(h,f'{J}/{ph}/supervisor-exit.json')
  if ex['host']!=h:fail(f'{h} exit host')
  rec['hosts'][h]=dict(stop_touched=remote(h,f'cat {J}.STOP').strip(),supervisor=adm['supervisor'],worker_groups_checked=len(pg)-1,live_after=0,
                       exit=dict(utc=ex['utc'],reason=ex['reason'],completed=[d['id'] for d in ex['completed']],failed=[d['id'] for d in ex['failed']],unstarted=len(ex['unstarted'])))
  print(h,'stopped',ex['utc'],ex['reason'],'completed',len(ex['completed']),'failed',len(ex['failed']),'unstarted',len(ex['unstarted']),'groups checked',len(pg))
 write(rdir(N)/'stop.json',rec)

def hub_ok(J,ph,h,bid):
 d=Path(J)/'hub-blocks'/ph/bid
 try:
  a=read(d/'hub-ack.json');m=read(d/'hub-ack.returned.json')
  return (a['hub']=='127x05' and a['source_host']==h and a['job']==J and a['phase']==ph and a['block']==bid and a['complete_sha256']==sha(d/'complete.json')
          and m['hub_ack_sha256']==sha(d/'hub-ack.json'))
 except (OSError,ValueError,KeyError):return False

def cmd_drain(N):
 st=need(N,'stop');ns,ph=st['namespace'],st['phase']
 if (rdir(N)/'drain.json').exists():fail('drain receipt exists')
 rec=dict(utc=utc(),round=N,namespace=ns,phase=ph,hosts={})
 for h in HOSTS:
  J=job(h,ns);want=set(st['hosts'][h]['exit']['completed'])
  listed=set(x for x in remote(h,f'cd {J}/{ph} && find . -mindepth 2 -maxdepth 2 -name complete.json | sort').split() )
  listed={x.split('/')[1] for x in listed}
  if listed!=want:fail(f'{h} complete.json set != supervisor completed ({len(listed)} vs {len(want)})')
  for _ in range(90):
   if all(hub_ok(J,ph,h,b) for b in want):break
   time.sleep(10)
  bad=[b for b in want if not hub_ok(J,ph,h,b)]
  if bad:fail(f'{h} blocks not durable+returned on 05: {bad[:5]}')
  adm=read(f'{J}/owned-copier-admission.json');ident=adm['identity']
  if adm['phase']!=ph or adm['source_host']!=h or adm['job']!=J:fail(f'{h} copier admission binding')
  Path(f'{J}/STOP-COPY').write_text(utc()+'\n')
  for _ in range(180):
   if not Path(f'/proc/{ident["pid"]}').exists():break
   time.sleep(1)
  if Path(f'/proc/{ident["pid"]}').exists():fail(f'{h} copier {ident["pid"]} still alive (STOP-COPY kept)')
  hc=read(f'{J}/copy-health-{h}.json');adm2=read(f'{J}/owned-copier-admission.json');srcadm=remote_json(h,f'{J}/owned-copier-admission.json')
  if not (hc.get('revoked') is True and not hc.get('lifecycle_error') and not hc.get('fatal_error') and adm2['identity']==ident and adm2['active'] is False
          and srcadm['identity']==ident and srcadm['active'] is False):fail(f'{h} copier revocation not proven (STOP-COPY kept)')
  os.remove(f'{J}/STOP-COPY')
  rec['hosts'][h]=dict(completed=len(want),durable_and_returned=len(want),copier=ident,revoked=True)
  print(h,'drained',len(want),'blocks durable+returned; copier',ident['pid'],'revoked on hub and source')
 write(rdir(N)/'drain.json',rec)

def cmd_inventory(N):
 st=need(N,'stop');dr=need(N,'drain');hist=history()
 if (rdir(N)/'inventory.json').exists():fail('inventory receipt exists')
 if dr['namespace']!=st['namespace']:fail('stop/drain mismatch')
 out=L/'dispatch'/f'replacement-r{N}.json'
 if out.exists():fail(f'{out} already published')
 work=rdir(N)/'work';
 if work.exists():fail(f'{work} exists from a failed attempt: reconcile by hand')
 work.mkdir()
 # source phases: exactly the stopped phase, both hosts
 src=[]
 for h in HOSTS:
  J=job(h,st['namespace']);M=work/f'phase-meta-{h}';M.mkdir()
  subprocess.run(['rsync','-a','--include=launch.json','--include=supervisor-exit.json','--include=stop-reason.json','--include=pids/***','--include=descriptors/***','--include=exits/***','--exclude=*',f'{h}:{J}/{st["phase"]}/',str(M)+'/'],check=True,timeout=300)
  if read(M/'launch.json')['dispatch_sha256']!=st['dispatch_sha256'] or read(M/'supervisor-exit.json')['host']!=h:fail(f'{h} phase metadata binding')
  src.append(M)
 # bound hub view: only this run's phases (history), each block validated against its phase's dispatch row
 V=work/'hub-view';V.mkdir();counted={}
 for ent in hist:
  disp={r['id']:r for r in read(L/'dispatch'/ent['dispatch_file'])['blocks']}
  if sha(L/'dispatch'/ent['dispatch_file'])!=ent['dispatch_sha256']:fail(f'history dispatch hash {ent}')
  for h in HOSTS:
   J=job(h,ent['namespace'])
   for d in sorted(glob.glob(f'{J}/hub-blocks/{ent["phase"]}/*/')):
    d=Path(d);bid=d.name
    if not (d/'hub-ack.json').exists():continue
    if not hub_ok(J,ent['phase'],h,bid):fail(f'hub block binding {h} {ent["namespace"]} {bid}')
    proof=read(d/'complete.json');desc=proof['descriptor'];row=disp.get(bid)
    if row is None or row['host']!=h:fail(f'{bid} not in {h} rows of {ent["dispatch_file"]}')
    if {k:v for k,v in desc.items() if k not in ('host','dispatch')}!={k:v for k,v in row.items() if k not in ('host','dispatch')}:fail(f'{bid} descriptor differs from dispatch row')
    canonical(desc)
    if bid in counted:fail(f'duplicate durable block {bid}')
    counted[bid]=desc;os.symlink(str(d).rstrip('/'),V/bid)
 led_in=L/'ledger'/'blind-ledger.json';led_work=work/'blind-ledger.json';shutil.copyfile(led_in,led_work);before=len(read(led_in)['events'])
 disp_work=work/f'replacement-r{N}.json'
 dis=[L/'dispatch'/e['dispatch_file'] for e in hist]
 subprocess.run(['nice','-n','19','/bin/python3','-B','replace.py','--source-phases',*map(str,src),'--dispatches',*map(str,dis),'--hub',str(V),'--ledger',str(led_work),
                 '--dispatch-out',str(disp_work),'--hosts','127x03','127x04','--stop-file',str(work/'STOP-replace')],cwd=str(K),check=True,timeout=1800)
 d=read(disp_work);rows=d['blocks'];ev=read(led_work)['events'];new=ev[before:]
 for r in rows:canonical(r)
 failed={b for h in HOSTS for b in st['hosts'][h]['exit']['failed']}
 if {e['lost']['id'] for e in new}!=failed:fail('new ledger events != failed blocks of the stopped phase')
 repl={e['replacement']['id'] for e in new}
 if not repl<= {r['id'] for r in rows}:fail('a new replacement is missing from the dispatch')
 logical=collections.Counter()
 for desc in counted.values():logical[desc.get('replaces') or desc['id']]+=1
 for r in rows:logical[r.get('replaces') or r['id']]+=1
 want={f'primary-{i:04d}' for i in range(3000)}|{f'guard-{i:04d}' for i in range(900)}
 if set(logical)!=want or any(v!=1 for v in logical.values()):fail('logical coverage is not exact')
 lost=collections.Counter(e['lost']['population'] for e in ev);kmax=collections.defaultdict(int)
 for e in ev:kmax[e['replacement']['population']]=max(kmax[e['replacement']['population']],e['replacement']['replacement_k'])
 gates=[p for p in CAPS if lost[p]>=CAPS[p]]+[f'k:{p}' for p in KLIM if kmax[p]>=KLIM[p]]
 # publish (only after every check): previous ledger kept, new ledger + dispatch promoted
 shutil.copyfile(led_in,L/'ledger'/f'blind-ledger-before-r{N}.json');shutil.copyfile(led_work,led_in);shutil.copyfile(disp_work,out)
 rec=dict(utc=utc(),round=N,source=st['namespace']+':'+st['phase'],counted=len(counted),rows=len(rows),hosts=dict(collections.Counter(r['host'] for r in rows)),
          games=sum(len(r['order']) for r in rows),never_started=len(d['never_started_redispatched']),new_events=len(new),ledger_events=len(ev),
          cumulative_lost=dict(lost),max_k=dict(kmax),escalation=gates,dispatch=dict(path=str(out),sha256=sha(out)),ledger_sha256=sha(led_in),coverage='exact')
 write(rdir(N)/'inventory.json',rec);print(json.dumps(rec))
 if gates:fail(f'ESCALATE to the coordinator before launch: {gates}')

STAGE='''J={J};S={S}
test ! -e "$J" && test ! -e "$J.STOP"
rm -rf "$S/overlay-src";mkdir -p "$S/overlay-src";tar -x -C "$S/overlay-src" -f "$S/overlay-391d2006.tar"
test "$(sha256sum "$S/extras-repl-r{N}.tar" | cut -d' ' -f1)" = "{XSHA}"
cd "$S/overlay-src/reports/explore/k4s-confirm"
nice -n 19 /mpac/sdicks02/repos/clasher/.venv/bin/python -B stage_k4s.py --job "$J" --overlay . {BASE}
tar -x -C "$J/repo" -f "$S/extras-repl-r{N}.tar"
ln -s "$J.STOP" "$J/STOP"
cd "$J/repo";sha256sum --quiet -c "$S/frozen-overlay.sha256"
mkdir -p "$(dirname {PREREG})";cp "$S/PREREG-K4S-DRAFT-r3.md" {PREREG};test "$(sha256sum {PREREG} | cut -d' ' -f1)" = {PSHA}
grep -q "$J" reports/explore/t1/plan.json
bash reports/explore/k4s-confirm/detach.sh "$J/qualification-driver.log" "$J/qualification-driver-pid.json" env K4S_JOB="$J" OWNED_STOP="$J.STOP" NICE=10 bash reports/explore/k4s-confirm/run_qualification.sh
'''
def cmd_stage(N):
 need(N,'inventory');ns=f'k4s-confirm-replacement-r{N}'
 if (rdir(N)/'stage.json').exists():fail('stage receipt exists')
 rec=dict(utc=utc(),round=N,namespace=ns,hosts={})
 for h in HOSTS:
  J=job(h,ns);S=f'{ROOT[h]}/k4s-confirm-r1-stage';tar=Path(f'/mpac/sdicks02/k4s-runner/stage/extras-{h}-repl-r{N}.tar')
  subprocess.run(['bash',str(K/'export_staging_extras.sh'),J,str(tar)],cwd=str(W),check=True,capture_output=True)
  subprocess.run(['scp','-q',str(tar),f'{h}:{S}/extras-repl-r{N}.tar'],check=True)
  base='--base /mpac/sdicks02/jobs-k4s/k4s-prep-20261011/base-s1 --inherited-pin /mpac/sdicks02/jobs-k4s/k4s-prep-20261011/base-s1/s1-runtime-pin-r2.json' if h=='127x04' else ''
  out=remote(h,STAGE.format(J=J,S=S,N=N,XSHA=sha(tar),BASE=base,PREREG=PREREG,PSHA=PREREG_SHA))
  rec['hosts'][h]=dict(job=J,extras_sha256=sha(tar),detach=out.strip().splitlines()[-1]);print(h,'staged + qualification launched',out.strip().splitlines()[-1])
 write(rdir(N)/'stage.json',rec)

def cmd_finalize(N):
 sg=need(N,'stage');inv=need(N,'inventory');ns=sg['namespace']
 if (rdir(N)/'finalize.json').exists():fail('finalize receipt exists')
 dsp=L/'dispatch'/f'replacement-r{N}.json'
 if sha(dsp)!=inv['dispatch']['sha256']:fail('dispatch changed since inventory')
 rec=dict(utc=utc(),round=N,namespace=ns,hosts={})
 for h in HOSTS:
  J=job(h,ns);SM=job(h,SMOKE_NS)
  remote(h,f'test -e {J}/QUALIFICATION-FINISHED && test -e {J}/TESTS-PASS && test -e {J}/QUALIFIED && test -e {J}/BELIEF-QUALIFIED')
  out=py(h,f'''import json,hashlib,sys
sys.path.insert(0,'{J}/repo/reports/explore/k4s-confirm')
q=json.load(open('{J}/qualification-{h}.json'))
assert q['verdict']=='PASS' and all(q['checks'].values()) and q['host']=='{h}' and q['job']=='{J}',('qualification',q['verdict'],q['host'],q['job'])
a=json.load(open('{J}/runtime-pin.json'));b=json.load(open('{SM}/runtime-pin.json'))
for k in ('files','native_source','inputs','inherited_runtime_pin_sha256','plan_sha256'):assert a[k]==b[k],k
assert q['runtime_pin_sha256']==hashlib.sha256(open('{J}/runtime-pin.json','rb').read()).hexdigest(),'qualification binds a different runtime pin'
from pathlib import Path
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for n,v in a['files'].items():assert h('{J}/repo/'+n)==v,n
for n,v in a['native_source'].items():assert h('{J}/native-source/'+n)==v,n
for n,v in a['inputs'].items():assert h('{J}/'+n)==v,n
print('OK',q['utc'],len(a['files']))''')
  remote(h,f'''test ! -e {J}/FROZEN-K4S.json
for f in FROZEN-K4S.json SMOKE-PASS smoke-admission.json;do cp -a {SM}/$f {J}/$f;done
test "$(sha256sum {J}/FROZEN-K4S.json | cut -d' ' -f1)" = {FROZEN_K4S}
test "$(sha256sum {J}/SMOKE-PASS | cut -d' ' -f1)" = {SMOKE[h]["SMOKE_PASS"]}
test "$(sha256sum {J}/smoke-admission.json | cut -d' ' -f1)" = {SMOKE[h]["admission"]}
test ! -e {J}/owned-supervisor-admission.json''')
  subprocess.run(['scp','-q',str(dsp),f'{h}:{J}/replacement-r{N}.json'],check=True)
  remote(h,f'test "$(sha256sum {J}/replacement-r{N}.json | cut -d" " -f1)" = {sha(dsp)}')
  if h=='127x03':
   remote(h,f'cd {J}/repo && K4S_JOB={J} nice -n 19 bash reports/explore/k4s-confirm/runtime.sh reports/explore/k4s-confirm/idle_services.py --job {J} >/dev/null')
   s=remote_json(h,f'{J}/idle-services.json')['services'][0]['service']
   if not (s['pid']==IDLE03['pid'] and s['start_ticks']==IDLE03['start_ticks'] and s['cmdline_sha256'].startswith(IDLE03['cmdline_prefix'])):fail(f'03 idle-service identity changed: {s}')
  rec['hosts'][h]=dict(job=J,qualification=out.strip(),carry_over=dict(frozen=FROZEN_K4S,**SMOKE[h]))
  print(h,'finalize checks OK',out.strip())
 a=read(L/'receipts'/'REPORTING-AUTHORIZATION.json')
 a['reporting_jobs']={h:job(h,ns) for h in HOSTS};a['phase']=f'replacement-r{N}'
 a['dispatch_path']=f'reports/explore/k4s-confirm/run-r1/dispatch/replacement-r{N}.json';a['dispatch_sha256']=sha(dsp)
 a['reporting_jobs_note']=dict(ruling='coordinator Option A (COORDINATOR.md afe83faa) + standing policy P2 (adc12f36)',original_dispatch_sha256='78335dc40094b404848088e55c287a536034e739c56789aa6f46af9a9b8af5b2',
                               ledger_sha256=inv['ledger_sha256'],inventory_receipt_sha256=sha(rdir(N)/'inventory.json'))
 ap=L/'receipts'/f'REPORTING-AUTHORIZATION-replacement-r{N}.json';write(ap,a)
 for h in HOSTS:
  J=job(h,ns);subprocess.run(['scp','-q',str(ap),f'{h}:{J}/REPORTING-AUTHORIZATION.json'],check=True)
  out=remote(h,f'cd {J}/repo && K4S_JOB={J} nice -n 19 bash reports/explore/k4s-confirm/runtime.sh -c "from barrier import reporting_release;from pathlib import Path;m=reporting_release(Path(\'{J}/repo\'),Path(\'{J}/FROZEN-K4S.json\'),Path(\'{J}/REPORTING-AUTHORIZATION.json\'));print(len(m[\'files\']))"')
  if out.strip()!='176':fail(f'{h} barrier output {out}')
  print(h,'barrier PASS')
 rec['authorization']=dict(path=str(ap),sha256=sha(ap));write(rdir(N)/'finalize.json',rec)

READ='''for f in /var/lib/ubuntu-release-upgrader/release-upgrade-available /var/lib/update-notifier/updates-available /var/lib/apt/lists; do echo "STAMP $f $(stat -c %Y $f)"; done
systemctl list-timers --all --no-pager | grep -E "apt-daily(-upgrade)?\\.timer" | sed 's/^/TIMER /' || true
ps -eo pid=,user=,args= | grep -E "apt-get|apt-check|/usr/lib/apt/|check-new-release|unattended-upgrade |update-notifier|apt.systemd.daily|release-upgrade-motd" | grep -v -e grep -e unattended-upgrade-shutdown | sed 's/^/PROC /' || true
echo NOW $(date +%s)'''
def state(h):
 out=remote(h,READ);s={};t=[];p=[];now=None
 for line in out.splitlines():
  if line.startswith('STAMP '):_,f,v=line.split();s[f]=int(v)
  elif line.startswith('TIMER '):t.append(line[6:])
  elif line.startswith('PROC '):p.append(line[5:])
  elif line.startswith('NOW '):now=int(line.split()[1])
 return s,t,p,now

def cmd_pretrigger(N,h):
 s,t,p,now=state(h)
 print(h,'before',{k:datetime.datetime.utcfromtimestamp(v).isoformat()+'Z' for k,v in s.items()},'procs',p)
 remote(h,'true')   # one ordinary login: pam_motd runs the update-motd hooks
 for _ in range(120):
  s2,_,p2,_=state(h)
  if not p2:break
  time.sleep(5)
 s2,_,p2,_=state(h)
 if p2:fail(f'{h} maintenance checks still running: {p2}')
 print(h,'after',{k:datetime.datetime.utcfromtimestamp(v).isoformat()+'Z' for k,v in s2.items()})
 write(rdir(N)/f'pretrigger-{h}.json',dict(utc=utc(),host=h,before=s,after=s2))

def cmd_prelaunch(N,builder,window_h,accept_motd):
 fz=need(N,'finalize');inv=need(N,'inventory')
 rec=dict(utc=utc(),round=N,builder=builder,escalation=inv['escalation'],cumulative_lost=inv['cumulative_lost'],max_k=inv['max_k'],hosts={})
 if inv['escalation']:fail('escalation gate set at inventory')
 if builder not in ('released','timeout','na'):fail('builder disposition required')
 for h in HOSTS:
  s,t,p,now=state(h)
  rel=s['/var/lib/ubuntu-release-upgrader/release-upgrade-available'];upd=s['/var/lib/update-notifier/updates-available'];lists=s['/var/lib/apt/lists']
  errs=[]
  if p:errs.append(f'maintenance running {p}')
  if now-rel>86400:errs.append('release-upgrade stamp stale: pretrigger')
  elif now-rel>86400-window_h*3600:
   msg=f'release-upgrade stamp expires inside the {window_h} h window (at {datetime.datetime.utcfromtimestamp(rel+86400).isoformat()}Z)'
   if accept_motd:rec.setdefault('accepted',[]).append(f'{h}: {msg}')
   else:errs.append(msg+': wait and pretrigger, or pass --accept-motd-expiry with a coordinator ruling')
  if lists>upd:errs.append('updates-available older than apt lists: pretrigger')
  rec['hosts'][h]=dict(stamps={k:datetime.datetime.utcfromtimestamp(v).isoformat()+'Z' for k,v in s.items()},timers=t,maintenance=p,errors=errs)
  print(h,'timers',t);print(h,'stamps',rec['hosts'][h]['stamps'],'errors',errs)
  if errs:fail(f'{h} prelaunch: {errs}')
 write(rdir(N)/'prelaunch.json',rec)

def cmd_launch(N):
 fz=need(N,'finalize');pl=need(N,'prelaunch');ns=fz['namespace']
 if (datetime.datetime.utcnow()-datetime.datetime.strptime(pl['utc'],'%Y-%m-%dT%H:%M:%SZ')).total_seconds()>900:fail('prelaunch receipt older than 15 min: re-run prelaunch')
 if (rdir(N)/'launch.json').exists():fail('launch receipt exists')
 rec=dict(utc=utc(),round=N,namespace=ns,hosts={})
 dsp=L/'dispatch'/f'replacement-r{N}.json'
 for h in HOSTS:
  J=job(h,ns)
  subprocess.run(['bash',str(L/'tools'/'launch_phase.sh'),h,f'replacement-r{N}',str(dsp),str(CORE[h])],env=dict(os.environ,K4S_JOBNAME=ns),check=True,timeout=900)
  ok=False
  for _ in range(60):
   try:
    lj=remote_json(h,f'{J}/replacement-r{N}/launch.json');ad=remote_json(h,f'{J}/host-admission-replacement.json')
    alive=remote(h,f'kill -0 {lj["supervisor_pid"]} && echo alive').strip()=='alive'
    ok=lj['host']==h and lj['dispatch_sha256']==sha(dsp) and ad['admitted'] is True and alive
   except SystemExit:ok=False
   if ok:break
   time.sleep(2)
  if not ok:fail(f'{h} supervisor did not confirm admission/launch: stop and reconcile the other host by owned STOP')
  rec['hosts'][h]=dict(launch=lj,admitted=True,copier_receipt=read(f'{J}/owned-copier-admission.json')['identity'])
  print(h,'LAUNCHED',lj['utc'],'supervisor',lj['supervisor_pid'])
 write(rdir(N)/'launch.json',rec)
 hist=history();hist.append(dict(namespace=ns,phase=f'replacement-r{N}',dispatch_file=f'replacement-r{N}.json',dispatch_sha256=sha(dsp),launched_utc=rec['utc']))
 write(L/'rounds'/'history.json',hist)

def main():
 a=argparse.ArgumentParser();a.add_argument('step');a.add_argument('N',type=int);a.add_argument('host',nargs='?');a.add_argument('--builder',default=None);a.add_argument('--window-hours',type=float,default=3.0);a.add_argument('--accept-motd-expiry',action='store_true');x=a.parse_args()
 if not 2<=x.N<=50:fail('round number')
 if x.step=='stop':cmd_stop(x.N)
 elif x.step=='drain':cmd_drain(x.N)
 elif x.step=='inventory':cmd_inventory(x.N)
 elif x.step=='stage':cmd_stage(x.N)
 elif x.step=='finalize':cmd_finalize(x.N)
 elif x.step=='pretrigger':
  if x.host not in HOSTS:fail('host')
  cmd_pretrigger(x.N,x.host)
 elif x.step=='prelaunch':cmd_prelaunch(x.N,x.builder,x.window_hours,x.accept_motd_expiry)
 elif x.step=='launch':cmd_launch(x.N)
 else:fail('unknown step')
if __name__=='__main__':main()
