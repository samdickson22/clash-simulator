"""Publish R3's admission receipt after complete K2 audit and process vacancy.

Post-run helper only. Copy to NEW $job/publish_release.py after reporting;
never add/replace a file in the pinned runtime snapshot.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess


def census():
    rows=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            fields=(path/'stat').read_text().rsplit(')',1)[1].split()
            rows.append(dict(pid=int(path.name),pgid=int(fields[2]),
                command=(path/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')))
        except (FileNotFoundError,ProcessLookupError):continue
    return rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--job',type=Path,required=True);args=parser.parse_args();job=args.job.resolve()
    assert socket.gethostname()=='127x03'
    assert os.sched_getaffinity(0)=={59}
    assert os.getpriority(os.PRIO_PROCESS,0)==10 and os.sched_getscheduler(0)==os.SCHED_OTHER
    assert (job/'POSTPROCESSED').exists()
    audit=json.loads((job/'execution.json').read_text())
    assert audit['complete'] and audit['receipt']['games']==1800 and audit['receipt']['terminal']
    assert not audit['remaining_processes'] and not audit['source_mismatch'] and not audit['native_mismatch']
    pgids=set()
    for phase,count in [('smoke',24),('reporting',1800)]:
        launch=json.loads((job/phase/'launch.json').read_text())
        exited=json.loads((job/phase/'supervisor-exit.json').read_text())
        receipt=json.loads((job/phase/'receipt.json').read_text())
        assert exited['returncode']==0 and exited['reason'] is None
        assert receipt['games']==count and receipt['terminal']
        pgids.update((launch['supervisor_pgid'],launch['child_pgid']))
    identities=list(job.glob('*-pid.json'))+list(job.glob('smoke-prelaunch-failed-*/*-pid.json'))
    for path in identities:
        identity=json.loads(path.read_text())
        if 'pgid' in identity:pgids.add(identity['pgid'])
    assert set(audit['fully_vacated_pgids'])<=pgids
    rows=census()
    assert not [r for r in rows if r['pgid'] in pgids],'owned PGID remains'
    other_python=[r for r in rows if r['pid']!=os.getpid() and str(job) in r['command'] and 'python' in r['command'] and not r['command'].startswith(('ssh','bash -c'))]
    assert not other_python,other_python
    g=Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010')
    assert (g/'STOP-03').exists()
    gexit=json.loads((g/'generation/exit.json').read_text());assert gexit['fully_vacated']
    assert not [r for r in rows if r['pgid']==gexit['identity']['pgid']],'G PGID remains'
    result=dict(released=True,host='127x03',utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),
        pgids=sorted(pgids),reporting_complete=True,reporting_games=1800,remaining_timing_processes=[],
        execution_audit_sha256=hashlib.sha256((job/'execution.json').read_bytes()).hexdigest(),
        G_STOP03_retained=True,R3_must_independently_verify_no_K2_G_X_timing=True)
    destination=job/'K2-CPU-RELEASE.json'
    if destination.exists():
        previous=json.loads(destination.read_text())
        assert previous['released'] and previous['reporting_complete'] and previous['pgids']==result['pgids']
        assert previous['execution_audit_sha256']==result['execution_audit_sha256']
        result=previous
    else:
        temporary=job/'K2-CPU-RELEASE.json.tmp';temporary.write_text(json.dumps(result,indent=2)+'\n');temporary.replace(destination)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
