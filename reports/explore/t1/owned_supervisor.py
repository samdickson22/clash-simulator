"""OP-3: authenticate the owned supervisor and its explicitly launched groups."""
import hashlib,os,shlex,socket
from pathlib import Path
from common import read,write,utc

KEYS=('pid','pgid','start_ticks','uid','cmdline_sha256','exe')
GROUP_KEYS=('pid','pgid','start_ticks','uid')

def identity(row,keys=KEYS):return {k:row[k] for k in keys}
def matches(row,pin):return row is not None and all(row.get(k)==v for k,v in pin.items())

def live_identity(pid):
    d=Path('/proc')/str(pid)
    try:
        stat=(d/'stat').read_text().rsplit(')',1)[1].split();uid=d.stat().st_uid
        raw=(d/'cmdline').read_bytes();exe=(d/'exe').resolve(strict=True).as_posix()
        check=(d/'stat').read_text().rsplit(')',1)[1].split()
        if stat[19]!=check[19] or uid!=d.stat().st_uid:return None
        return dict(pid=pid,ppid=int(stat[1]),pgid=int(stat[2]),start_ticks=int(stat[19]),uid=uid,
                    cmdline_sha256=hashlib.sha256(raw).hexdigest(),exe=exe)
    except OSError:return None

def pin(j,rows,phase):
    r=next(r for r in rows if r['pid']==os.getpid())
    assert r['pgid']==os.getpgrp()==r['pid'] and r['uid']==os.getuid()
    argv=shlex.split(r['cmd'])
    assert 'reports/explore/t1/supervise.py' in argv and '--job' in argv
    assert argv[argv.index('--job')+1]==str(j)
    assert matches(live_identity(r['pid']),identity(r)),'supervisor identity changed'
    target=j/'owned-supervisor-admission.json'
    assert not target.exists(),'supervisor admission cannot be silently refreshed'
    write(target,dict(utc=utc(),host=socket.gethostname(),job=str(j),phase=phase,
                      supervisor=identity(r),worker_groups=[]))

def add_worker(j,pid):
    target=j/'owned-supervisor-admission.json';receipt=read(target);root=receipt['supervisor']
    assert root['pid']==os.getpid() and matches(live_identity(root['pid']),root)
    child=live_identity(pid)
    assert child and child['pgid']==pid and child['ppid']==root['pid'] and child['uid']==root['uid']
    pin=identity(child,GROUP_KEYS)
    assert pin not in receipt['worker_groups'];receipt['worker_groups'].append(pin)
    write(target,receipt)

def member(j,row,reader=None):
    reader=reader or live_identity
    target=j/'owned-supervisor-admission.json'
    if not target.exists():return False
    receipt=read(target);root=receipt['supervisor']
    if receipt['job']!=str(j) or row['uid']!=root['uid'] or not matches(reader(root['pid']),root):return False
    if row['pid']==root['pid']:return matches(row,root)
    if row['pgid']==root['pgid'] or row['ppid']==root['pid']:return True
    for group in receipt['worker_groups']:
        if row['pgid']!=group['pgid'] and row['ppid']!=group['pid']:continue
        leader=reader(group['pid'])
        # An exited group leader can be proven by its captured identity. Other
        # members require a still-identical leader; PID/PGID reuse is foreign.
        if leader is None:
            if row['pid']==group['pid'] and matches(row,group):return True
        elif matches(leader,group):return True
    return False
