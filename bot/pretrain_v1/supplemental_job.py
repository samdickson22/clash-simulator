"""One supplemental seed or a CPU memory qualification; no retries or resume."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
import resource
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

BASE = Path('/mpac/sdicks02/jobs/clasher/supplemental-bc-20261022')
STAGING = BASE/'staging'
ROOT = Path('/mpac/sdicks02/repos/clasher-bc-supplemental-40ea-20261022')
ADAPTER = Path('/mpac/sdicks02/repos/clasher-bc-supplemental-stop-20261022')
SEEDS = {'127x09':2026102004,'127x12':2026102005,'127x17':2026102006,
         '127x13':2026102007,'127x14':2026102008,'127x15':2026102009,'127x16':2026102010}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4<<20), b''):
            h.update(block)
    return h.hexdigest()


def publish(path, value):
    from bot.pretrain_v1.lease_stop import atomic_write
    atomic_write(path, lambda stream: stream.write((json.dumps(value, indent=2)+'\n').encode()))


def supervisor(host):
    name = 'clasher-pv1-lease-r37-7851936824' if host in ('127x09','127x12','127x17') else 'clasher-pv1-lease-1316-995579193e'
    pin = '0613d6db62371eb197bb5d41cbf342b57f1998ddeb91e04c7c5ab2be36ac0ffc' if host in ('127x09','127x12','127x17') else 'cf162c7a8d1beddd46bfed5b226ebe91ec4138af451f33a30ac950195bb61872'
    path = Path('/mpac/sdicks02/repos')/name/'lease_supervisor.py'
    assert sha(path) == pin
    spec = importlib.util.spec_from_file_location('reviewed_supervisor', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(config,check):
    for name, digest in config['adapter_files'].items():
        assert sha(ADAPTER/name) == digest, name
    for category, target in [('source', ROOT/'source'), ('store', Path(config['store'])), ('env', ROOT/'env')]:
        mapping_path = STAGING/(category+'-map.json')
        assert sha(mapping_path) == config['map_hashes'][category]
        mapping = json.loads(mapping_path.read_bytes())
        assert len(mapping) == {'source':73,'store':6241,'env':config['env_files']}[category]
        for name, ref in mapping.items():
            check()
            pure = Path(name)
            assert not pure.is_absolute() and '..' not in pure.parts
            path = target/name
            assert not path.is_symlink() and path.stat().st_size == ref['bytes'] and sha(path) == ref['sha256'], name
            if category == 'source' and name not in config['adapter_files']:
                assert sha(ADAPTER/name) == ref['sha256'], name
    assert sha(Path(config['store'])/'MANIFEST.jsonl') == '1aa01c37fdd18ac7c23a5e9cf7b875b674d5021309ab4b4b79603fd29661b264'
    assert sha(STAGING/'STORE-READY.json') == '56dd0c46b340e672b5749952bead6a9e773f9924cd63f3f9285ed8e422eb1035'
    ready = json.loads((STAGING/'ready.json').read_bytes())
    assert ready['status'] == 'ready-cpu-staging-only' and ready['training_started'] is False


def environment(config):
    env = dict(os.environ, PYTHONHOME=str(ROOT/'env/python'), PYTHONNOUSERSITE='1',
               PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='3', OPENBLAS_NUM_THREADS='1',
               MKL_NUM_THREADS='3', NUMEXPR_NUM_THREADS='1', TMPDIR=str(BASE/'tmp'),
               XDG_CACHE_HOME=str(BASE/'cache'), TORCH_HOME=str(BASE/'cache/torch'),
               CUDA_CACHE_PATH=str(BASE/'cache/cuda'), TRITON_CACHE_DIR=str(BASE/'cache/triton'),
               TORCHINDUCTOR_CACHE_DIR=str(BASE/'cache/inductor'),
               PV1_HOST_MIN_AVAILABLE_GIB='28', PV1_HOST_MAX_LOAD='90')
    env['PYTHONPATH'] = str(ADAPTER)
    env['PV1_GPU_FRACTION'] = str(config['allocator_gib']/config['gpu_total_gib'])
    return env


def memory_probe(config):
    import resource
    import numpy as np
    import torch
    from bot.pretrain_v1.train_bc import Store, game_sampler
    assert os.environ['CUDA_VISIBLE_DEVICES'] == ''
    assert torch.__version__ == '2.7.1+cu118' and np.__version__ == '2.3.5'
    torch.set_num_threads(3)
    store = Store(config['store'])
    assert store.n == 23498034
    tr = np.nonzero(store.split == 0)[0]
    dv = np.nonzero(store.split == 1)[0]
    dv_eval = np.sort(np.random.default_rng(0).choice(dv, min(len(dv),400000), replace=False))
    p, sampler = game_sampler(store,tr,.5,5.)
    iw = ((1/len(tr))/p).astype(np.float32)
    spe = max(1,len(tr)//512)
    draws = np.random.default_rng(config['seed']).choice(len(tr),spe*512,p=p)
    batches = [tr[draws[i*512:(i+1)*512]] for i in range(spe)]
    iws = [iw[draws[i*512:(i+1)*512]] for i in range(spe)]
    prepared = [store.batch(batches[i]) for i in range(min(6,spe))]
    value = dict(status='cpu-memory-qualified', rows=store.n, train_rows=len(tr),dev_rows=len(dv),
                 max_rss_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,
                 pid=os.getpid(),seed=config['seed'], sampler=sampler,
                 projected_training_overhead_gib=2.0, completed=True)
    M = supervisor(config['host'])
    value.update(host=config['host'],config_sha256=sha(config['config_path']),
                 identity=dict(pid=os.getpid(),start=M.proc_stat(os.getpid())[4],boot=M.boot_id()),
                 written_at=time.time())
    publish(BASE/'memory-probe-child.json',value)
    print(json.dumps(value),flush=True)
    return value


def validate_memory(receipt,config,boot):
    assert receipt['status']=='cpu-memory-qualified' and receipt['completed'] is True
    assert receipt['host']==config['host'] and receipt['seed']==config['seed']
    assert receipt['config_sha256']==sha(config['config_path'])
    identity=receipt['identity']
    assert identity['boot']==boot and type(identity['pid']) is int and identity['pid']>0
    assert type(identity['start']) is int and identity['start']>0
    assert 0<=time.time()-receipt['written_at']<=3600
    peak=receipt['qualified_peak_gib']
    assert type(peak) in (int,float) and math.isfinite(peak) and peak>0
    assert peak>=receipt['peak_pss_gib'] and peak>=receipt['child_peak_rss_gib']
    assert peak+2<=config['pss_gib'], 'insufficient measured memory margin'


SAMPLE_CODE = """
import sys,json,hashlib,importlib.util
path,pin,host=sys.argv[1:]
with open(path,'rb') as stream:assert hashlib.sha256(stream.read()).hexdigest()==pin
spec=importlib.util.spec_from_file_location('m',path);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
snapshot=M.job_scan(host) if hasattr(M,'job_scan') else M.scan()
state=M.State(M.STATE_ROOT,host);records=state.records()
jobs=M.job_discover(host,records,snapshot,M.boot_id()) if hasattr(M,'job_discover') else M.discover(records,snapshot,M.boot_id())
sample=M.job_sample(host,records,snapshot,jobs) if hasattr(M,'job_sample') else M.sample(records,snapshot,jobs)
actual=M.job_sample(host,{},snapshot,{}) if hasattr(M,'job_sample') else M.sample({},snapshot,{})
print(json.dumps(dict(sample=sample,actual=actual,gpu=M.gpu_free_gb())),flush=True)
"""


def sample_resources(M,host,deadline):
    env=dict(os.environ)
    env.pop('PYTHONHOME',None)
    args=['/bin/python3','-B','-c',SAMPLE_CODE,M.__file__,sha(M.__file__),host]
    child=None
    try:
        child=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,
                               stdin=subprocess.DEVNULL)
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise RuntimeError('resource sample missed one-second deadline')
        output,error=child.communicate(timeout=remaining)
        if child.returncode or time.monotonic()>deadline:
            raise RuntimeError('resource sample failed or missed one-second deadline')
        return json.loads(output)
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def run(config, mode):
    host = os.uname().nodename.split('.')[0]
    assert config['host'] == host and config['seed'] == SEEDS[host]
    assert os.environ.get('CLASHER_LEASE_JOB') and os.environ.get('CLASHER_LEASE_STOP_FILE')
    M = supervisor(host)
    token = os.environ['CLASHER_LEASE_JOB']
    started = time.monotonic()
    env = environment(config)
    out = Path(config['out'])
    stopping = False
    def request(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM,request)
    notifier = None
    if mode == 'train':
        assert not out.exists(), 'supplemental seed already started; no resume/replacement'
        out.mkdir()
        from bot.pretrain_v1.lease_stop import LeaseStop
        os.environ['PV1_LEASE_STOP_ONLY'] = '1'
        notifier = LeaseStop.from_env(out,config['seed'])
        # Wrapper keeps a flag-only handler; the notifier validates the own generation.
        signal.signal(signal.SIGTERM,request)
    def check_initialization():
        if notifier is not None:
            notifier.signal_requested = stopping
            notifier.poll()
        elif stopping or Path(os.environ['CLASHER_LEASE_STOP_FILE']).exists():
            raise RuntimeError('lease stopped CPU qualification initialization')
    verify(config,check_initialization)
    check_initialization()
    if mode == 'probe':
        env['CUDA_VISIBLE_DEVICES'] = ''
        args = [config['python'],'-B','-m','bot.pretrain_v1.supplemental_job','probe-child',config['config_path']]
    else:
        receipt = json.loads((BASE/'memory-probe.json').read_bytes())
        validate_memory(receipt,config,M.boot_id())
        env['PV1_LEASE_STOP_ONLY'] = '1'
        args = [config['python'],'-B','-m','bot.pretrain_v1.train_bc',
                '--store',config['store'],'--out',str(out),'--seed',str(config['seed']),
                '--device','cuda','--threads','3','--d','320','--layers','6','--heads','8',
                '--ffn','1280','--drop','0.1','--lr','2e-4','--wd','0.01',
                '--amp','bf16','--bs','512','--epochs','8','--patience','2']
    proc = None
    peak = 0.0
    failure = None
    try:
        proc = subprocess.Popen(args,cwd=ADAPTER,env=env,stdin=subprocess.DEVNULL)
        identity = dict(pid=proc.pid,start=M.proc_stat(proc.pid)[4],boot=M.boot_id())
        publish(BASE/(mode+'-identity.json'),dict(identity,mode=mode,host=host,seed=config['seed'],
                token=token,command=args,config_sha256=sha(config['config_path']),started_utc=M.iso(M.now())))
        stop_seen = None
        next_tick=time.monotonic()
        while proc.poll() is None:
            if stopping or Path(os.environ['CLASHER_LEASE_STOP_FILE']).exists():
                if stop_seen is None:
                    stop_seen = time.monotonic()
                    proc.terminate()
                if time.monotonic()-stop_seen > 1500:
                    proc.kill()
            observed=sample_resources(M,host,next_tick+1.)
            sample,actual,gpu=observed['sample'],observed['actual'],observed['gpu']
            peak = max(peak, actual['pss']/M.GIB)
            process_cap = 32 if host in ('127x13','127x14','127x15','127x16') else 64 if host=='127x12' else 96
            bad = sample['procs'] > process_cap or sample['pss'] > (32 if host in ('127x13','127x14','127x15','127x16') else 64)*M.GIB or sample['mem'] <= 28*M.GIB or sample['load'] > 90 or gpu is None or gpu < 8
            if bad:
                failure = dict(status='resource-failure',sample=sample,gpu_free_gib=gpu)
                proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
                break
            if mode == 'probe' and time.monotonic()-started>1200:
                raise RuntimeError('CPU memory qualification deadline')
            next_tick+=1.
            time.sleep(max(0.,next_tick-time.monotonic()))
        rc = proc.wait(timeout=5)
        if failure is not None:
            publish(BASE/(mode+'-failure.json'),failure)
            raise RuntimeError('resource guard stopped own supplemental child')
        if mode == 'probe':
            assert rc == 0, rc
            child = json.loads((BASE/'memory-probe-child.json').read_bytes())
            assert child['completed'] is True and child['identity']==identity
            assert child['host']==host and child['seed']==config['seed']
            assert child['config_sha256']==sha(config['config_path'])
            rss = child['max_rss_gib']
            assert type(rss) in (int,float) and math.isfinite(rss) and rss>0
            upper = max(peak,rss+resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20)
            result = dict(status='cpu-memory-qualified',completed=True,
                    peak_pss_gib=peak,child_peak_rss_gib=rss,qualified_peak_gib=upper,
                    host=host,seed=config['seed'],identity=identity,
                    config_sha256=sha(config['config_path']),written_at=time.time())
            validate_memory(result,config,M.boot_id())
            publish(BASE/'memory-probe.json',result)
        else:
            publish(BASE/'training-exit.json',dict(returncode=rc,identity=identity,peak_pss_gib=peak,
                    status='complete' if rc==0 and (out/'summary.json').exists() else 'unfinished',
                    lease_exit=str(out/'lease-exit.json') if (out/'lease-exit.json').exists() else None))
            if rc != 0:
                raise SystemExit(rc)
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def main():
    mode, path = sys.argv[1:]
    config = json.loads(Path(path).read_bytes())
    if mode == 'probe-child':
        memory_probe(config)
    elif mode in ('probe','train'):
        run(config,mode)
    else:
        raise ValueError(mode)

if __name__ == '__main__':
    main()
