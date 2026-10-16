"""Freeze/recheck only an exact owned queued pilot; resume if admission won the race."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import time

JOB=Path('/mpac/sdicks02/jobs/clasher/cards/missing-templates-r3')
LEASES=Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims')


def process(pid):
    path=Path('/proc')/str(pid)
    try:
        raw=(path/'stat').read_text();tail=raw.rsplit(')',1)[1].split()
        argv=(path/'cmdline').read_bytes()
        return dict(pid=pid,pgid=int(tail[2]),state=tail[0],start_ticks=int(tail[19]),
            uid=path.stat().st_uid,comm=raw.split('(',1)[1].rsplit(')',1)[0],
            argv_sha256=hashlib.sha256(argv).hexdigest(),argv=argv.replace(b'\0',b' ').decode())
    except FileNotFoundError:return None


def group(pgid):
    result=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:r=process(int(path.name))
        except (PermissionError,ProcessLookupError):continue
        if r and r['pgid']==pgid:result.append(r)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--identity',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    assert a.out.parent.resolve()==JOB and not os.path.lexists(a.out)
    expected=json.loads(a.identity.read_text());pid=expected['pid']
    assert pid==2967873 and expected['pgid']==pid and expected['uid']==os.getuid()
    required='/class-checkpoint-1802e899c-source/reports/cards/runtime/tools/object_templates_probe.py --cards RageBarbarian Rage GoblinDrill IceWizard ElectroWizard --out '+str(JOB/'class-1802e899c-pilot.json')
    assert required in expected['argv']
    def validate():
        r=process(pid);assert r is not None,'launcher exited; inspect terminal state'
        assert all(r[k]==expected[k] for k in ('pgid','uid','start_ticks','argv_sha256')),(expected,r)
        return r
    lease=LEASES/f'lease-{pid}'
    def admitted(members):return lease.exists() or any(r['comm'].startswith('python') for r in members)
    validate();before=group(pid)
    assert before and all(r['uid']==os.getuid() for r in before)
    out=dict(expected=expected,before=before)
    if admitted(before):out['result']='ADMITTED_LEAVE_RUNNING'
    else:
        stopped=False
        try:
            os.killpg(pid,signal.SIGSTOP);stopped=True
            # Let pending stop signals settle and detect a child forked at the boundary.
            for attempt in range(40):
                members=group(pid)
                if members and all(r['state'] in ('T','t','Z') for r in members):break
                time.sleep(.025)
            else:raise RuntimeError('group did not stop; resume without cancellation')
            validate();out['frozen']=members
            assert all(r['uid']==os.getuid() for r in members)
            if admitted(members):out['result']='ADMITTED_LEAVE_RUNNING'
            else:
                allowed={'bash','sleep','ps','grep','awk','tr','wc','cat'}
                assert all(r['comm'] in allowed or r['state']=='Z' for r in members),members
                os.killpg(pid,signal.SIGTERM)
                out['result']='SUPERSEDED_FOR_SCHEDULING'
        finally:
            if stopped:
                try:os.killpg(pid,signal.SIGCONT)
                except ProcessLookupError:pass
        if out['result']=='SUPERSEDED_FOR_SCHEDULING':
            for attempt in range(100):
                live=[r for r in group(pid) if r['state']!='Z']
                if not live and not lease.exists():break
                time.sleep(.05)
            else:raise RuntimeError('terminal exit/no lease not confirmed; do not queue another job')
            out.update(after=group(pid),lease_exists=lease.exists())
    with a.out.open('x') as f:f.write(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(out['result'])


if __name__=='__main__':main()
