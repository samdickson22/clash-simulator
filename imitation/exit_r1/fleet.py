"""Lightweight coordinator: sum completed roots, stop owned hosts at fleet target."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shlex
import subprocess
import time


def write_json(path,value):
    path=Path(path)
    temp=path.with_suffix(path.suffix+'.partial')
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temp.replace(path)

JOB='/mpac/sdicks02/jobs/clasher/exit-r1-20261009-r1'
HOSTS=('127x03','127x04','127x08')


def remote(host,code):
    if host not in HOSTS:raise ValueError('unauthorized host')
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5',host,
        'nice -n 19 chrt --idle 0 /usr/bin/python3 -c '+shlex.quote(code)],
        text=True,capture_output=True,timeout=15,check=True)
    return json.loads(result.stdout)


def status(host):
    return remote(host,'import json,pathlib; p=pathlib.Path('+repr(JOB+'/generation')+'); '
        's=json.loads((p/"progress.json").read_text()); '
        'e=json.loads((p/"exit.json").read_text()) if (p/"exit.json").exists() else None; '
        's.update(e["totals"],fully_vacated=e["fully_vacated"]) if e else None; print(json.dumps(s))')


def stop(host):
    return remote(host,'import pathlib,json; p=pathlib.Path('+repr(JOB+'/GENERATION.STOP')+'); '
        'p.touch(); print(json.dumps({"stop_path":str(p),"written":True}))')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--target',type=int,default=6000000)
    a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    history=[]
    with (out/'observations.jsonl').open('a',buffering=1) as log:
        while True:
            now=time.monotonic();states={};errors={}
            for host in HOSTS:
                try:states[host]=status(host)
                except Exception as e:errors[host]=str(e)
            if not errors:
                roots=sum(s['root_decisions'] for s in states.values())
                rows=sum(s['rows'] for s in states.values())
                history.append((now,roots,rows))
                history=history[-30:]
                # Rolling >=120s avoids interpreting startup as steady throughput.
                old=next((v for v in reversed(history) if now-v[0]>=120),history[0])
                span=now-old[0]
                rate=(roots-old[1])/span if span>0 else None
                result=dict(at=datetime.now(timezone.utc).isoformat(),root_decisions=roots,emitted_rows=rows,
                    warm_window_seconds=span,warm_roots_per_second=rate,
                    eta_seconds=max(0.,a.target-roots)/rate if rate else None,target_roots=a.target,hosts=states)
                write_json(out/'progress.json',result);log.write(json.dumps(result)+'\n');print(json.dumps(result),flush=True)
                if roots>=a.target:
                    stops={host:stop(host) for host in HOSTS}
                    start=time.monotonic()
                    while time.monotonic()-start<300:
                        final={host:status(host) for host in HOSTS}
                        if all(s.get('fully_vacated') for s in final.values()):break
                        time.sleep(2)
                    write_json(out/'exit.json',dict(at=datetime.now(timezone.utc).isoformat(),stops=stops,
                        stop_to_exit_seconds=time.monotonic()-start,hosts=final,
                        fully_vacated=all(s.get('fully_vacated') for s in final.values()),
                        final_roots=sum(s['root_decisions'] for s in final.values())))
                    return
            else:
                write_json(out/'errors.json',dict(at=datetime.now(timezone.utc).isoformat(),errors=errors))
            time.sleep(30)


if __name__=='__main__':main()
