"""Explicit single-host install, CPU qualification or reviewed training admission."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

REPO=Path(__file__).resolve().parents[4]
BASE=Path('/mpac/sdicks02/jobs/clasher/supplemental-bc-20261022')
STAGE=BASE/'staging'
ADAPTER='/mpac/sdicks02/repos/clasher-bc-supplemental-stop-20261022'
ROOT='/mpac/sdicks02/repos/clasher-bc-supplemental-40ea-20261022'
SEEDS={'127x09':2026102004,'127x12':2026102005,'127x17':2026102006,'127x13':2026102007,'127x14':2026102008,'127x15':2026102009,'127x16':2026102010}

def sha(raw):return hashlib.sha256(raw).hexdigest()

INSTALL=r'''
import base64,json,os,pathlib,hashlib,importlib.util
s=SUPERVISOR
spec=importlib.util.spec_from_file_location('m',s);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
assert os.environ['CUDA_VISIBLE_DEVICES']=='' and os.environ['CLASHER_LEASE_JOB']
def check():assert not os.path.exists(os.environ['CLASHER_LEASE_STOP_FILE'])
root=pathlib.Path(ROOT);dest=pathlib.Path(ADAPTER);base=pathlib.Path(BASE)
M.make_directories(str(dest));M.make_directories(str(base))
for n,ref in json.loads((base/'staging/source-map.json').read_bytes()).items():
 check();data=(root/'source'/n).read_bytes();assert hashlib.sha256(data).hexdigest()==ref['sha256']
 if n in OVERRIDES:data=base64.b64decode(OVERRIDES[n])
 target=dest/n;M.make_directories(str(target.parent))
 if target.exists():
  with M.safe_open(str(target),'rb') as f:assert f.read()==data,'existing adapter differs'
 else:
  with M.safe_open(str(target),'w') as f:f.buffer.write(data);f.flush();os.fsync(f.fileno())
for n,encoded in OVERRIDES.items():
 check();target=dest/n;data=base64.b64decode(encoded);M.make_directories(str(target.parent))
 if target.exists():
  with M.safe_open(str(target),'rb') as f:assert f.read()==data
 else:
  with M.safe_open(str(target),'w') as f:f.buffer.write(data);f.flush();os.fsync(f.fileno())
for n in ['tmp','cache','cache/torch']:M.make_directories(str(base/n))
config=CONFIG;path=pathlib.Path(config['config_path']);raw=(json.dumps(config,sort_keys=True,indent=2)+'\n').encode()
if path.exists():
 with M.safe_open(str(path),'rb') as f:assert f.read()==raw
else:
 with M.safe_open(str(path),'w') as f:f.buffer.write(raw);f.flush();os.fsync(f.fileno())
M.write_atomic(str(base/'adapter-installed.json'),{'status':'installed-no-training','config_sha256':hashlib.sha256(raw).hexdigest(),'adapter_files':config['adapter_files'],'pid':os.getpid(),'start':M.proc_stat(os.getpid())[4],'boot':M.boot_id()})
'''

REMOTE=r'''
import os,pathlib,json,hashlib,importlib.util,argparse,subprocess,base64
h=os.uname().nodename.split('.')[0];assert h==HOST
old=h in ('127x09','127x12','127x17')
s='/mpac/sdicks02/repos/'+('clasher-pv1-lease-r37-7851936824' if old else 'clasher-pv1-lease-1316-995579193e')+'/lease_supervisor.py'
pin='0613d6db62371eb197bb5d41cbf342b57f1998ddeb91e04c7c5ab2be36ac0ffc' if old else 'cf162c7a8d1beddd46bfed5b226ebe91ec4138af451f33a30ac950195bb61872'
assert hashlib.sha256(pathlib.Path(s).read_bytes()).hexdigest()==pin
sp=importlib.util.spec_from_file_location('m',s);M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
st=M.State(M.STATE_ROOT,h);assert st.supervisor_live()
with M.safe_open(st.dir+'/supervisor.json','r') as f:w=json.load(f)
assert M.proc_stat(w['pid'])[4]==w['start'] and w['boot']==M.boot_id()
assert s.encode() in pathlib.Path('/proc/'+str(w['pid'])+'/cmdline').read_bytes()
assert not os.path.exists(st.halt) and not os.path.exists(st.release)
recs=st.records();assert all(r['state']=='gone' for r in recs.values()),'existing admitted work'
scan=M.job_scan(h) if hasattr(M,'job_scan') else M.scan()
jobs=M.job_discover(h,recs,scan,M.boot_id()) if hasattr(M,'job_discover') else M.discover(recs,scan,M.boot_id())
assert not any(jobs.values()),'owned work still alive'
sample=M.job_sample(h,recs,scan,jobs) if hasattr(M,'job_sample') else M.sample(recs,scan,jobs)
lease,deadline,cap,pss=M.load_lease(M.LEASE_DIR+'/'+h+'.json',h)
assert M.lease_ending(lease) is None and lease['status']=='active'
assert deadline<=M.parse_utc('2026-10-25T07:53:00Z')
config=CONFIG
assert sample['load']<=90 and sample['mem']-config['pss_gib']*M.GIB>28*M.GIB
assert sample['pss']+config['pss_gib']*M.GIB<=min(pss,32 if h in ('127x13','127x14','127x15','127x16') else 64)*M.GIB
assert sample['procs']+8<=cap
assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getaffinity(0)<=set(range(32))
gpu=M.gpu_free_gb();assert gpu is not None and gpu>=8
if PHASE=='install':
 cmd=['/bin/python3','-B','-c',INSTALL_CODE];workers=4;pssgb=2;gpugb=0;cwd=str(pathlib.Path(ROOT)/'source')
else:
 assert pathlib.Path(config['config_path']).read_text()==json.dumps(config,sort_keys=True,indent=2)+'\n'
 env=dict(PYTHONHOME=str(pathlib.Path(ROOT)/'env/python'),PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=ADAPTER,TMPDIR=str(pathlib.Path(BASE)/'tmp'),XDG_CACHE_HOME=str(pathlib.Path(BASE)/'cache'),TORCH_HOME=str(pathlib.Path(BASE)/'cache/torch'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
 os.environ.update(env)
 cmd=[config['python'],'-B','-m','bot.pretrain_v1.supplemental_job','probe' if PHASE=='probe' else 'train',config['config_path']]
 workers=8;pssgb=config['pss_gib'];gpugb=0;cwd=ADAPTER
 if PHASE=='train':
  assert not pathlib.Path(config['out']).exists(),'seed already started'
  raw=base64.b64decode(REVIEW_CONTENT);assert hashlib.sha256(raw).hexdigest()==REVIEW_SHA
  assert REVIEW_PATH.startswith(BASE+'/')
  M.make_directories(str(pathlib.Path(REVIEW_PATH).parent))
  if pathlib.Path(REVIEW_PATH).exists():
   with M.safe_open(REVIEW_PATH,'rb') as f:assert f.read()==raw
  else:
   with M.safe_open(REVIEW_PATH,'w') as f:f.buffer.write(raw);f.flush();os.fsync(f.fileno())
  report=raw.decode();assert REVIEW_SHA==hashlib.sha256(report.encode()).hexdigest() and 'Verdict: GO' in report
  assert all(digest in report for digest in config['adapter_files'].values())
  assert CONFIG_SHA in report
  q=subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10,check=True)
  assert not q.stdout.strip(),'GPU compute process present'
  total=float(subprocess.run(['nvidia-smi','--query-gpu=memory.total','--format=csv,noheader,nounits'],stdout=subprocess.PIPE,timeout=10,check=True).stdout.decode().strip())/1024
  assert abs(total-config['gpu_total_gib'])<.01
  gpugb=config['allocator_gib']+1.5
  assert gpugb<=gpu-8 and config['allocator_gib']<=39.03515625
  measured=json.loads((pathlib.Path(BASE)/'memory-probe.json').read_bytes())
  assert measured['completed'] and measured['peak_pss_gib']+2<=pssgb
name='supplemental-bc-'+PHASE+'-'+str(config['seed'])
a=argparse.Namespace(name=name,workers=workers,pss_gb=pssgb,gpu_gb=gpugb,grace=1500,cwd=cwd,cmd=cmd)
print(json.dumps({'phase':PHASE,'host':h,'source_sha256':pin,'watcher':w,'sample':sample,'gpu_free_gib':gpu,'config':config}),flush=True)
M.admit(a,st,M.LEASE_DIR+'/'+h+'.json')
'''

def configuration(host,overrides):
    pins=json.loads((STAGE/'pins.json').read_bytes())
    return dict(host=host,seed=SEEDS[host],store=str(STAGE/'store/f-ce6e509ee43a-b-1005dbb4'),
                out=str(BASE/('M-s'+str(SEEDS[host]))),python=ROOT+'/env/python/bin/python3.12',
                config_path=str(BASE/'launch-config.json'),pss_gib=30.5,allocator_gib=37.5,gpu_total_gib=47.98828125,
                env_files=pins['maps']['env']['files'],map_hashes={n:pins['maps'][n]['sha256'] for n in ['source','store','env']},
                adapter_files={n:sha(raw) for n,raw in overrides.items()},grace_seconds=1500,
                original_commit='40ea0b503d94daba5486cb151f759b233664ba43',automatic_resume=False)


def main():
    host,phase=sys.argv[1:3]
    assert host in SEEDS and phase in ('plan','install','probe','train')
    if host in ('127x09','127x12') and phase != 'plan':
        handoff=json.loads((BASE/'r40-ssh-handoff.json').read_bytes())
        assert handoff[host]['ssh_released'] and handoff[host]['r40_complete']
    overrides={n:(REPO/n).read_bytes() for n in ['bot/pretrain_v1/train_bc.py','bot/pretrain_v1/lease_stop.py','bot/pretrain_v1/supplemental_job.py']}
    config=configuration(host,overrides)
    configraw=(json.dumps(config,sort_keys=True,indent=2)+'\n').encode()
    local=BASE/(host+'-launch-config.json');local.write_bytes(configraw)
    if phase=='plan':return
    # Stable immutable combined review gate is supplied only after independent GO.
    gate=json.loads((BASE/'combined-review-GO.json').read_bytes()) if phase=='train' else dict(path='',sha256='')
    installer='SUPERVISOR='+repr('/mpac/sdicks02/repos/'+('clasher-pv1-lease-r37-7851936824' if host in ('127x09','127x12','127x17') else 'clasher-pv1-lease-1316-995579193e')+'/lease_supervisor.py')+'\nROOT='+repr(ROOT)+'\nADAPTER='+repr(ADAPTER)+'\nBASE='+repr(str(BASE))+'\nCONFIG='+repr(config)+'\nOVERRIDES='+repr({n:base64.b64encode(raw).decode() for n,raw in overrides.items()})+'\n'+INSTALL
    code='HOST='+repr(host)+'\nPHASE='+repr(phase)+'\nCONFIG='+repr(config)+'\nCONFIG_SHA='+repr(sha(configraw))+'\nROOT='+repr(ROOT)+'\nADAPTER='+repr(ADAPTER)+'\nBASE='+repr(str(BASE))+'\nINSTALL_CODE='+repr(installer)+'\nREVIEW_PATH='+repr(gate['path'])+'\nREVIEW_CONTENT='+repr(base64.b64encode(Path(gate['path']).read_bytes()).decode() if phase=='train' else '')+'\nREVIEW_SHA='+repr(gate['sha256'])+'\n'+REMOTE
    cmd=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','ConnectionAttempts=1','-o','ControlMaster=no','-o','ControlPath=none','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no',host,'taskset -c 0-31 nice -n 15 /bin/python3 -B -']
    result=subprocess.run(cmd,input=code.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=55)
    (BASE/(host+'-'+phase+'.stdout')).write_bytes(result.stdout)
    (BASE/(host+'-'+phase+'.stderr')).write_bytes(result.stderr)
    print(result.stdout.decode(),result.stderr.decode(),flush=True)
    raise SystemExit(result.returncode)

if __name__=='__main__':main()
