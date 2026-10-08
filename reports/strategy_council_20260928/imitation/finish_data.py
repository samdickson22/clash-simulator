"""Detached continuation: collect T2, audit/copy, build T3, score/copy/receipt.

Each expensive phase has a completion receipt. Re-running resumes verified
outputs; no input or fleet data is deleted. Failure writes operations/blocked.
"""
import argparse
import json
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DATA=HERE/'data'
JOBS=Path('/mpac/sdicks02/jobs/clasher')
OPS=DATA/'operations'
SIDECAR=DATA/'c56-sidecars-v1'
STORE=DATA/'c56-store-v1'
BASELINES=DATA/'baselines-v1'
PYTHON=ROOT/'.venv/bin/python'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def run(args):
    print(shlex.join(map(str,args)),flush=True)
    subprocess.run(list(map(str,args)),check=True,cwd=ROOT)


def remote(host,args):
    run(['ssh',host,shlex.join(map(str,args))])


def copy_tree(source,destination,files,tag):
    listing=OPS/f'{tag}-files.txt';listing.write_text('\n'.join(files)+'\n')
    run(['rsync','-cr','--files-from',listing,str(source).rstrip('/')+'/',str(destination).rstrip('/')+'/'])
    result=subprocess.run(['rsync','-crni','--files-from',str(listing),str(source).rstrip('/')+'/',str(destination).rstrip('/')+'/'],
                          check=True,capture_output=True,text=True)
    (OPS/f'{tag}-verify.txt').write_text(result.stdout)
    assert not result.stdout, result.stdout[:1000]


def wait_production():
    deadline=time.monotonic()+12*3600
    labels={'127x01':'imitation-t2-production-01-v1','127x03':'imitation-t2-production-03-v1'}
    while time.monotonic()<deadline:
        status={}
        for host,label in labels.items():
            path=JOBS/f'{label}.exit'
            if host=='127x01':text=path.read_text().strip() if path.exists() else 'running'
            else:
                script=f'if test -f {shlex.quote(str(path))}; then cat {shlex.quote(str(path))}; else echo running; fi'
                p=subprocess.run(['ssh',host,script],check=True,text=True,capture_output=True)
                text=p.stdout.strip()
            assert text in ('running','0'),(host,label,text)
            status[host]=text
        write(OPS/'continuation-status.json',dict(stage='T2 replay',status=status,utc=time.time()))
        if all(s=='0' for s in status.values()):return
        time.sleep(60)
    raise TimeoutError('12-hour replay deadline; inspect PIDs before resuming')


def mirror(root,host,kind):
    remote(host,['mkdir','-p',root])
    files=[str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.suffix!='.tmp']
    copy_tree(root,f'{host}:{root}',files,f'{kind}-{host}')
    remote(host,[PYTHON,'-B',HERE/'verify_artifacts.py',kind,root])
    run(['rsync','-c',f'{host}:{root}/copy-verified-{host}.json',root])
    return json.loads((root/f'copy-verified-{host}.json').read_text())


def main():
    assert socket.gethostname()=='127x01'
    OPS.mkdir(parents=True,exist_ok=True)
    started=time.time()
    wait_production()
    # Only this task's new output subtree is collected; partitions are disjoint.
    code='from pathlib import Path; p=Path('+repr(str(SIDECAR))+'); print("\\n".join(str(f.relative_to(p)) for f in p.rglob("*") if f.is_file() and f.suffix!=".tmp"))'
    p=subprocess.run(['ssh','127x03',shlex.join([str(PYTHON),'-B','-c',code])],check=True,capture_output=True,text=True)
    copy_tree(f'127x03:{SIDECAR}',SIDECAR,p.stdout.splitlines(),'collect-03')
    if not (SIDECAR/'manifest.json').exists():
        run([PYTHON,'-B',HERE/'replay_sidecars.py','--out',SIDECAR,'--finalize'])
    backup=mirror(SIDECAR,'127x04','sidecars')
    manifest=json.loads((SIDECAR/'manifest.json').read_text())
    write(DATA/'receipts/T2-PASS.json',dict(passed=True,perspectives=manifest['perspectives'],rows=manifest['rows'],
          units=manifest['units'],violations=manifest['violations'],cpu_seconds=manifest['cpu_seconds'],backup=backup,
          manifest=str(SIDECAR/'manifest.json'),coverage=str(SIDECAR/'coverage.json')))
    write(OPS/'continuation-status.json',dict(stage='T3 store',utc=time.time()))
    if not (STORE/'manifest.json').exists():
        run([PYTHON,'-B',HERE/'build_store.py','--out',STORE,'--sidecar',SIDECAR])
    write(OPS/'continuation-status.json',dict(stage='T3 baselines',utc=time.time()))
    if not (BASELINES/'frequency-complete.json').exists():
        run([PYTHON,'-B',HERE/'baselines.py','frequency','--store',STORE,'--out',BASELINES])
    if not (BASELINES/'p16-complete.json').exists():
        # CPU by default: the hub GPU remains available to the perception worker.
        run([PYTHON,'-B',HERE/'baselines.py','p16','--store',STORE,'--out',BASELINES,'--device','cpu'])
    write(OPS/'continuation-status.json',dict(stage='T3 LAN copies',utc=time.time()))
    copies=[mirror(STORE,host,'store') for host in ('127x04','127x08')]
    store=json.loads((STORE/'manifest.json').read_text())
    metrics={p.stem:json.loads(p.read_text()) for p in BASELINES.glob('*.json') if 'perspectives' not in p.stem}
    write(DATA/'receipts/T3-PASS.json',dict(passed=True,store=str(STORE),roles=store['roles'],
          roundtrip_perspectives=store['roundtrip_perspectives'],roundtrip_exact=store['roundtrip_exact'],
          copies=copies,baselines=metrics,continuation_wall_seconds=time.time()-started))
    write(OPS/'continuation-status.json',dict(stage='complete',utc=time.time()))


if __name__=='__main__':
    try:main()
    except BaseException:
        write(OPS/'continuation-blocked.json',dict(passed=False,utc=time.time(),traceback=traceback.format_exc()))
        raise
