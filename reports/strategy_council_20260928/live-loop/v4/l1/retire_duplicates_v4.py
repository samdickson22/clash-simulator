"""Approved349-base retirement: verify01, then unlink only698 named18 payloads.

Queue on01 via fleet_run; worker on18 via its unchanged exclusive lease wrapper.
Never removes directories, indices, acquisition inputs, unique shards or weights.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import time


LEASE=Path('/mpac/sdicks02/repos/clasher-lease')
HOME=Path('/mpac/sdicks02/repos/clasher-v4-cache')
TARGET=LEASE/'data/v4-cache'
FILES=('raw.zst','pixels.zst')
MANIFEST_SHA='67b710014a12fb12ec363611c36b7f11bcdb97e08a01d94876efb9d6f06d8c14'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
    return h.hexdigest()


def read(path):return json.loads(path.read_text())
def put(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def proposal(path):
    value=read(path)
    if (value.get('source_host')!='127x18' or value.get('retained_host')!='127x01'
            or value.get('source_root')!=str(TARGET) or value.get('retained_root')!=str(HOME)
            or value.get('matches')!=349 or len(value.get('index_sha256',{}))!=349
            or value.get('evidence_manifest_sha256')!=MANIFEST_SHA
            or any(re.fullmatch(r'v4-phase-a-[0-9]+',ep) is None for ep in value['index_sha256'])):
        raise ValueError('Only the explicitly approved349-base proposal is eligible')
    return value


def file_info(path):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode):raise ValueError('Regular cache file required')
    return [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns]


def target_plan(root,pins,verified):
    """Validate every target before any unlink; indices are retained in place."""
    if root.resolve()!=root:raise ValueError('Cache root alias refused')
    if set(pins)!=set(verified):raise ValueError('Retained verification population differs')
    plan=[]
    for ep,digest in sorted(pins.items()):
        if re.fullmatch(r'v4-phase-a-[0-9]+',ep) is None:raise ValueError('Unsafe episode')
        folder=root/ep
        if folder.is_symlink() or not folder.is_dir():raise ValueError('Regular shard directory required')
        index=folder/'index.json';file_info(index)
        if sha(index)!=digest:raise ValueError('Target index differs from retained verified index')
        idx=read(index);v=verified[ep]
        if (idx['split'] not in ('train','validation') or set(idx['sha256'])!=set(FILES)
                or idx['sha256']!=v['sha256'] or idx['equality']!=v['equality']
                or v['index_sha256']!=digest or idx['equality'].get('pass') is not True):
            raise ValueError('Checksum/equality provenance differs')
        for name in FILES:
            path=folder/name;info=file_info(path)
            if info[2]!=v['sizes'][name]:raise ValueError('Target payload size differs')
            plan.append((ep,name,info,idx['sha256'][name]))
    return plan


def remote_status():
    command=r'''
import datetime,fcntl,json,pathlib
p=pathlib.Path('/mpac/sdicks02/fleet-leases/127x18.json');r=json.loads(p.read_text())
end=datetime.datetime.fromisoformat(r['expected_end_utc'].replace('Z','+00:00'))
assert r['project']=='clasher' and not r.get('reclaim') and not r.get('refused')
assert datetime.datetime.now(datetime.timezone.utc)<end
f=open('/mpac/sdicks02/repos/clasher-lease/jobs/host-workload.lock','a')
try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);free=True
except BlockingIOError:free=False
print(json.dumps(dict(workload_lock_free=free)))
'''
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','127x18','python3 -'],
        input=command,text=True,capture_output=True,check=True,timeout=30)
    return json.loads(result.stdout)


def worker(a):
    if socket.gethostname().split('.')[0]!='127x18' or os.environ.get('CLASHER_LEASE_ROOT')!=str(LEASE):
        raise ValueError('18 lease wrapper required')
    if a.output.parent!=LEASE/'jobs' or a.output.exists():raise ValueError('Fresh lease-local evidence directory required')
    approved=proposal(a.proposal);proof=read(a.proof)
    if (proof.get('proposal_sha256')!=sha(a.proposal) or proof.get('host')!='127x01'
            or proof.get('fully_verified') is not True or time.time()-proof['verified_time']>900):
        raise ValueError('Fresh full retained-copy verification required')
    with (TARGET/'.writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        plan=target_plan(TARGET,approved['index_sha256'],proof['matches'])
        if len(plan)!=698:raise ValueError('Exactly698 approved payloads required')
        a.output.mkdir()
        shutil.copyfile(a.proposal,a.output/'proposal.json');shutil.copyfile(a.proof,a.output/'retained-verification.json')
        deleted=0;released=0
        with (a.output/'retirement.jsonl').open('x') as journal:
            for ep,name,expected,digest in plan:
                # Reclaim/expiry must stop this bounded metadata operation promptly.
                lease=read(Path('/mpac/sdicks02/fleet-leases/127x18.json'))
                end=datetime.datetime.fromisoformat(lease['expected_end_utc'].replace('Z','+00:00')).timestamp()
                if lease.get('project')!='clasher' or lease.get('reclaim') or lease.get('refused') or time.time()>=end:
                    raise ValueError('Lease no longer permits retirement')
                path=TARGET/ep/name
                if file_info(path)!=expected:raise ValueError('Target changed after preflight')
                row=dict(episode=ep,file=name,bytes=expected[2],sha256=digest)
                journal.write(json.dumps(dict(row,status='intent'))+'\n');journal.flush();os.fsync(journal.fileno())
                directory=os.open(TARGET/ep,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
                try:
                    current=os.stat(name,dir_fd=directory,follow_symlinks=False)
                    if [current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns,current.st_ctime_ns]!=expected:
                        raise ValueError('Target changed before unlink')
                    os.unlink(name,dir_fd=directory)
                finally:os.close(directory)
                journal.write(json.dumps(dict(row,status='deleted'))+'\n');journal.flush();os.fsync(journal.fileno())
                deleted+=1;released+=expected[2]
        put(a.output/'complete.json',dict(deleted_payloads=deleted,retired_matches=349,released_bytes=released,
            proposal_sha256=sha(a.proposal),proof_sha256=sha(a.proof),indices_retained=True,
            raw_acquisition_touched=False,unique_shards_touched=False,weights_touched=False,heldout_payloads_opened=False))


def queue(a):
    if socket.gethostname().split('.')[0]!='127x01':raise ValueError('01 fleet queue required')
    approved=proposal(a.proposal)
    if a.output.parent!=Path('/mpac/sdicks02/jobs/clasher') or a.output.exists():raise ValueError('Fresh home job directory required')
    if re.fullmatch(r'v4-duplicate-retirement-[a-zA-Z0-9-]+',a.label) is None:raise ValueError('Safe retirement label required')
    a.output.mkdir();deadline=datetime.datetime.fromisoformat(a.deadline.replace('Z','+00:00')).timestamp()
    while time.time()<deadline:
        state=remote_status();print(json.dumps(dict(time=time.time(),**state)),flush=True)
        if state['workload_lock_free']:break
        time.sleep(min(60,max(0,deadline-time.time())))
    else:
        put(a.output/'stopped.json',dict(reason='deadline waiting for18 workload lock',deleted=False));return
    # Keep01 immutable through verification and18 retirement. The training cache
    # service's shared lock coexists; no second heavy verifier runs while blocked.
    with (HOME/'.writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_SH|fcntl.LOCK_NB)
        evidence={};archive=a.output/'indices';archive.mkdir()
        for ep,expected in sorted(approved['index_sha256'].items()):
            folder=HOME/ep
            if folder.is_symlink():raise ValueError('Retained shard alias refused')
            index=folder/'index.json';file_info(index)
            if sha(index)!=expected:raise ValueError('Retained index changed')
            idx=read(index)
            if (idx['split'] not in ('train','validation') or set(idx['sha256'])!=set(FILES)
                    or idx['equality'].get('pass') is not True or idx['equality'].get('mismatches')!=0):
                raise ValueError('Retained equality evidence invalid')
            sizes={}
            for name,digest in idx['sha256'].items():
                path=folder/name;before=file_info(path)
                if sha(path)!=digest or file_info(path)!=before:raise ValueError('Retained payload failed verification')
                sizes[name]=before[2]
            shutil.copyfile(index,archive/(ep+'.json'))
            evidence[ep]=dict(index_sha256=expected,sha256=idx['sha256'],sizes=sizes,equality=idx['equality'])
        proof=a.output/'retained-verification.json'
        put(proof,dict(host='127x01',verified_time=time.time(),fully_verified=True,
            proposal_sha256=sha(a.proposal),matches=evidence,heldout_payloads_opened=False))
        if time.time()>=deadline:raise ValueError('Retirement queue deadline reached after verification')
        remote=LEASE/'jobs'/a.label
        for source,suffix in [(proof,'-proof.json'),(a.proposal,'-proposal.json')]:
            subprocess.run(['scp','-q',str(source),'127x18:'+str(remote)+suffix],check=True,timeout=30)
        script=LEASE/'repo/reports/strategy_council_20260928/live-loop/v4/l1/retire_duplicates_v4.py'
        subprocess.run(['ssh','127x18','bash',str(LEASE/'run.sh'),a.label,
            str(LEASE/'envs/clasher-gpu/bin/python'),'-B',str(script),'--mode','worker',
            '--proposal',str(remote)+'-proposal.json','--proof',str(remote)+'-proof.json',
            '--output',str(remote)+'-evidence'],check=True,timeout=30)
        # The metadata-only worker should finish in seconds; preserve the held
        # retained-copy lock until its bounded receipt is collected.
        for _ in range(60):
            result=subprocess.run(['ssh','127x18','cat',str(remote)+'.exit.json'],capture_output=True,text=True,timeout=20)
            if result.returncode==0:
                receipt=json.loads(result.stdout);put(a.output/'worker-exit.json',receipt)
                if receipt.get('exit_code')!=0:raise ValueError('Retirement worker failed; inspect retained evidence, no automatic retry')
                subprocess.run(['scp','-q','127x18:'+str(remote)+'-evidence/complete.json',str(a.output/'complete.json')],check=True,timeout=30)
                return
            time.sleep(5)
        raise ValueError('Retirement receipt timeout; inspect exact worker before any retry')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=('queue','worker'),required=True)
    for name in ('proposal','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--proof',type=Path);p.add_argument('--label');p.add_argument('--deadline',default='2026-10-09T04:50:00Z')
    args=p.parse_args();(queue if args.mode=='queue' else worker)(args)
