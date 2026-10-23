import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
sys.dont_write_bytecode=True
import os,sys,json,time,hashlib,importlib.util,signal,calendar,errno,traceback,math
from pathlib import Path
from contextlib import contextmanager
BASE=Path('/mpac/sdicks02/jobs/clasher/M-physical-host14-r85-fix-20261023/r')
READY=Path('/mpac/sdicks02/repos/clasher-M-host14-ready-20261023')
SOURCE=Path('/mpac/sdicks02/repos/clasher-M-host14-source-20261023')
R37='/mpac/sdicks02/repos/clasher-pv1-lease-1316-995579193e/lease_supervisor.py'
R37_SHA='cf162c7a8d1beddd46bfed5b226ebe91ec4138af451f33a30ac950195bb61872'
AGG='cbb35f51d8aa9d4c4bd5d40894a79616d8a25d02fe9545d9637d8c96c12f3dd3'
ARCHIVE_SHA='73527481b5010e9a19a1090eee49710f45ae77d3f97a8dc9d1bcb61d40eaae13'
SCRIPT_SHA='2a1b18a645ae1aa1ad9dcd307f46f9d44b2ed09c68e29306c2e304d090884c0c'
ANCHORS={'M':'947af5cb5ac2b47fe666b329f21326e180b4b0d742bd97b1867603446cad79f4','S100':'74c7640776fd2c00fdd20c8c732dc07f4ed94c98964b5f816de4a60ae7cc332f'}
WATCH={'127x14':(1490887,17428347,'bfd7788a-d4d1-4687-9761-c462114e8849')}
MONITOR_IDENTITY_PROTOCOL='r40-trusted-lifetime-candidate-v1'
class ProbeLifetime:
 def __init__(self,m,tok,lease,allow_cache=True):
  self.m=m;self.tok=tok;self.lease=lease;self.allow_cache=allow_cache;self.fd=None;self.bound=None;self.revoked=False
 def close(self):
  if self.fd is not None:os.close(self.fd);self.fd=None
 def error(self,row,stage,ex):
  row.setdefault('identity_diagnostics',[]).append(dict(stage=stage,monotonic_ns=time.monotonic_ns(),type=type(ex).__name__,errno=getattr(ex,'errno',None),filename=getattr(ex,'filename',None),error=repr(ex),traceback=traceback.format_exc()))
 def stat(self,pid,row,label):
  d={};row[label]=d
  for name in ('stat','uid','boot'):
   try:
    if name=='stat':
     st=self.m.proc_stat(pid);assert st is not None,'process missing'
     d.update(start=st[4],state=st[0],sid=st[2])
    elif name=='uid':d['uid']=os.stat('/proc/%d'%pid).st_uid
    else:d['boot']=self.m.boot_id()
   except Exception as ex:self.error(row,label+'.'+name,ex)
  d['monotonic_ns']=time.monotonic_ns();return d
 def key(self,d):return tuple(d[k] for k in ('start','sid','uid','boot'))
 def fdcheck(self,pid,row,label):
  data=Path('/proc/self/fdinfo/%d'%self.fd).read_text()
  row[label]=dict(raw=data,monotonic_ns=time.monotonic_ns())
  values=[int(l.split()[1]) for l in data.splitlines() if l.startswith('Pid:')]
  row[label]['pid_values']=values
  assert values==[pid],'pidfd missing, reaped or wrong PID'
 def attribute(self,pid,identity,row):
  row.update(attributed=False,source=None,probe_token=None,lease_token=None,identity_protocol=MONITOR_IDENTITY_PROTOCOL)
  before=self.stat(pid,row,'stat_before');row.update(before)
  expected=identity is not None and pid==identity['pid'];opened=False;env_error=None;problem=None
  try:
   assert not row.get('identity_diagnostics'),'incomplete initial stat'
   if expected:
    assert not self.revoked,'lifetime binding revoked'
    assert identity['probe_token']==self.tok.decode().split('=',1)[1],'published token mismatch'
    key=(identity['start'],identity['sid'],os.getuid(),identity['boot'])
    assert self.key(before)==key,'expected identity mismatch'
    if self.allow_cache:
     if self.fd is None:self.fd=self.m._pidfd_open(pid);opened=True
     self.fdcheck(pid,row,'pidfd_before')
     pinned=self.stat(pid,row,'stat_pinned')
     assert self.key(pinned)==key and not row.get('identity_diagnostics'),'identity changed at pidfd open'
   env=b'';row['environ_started_monotonic_ns']=time.monotonic_ns()
   try:
    if before['uid']==os.getuid():env=b'\0'+Path('/proc/%d/environ'%pid).read_bytes()+b'\0'
    row.update(probe_token=b'\0'+self.tok+b'\0' in env,lease_token=b'\0'+self.lease+b'\0' in env)
   except OSError as ex:
    env_error=ex;self.error(row,'environ',ex)
   finally:row['environ_finished_monotonic_ns']=time.monotonic_ns()
  except Exception as ex:problem=ex;self.error(row,'binding',ex)
  after=self.stat(pid,row,'stat_after')
  try:
   assert problem is None,'binding failed'
   assert self.key(before)==self.key(after),'identity changed during attribution'
   assert all(d['stage']=='environ' for d in row.get('identity_diagnostics',[])),'kernel identity read failed'
   if expected:
    assert self.key(after)==key,'expected identity changed'
    if self.allow_cache:self.fdcheck(pid,row,'pidfd_after')
   if env_error is not None:
    assert expected and self.allow_cache and self.bound is not None and not opened,'no initial full binding'
    assert env_error.errno in (errno.EACCES,errno.EPERM),'environment error not eligible'
    assert self.key(after)==self.bound['key'],'cached epoch mismatch'
    row.update(source='trusted-lifetime-plus-fresh-stat',cached_identity=self.bound,probe_token=None,lease_token=None)
   else:
    if expected:
     assert row['probe_token'] is True and row['lease_token'] is True,'readable token mismatch'
     if self.allow_cache and self.bound is None:self.bound=dict(pid=pid,key=key,probe_token=True,lease_token=True,token_provenance='successful-fresh-read',bound_monotonic_ns=time.monotonic_ns())
    row['source']='fresh-environ-plus-stat'
   row['attributed']=True
  except Exception as ex:
   self.error(row,'acceptance',ex)
   if expected:self.revoked=True;self.close()
   raise
class Deadline(BaseException):pass
class Budget(BaseException):pass
LIMITS=[];FIRED=[]
def _arm():
 left=min(LIMITS)-time.monotonic()
 if left>0:signal.setitimer(signal.ITIMER_REAL,left);return
 signal.setitimer(signal.ITIMER_REAL,0)
 if LIMITS[0]<=time.monotonic() and not FIRED:FIRED.append(1);raise Deadline('finite parent-owned deadline')
 if left<=0 and min(LIMITS)<LIMITS[0]:raise Budget('bounded work budget')
def _fire(*_):
 if time.monotonic()>=LIMITS[0]:
  if not FIRED:FIRED.append(1);raise Deadline('finite parent-owned deadline')
  return
 if time.monotonic()>=min(LIMITS):raise Budget('bounded work budget')
 _arm()
def deadline(seconds):
 """Install or replace this process's finite deadline (for example a separately bounded cleanup phase)."""
 signal.signal(signal.SIGALRM,_fire);LIMITS[:]=[time.monotonic()+seconds];FIRED[:]=[];_arm()
@contextmanager
def bounded(seconds):
 LIMITS.append(time.monotonic()+seconds);_arm()
 try:yield
 finally:
  LIMITS.pop();_arm()
def remaining():return LIMITS[0]-time.monotonic()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(p,obj):
 p=Path(p);tmp=p.with_name('.%s.%d.%s.tmp'%(p.name,os.getpid(),os.urandom(8).hex()))
 with tmp.open('x') as f:json.dump(obj,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 try:os.link(str(tmp),str(p))
 finally:os.unlink(str(tmp))
 d=os.open(str(p.parent),os.O_RDONLY)
 try:os.fsync(d)
 finally:os.close(d)
def utc():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def load_r37(context=None):
 if context is None:
  g=(Path(__file__).resolve().parent/'gate.py').read_bytes();assert hashlib.sha256(g).hexdigest()=='03bc6ded28c261f7b3499544a351627c2810732f5c6582b5baae099f290e5022'
  scope={};exec(compile(g,'gate.py','exec'),scope);scope['R64_DISK']('common.py',__file__)
 else:
  import base64
  f=base64.b64decode(context['freeze']);manifest=base64.b64decode(context['manifest']);r=context['review'];d=json.loads(f)
  assert r['status']=='GO' and r['review']=='R87' and r['freeze_sha256']==hashlib.sha256(f).hexdigest()
  assert d['manifest_sha256']==hashlib.sha256(manifest).hexdigest() and d['authorization_sha256']==r['authorization_sha256']=='32269e4e1519451f2300ac5e53cb2bf03c6b0faf246066f39c75ad53b57d5cf1'
  assert r['host']=='127x14' and r['maximum_new_M_measurements']==1
 raw=Path(R37).read_bytes();assert hashlib.sha256(raw).hexdigest()==R37_SHA
 import types
 m=types.ModuleType('r37');m.__file__=R37;exec(compile(raw,R37,'exec'),m.__dict__);assert m.host()=='127x14';m.require_pidfd();return m
def state(m):
 s=m.State.__new__(m.State);s.h=m.host();s.dir=m.STATE_ROOT+'/'+s.h;s.jobs=s.dir+'/jobs';s.logs=s.dir+'/logs';s.recovery=s.dir+'/recovery';s.release=s.dir+'/RELEASE';s.halt=s.dir+'/HALT';s.request_issues={};return s
def proc_uid(pid):
 line=next(l for l in Path('/proc/%d/status'%pid).read_text().splitlines() if l.startswith('Uid:'))
 return int(line.split()[1])
def wrapper_pss(m,pid):
 try:
  with open('/proc/%d/smaps_rollup'%pid) as f:pss=next(int(l.split()[1])*1024 for l in f if l.startswith('Pss:'));how='pss'
 except PermissionError:
  pss=next(int(l.split()[1])*1024 for l in Path('/proc/%d/status'%pid).read_text().splitlines() if l.startswith('VmRSS:'));how='rss'
 assert pss>0,'wrapper %d PSS unreadable'%pid
 return pss,how
def wrapper_chain(m):
 uid=os.getuid();boot=m.boot_id();pid=os.getpid();out=[]
 while proc_uid(pid)==uid:
  st=m.proc_stat(pid);assert st is not None and st[0] not in 'ZX','wrapper %d unreadable'%pid
  cmd=Path('/proc/%d/cmdline'%pid).read_bytes();assert cmd and m.proc_stat(pid)[4]==st[4],'wrapper %d changed'%pid
  out.append(dict(pid=pid,start=st[4],boot=boot,sid=st[2],uid=uid,nice=st[3],cmd=cmd.split(b'\0')[0].decode(errors='replace')))
  assert len(out)<=4 and st[1]>1,'launcher chain reached init without uid change'
  pid=st[1]
 assert len(out)>=2 and out[-1]['cmd'].startswith('sshd'),'top same-uid launcher is not a dedicated sshd session %r'%out
 return out
def charge_wrappers(m,procs,jobs,sample):
 raw=os.environ.get('R40_WRAPPERS');assert raw,'wrapper identities missing'
 chain=json.loads(raw);assert len(chain)>=2 and chain[-1]['cmd'].startswith('sshd'),'wrapper identities incomplete'
 counted={p for p,x in procs.items() if m.is_clasher(x)}|{p for v in jobs.values() for p in v}
 rows=[];extra=0;charged=0
 for w in chain:
  st=m.proc_stat(w['pid'])
  assert st is not None and st[0] not in 'ZX' and st[4]==w['start'] and st[2]==w['sid'],'wrapper %d gone or reused'%w['pid']
  assert m.boot_id()==w['boot'] and proc_uid(w['pid'])==w['uid']==os.getuid(),'wrapper %d identity changed'%w['pid']
  assert w['cmd'].startswith('sshd') or st[3]>=10,'compute wrapper %d nice below 10'%w['pid']
  pss,how=wrapper_pss(m,w['pid']);assert m.proc_stat(w['pid'])[4]==w['start'],'wrapper %d reused during read'%w['pid']
  r37=w['pid'] in counted and (w['pid'] not in procs or procs[w['pid']]['start']==w['start'])
  if not r37:extra+=1;charged+=pss
  rows.append(dict(w,pss=pss,pss_source=how,counted_by_r37=r37))
 return dict(sample,procs=sample['procs']+extra,pss=sample['pss']+charged,r37_procs=sample['procs'],r37_pss=sample['pss'],wrappers=rows)
def gpu_contract(record):
 value=record['gpu_gb']
 assert type(value) in (int,float) and math.isfinite(value) and value>=0,'invalid or ambiguous GPU reservation contract'
 return value
def admission(m,workers=0,pss_gb=0):
 s=state(m);pid,start,boot=WATCH[m.host()]
 assert m.boot_id()==boot and m.alive(pid,start)
 w=json.loads(Path(s.dir+'/supervisor.json').read_bytes());assert (w['pid'],w['start'],w['boot'])==(pid,start,boot)
 cmd=Path('/proc/%d/cmdline'%pid).read_bytes();assert R37.encode() in cmd and b'supervise' in cmd
 assert s.supervisor_live() and not Path(s.halt).exists() and not Path(s.release).exists()
 lease,deadline,cap,psscap=m.load_lease(m.LEASE_DIR+'/'+m.host()+'.json',m.host());assert m.lease_ending(lease) is None
 assert deadline-time.time()>900
 assert cap<=32 and psscap<=32 and deadline<=m.parse_utc('2026-10-25T07:53:00Z')
 recs=s.records();assert not any(r['state'] in ('intent','uncertain','stopping') for r in recs.values())
 procs=m.job_scan(m.host());jobs=m.job_discover(m.host(),recs,procs,m.boot_id())
 assert not any(v and gpu_contract(recs[n])>0 and n!='M-host14-measure-20261023-once' for n,v in jobs.items()),'competing GPU job: defer without displacement'
 sample=charge_wrappers(m,procs,jobs,m.job_sample(m.host(),recs,procs,jobs))
 assert sample['mem']>=32*m.GIB and sample['mem']-pss_gb*m.GIB>28*m.GIB and sample['load']<=90
 assert os.sched_getaffinity(0)<=set(range(32)),'own CPU affinity outside 0-31'
 assert not any(m.affinity_issue(m.host(),v) for v in jobs.values()),'job affinity violation'
 assert not m.affinity_issue(m.host(),{p:x for p,x in procs.items() if m.is_clasher(x)}),'all-owner affinity violation'
 assert sample['procs']+workers<=cap and sample['pss']+pss_gb*m.GIB<=psscap*m.GIB
 assert os.getpriority(os.PRIO_PROCESS,0)>=10
 for p in procs.values():
  if m.is_clasher(p):assert p['nice']>=10
 return dict(utc=utc(),watcher=w,lease=lease,deadline=deadline,cap=cap,pss_cap=psscap,sample=sample,jobs={n:[[p,x['start']] for p,x in v.items()] for n,v in jobs.items()})
def lease_check():
 assert os.environ.get('CLASHER_LEASE_JOB') and os.environ.get('CLASHER_LEASE_STOP_FILE') and os.environ.get('CLASHER_LEASE_STOP_BY_UTC')
 assert not Path(os.environ['CLASHER_LEASE_STOP_FILE']).exists()
 assert time.time()<calendar.timegm(time.strptime(os.environ['CLASHER_LEASE_STOP_BY_UTC'],'%Y-%m-%dT%H:%M:%SZ'))-120
def no_cache(root):
 root=Path(root)
 assert root.is_dir(),'missing source/runtime root'
 for p in root.rglob('*'):
  assert p.name!='__pycache__' and p.suffix not in ('.pyc','.pyo'),'unreviewed bytecode/cache '+str(p)
  assert not p.is_symlink(),'symlink source/runtime '+str(p)
def verify_ready(expected=None):
 raw=(READY/'cpu-stage-inventory.json').read_bytes()
 if expected is None:expected=json.loads((BASE/'ready-plan.json').read_bytes())
 assert hashlib.sha256(raw).hexdigest()==expected['inventory_sha256'],'readiness inventory mismatch'
 plan=json.loads(raw)
 assert plan['host']=='127x14' and plan['ready']==str(READY)
 no_cache(READY)
 for rel,row in plan['ready_files'].items():
  p=READY/rel;assert p.is_file() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'immutable environment/input mismatch '+rel
 assert {str(p.relative_to(READY)) for p in READY.rglob('*') if p.is_file()}==set(plan['ready_files'])|{'cpu-stage-inventory.json'},'runtime inventory mismatch'
 return dict(files=len(plan['ready_files']),inventory_sha256=sha(READY/'cpu-stage-inventory.json'))
def verify_inputs(size):
 manifest=json.loads((BASE/'inputs.json').read_bytes());assert sha(BASE/'archive.tar')==ARCHIVE_SHA
 no_cache(SOURCE);verify_ready()
 for rel,h in manifest['source_files'].items():assert sha(SOURCE/rel)==h,rel
 actual={str(p.relative_to(SOURCE)) for p in SOURCE.rglob('*') if p.is_file()}
 assert actual==set(manifest['source_files'])
 digest=hashlib.sha256()
 for p in sorted((SOURCE/'bot/pretrain_v1').rglob('*.py')):digest.update(str(p.relative_to(SOURCE)).encode()+b'\0'+p.read_bytes())
 assert digest.hexdigest()==AGG and sha(SOURCE/'bot/pretrain_v1/checks/qualify_maxshape.py')==SCRIPT_SHA
 assert sha(READY/'dependencies/relocated-references.json')=='b01eefc9c93099fd1ccb55fc7efde0b01778be68d7b802faf1c1363ee0e844bd'
 refs=json.loads((READY/'dependencies/relocated-references.json').read_bytes())['files'];assert len(refs)==31
 for row in refs:
  rel=Path(row['relocated_path']).relative_to('/mpac/sdicks02/repos/clasher-pv1-ready-20261022');assert sha(READY/rel)==row['sha256']
 for name,h in manifest['helper_files'].items():assert sha(BASE/name)==h,name
 anchor=BASE/'anchors'/size/'anchor.pt';selection=anchor.with_name('selection.json')
 assert sha(anchor)==ANCHORS[size] and sha(selection)==manifest['selections'][size]
 r=json.loads(selection.read_bytes());assert r['admitted'] is True and r['smoke'] is False and r['sha256']==ANCHORS[size] and r['file']=='anchor.pt'
 return dict(commit='4e8f740beab33557f1f5ceb0bd2c5b4678d8e3bb',aggregate_sha256=AGG,archive_sha256=ARCHIVE_SHA,script_sha256=SCRIPT_SHA,anchor_sha256=ANCHORS[size],selection_sha256=sha(selection),source_files=len(actual),helper_files=manifest['helper_files'],dependencies_verified=len(refs))
