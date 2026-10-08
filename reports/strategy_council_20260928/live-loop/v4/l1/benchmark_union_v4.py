"""Detached engineering union benchmark: lease18/16 or home01/03 only."""
import argparse
import json
from pathlib import Path
import re
import signal
import socket
import subprocess
import time
from pixel_cache import sha


def main():
    p=argparse.ArgumentParser()
    for n in ('server-label','extension-prefix'):p.add_argument('--'+n,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    host=socket.gethostname().split('.')[0]
    if host not in ('127x18','127x01'):raise ValueError('Approved benchmark client required')
    home=host=='127x01';server_host='127x03' if home else '127x16'
    if not re.fullmatch('v4-cache-transport-server-[a-zA-Z0-9-]+',a.server_label):raise ValueError('Invalid server label')
    if not re.fullmatch('v4-cache-unique-[a-zA-Z0-9-]+',a.extension_prefix):raise ValueError('Invalid extension label')
    root=Path('/mpac/sdicks02/repos/clasher-lease');jobs=root/'jobs';source=root/'data/v4-matches'
    code=Path(__file__).parent;python=str(root/'envs/clasher-gpu/bin/python')
    remote_jobs=jobs;local_cache=root/'data/v4-cache'
    if home:
        jobs=Path('/mpac/sdicks02/jobs/clasher');remote_jobs=jobs
        source=a.output/'source';python='/mpac/sdicks02/envs/clasher-gpu/bin/python'
        local_cache=Path('/mpac/sdicks02/repos/clasher-v4-cache')
    a.output.mkdir(exist_ok=False);child=None;tunnel=None;stopped=False
    def stop(sig,frame):
        nonlocal stopped
        stopped=True
        if child is not None and child.poll() is None:child.send_signal(signal.SIGTERM)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGUSR1,stop)
    def run(cmd):
        nonlocal child
        if stopped:raise SystemExit(75)
        child=subprocess.Popen(list(map(str,cmd)));rc=child.wait();child=None
        if stopped:raise SystemExit(75)
        if rc:raise subprocess.CalledProcessError(rc,cmd)
    try:
        for suffix in (('ready.json','token') if home else ('ready.json','reference.json','token')):
            dst=a.output/suffix
            if suffix=='token':dst.touch(mode=0o600)
            run(['scp','-q',server_host+':'+str(remote_jobs/(a.server_label+'.'+suffix)),dst])
        for suffix in ('plan.json','manifest.json'):
            run(['scp','-q',server_host+':'+str(remote_jobs/(a.extension_prefix+'-'+suffix)),a.output/suffix])
        base_inventory=jobs/'v4-cache-extend-20261008-18r10-stage.json'
        base_manifest=jobs/'v4-cache-gather-20261008-18r10-manifest.json'
        if home:
            evidence=code/'receipts/preformal-cache-20261008'
            base_inventory=evidence/base_inventory.name;base_manifest=evidence/base_manifest.name
        base=json.loads(base_inventory.read_text());extension=json.loads((a.output/'plan.json').read_text())
        expected=dict(base['receipt_sha256'])
        if set(expected)&set(extension['receipt_sha256']):raise ValueError('Overlapping snapshots')
        expected.update(extension['receipt_sha256'])
        # Explicit admitted episodes only; this remains an engineering snapshot.
        if home:
            expected_path=a.output/'expected.json';expected_path.write_text(json.dumps(expected))
            run([python,'-B',code/'stage_engineering_view_v4.py','--destination',source,
                '--split',code.parent/'split.json','--expected',expected_path])
        else:
            run([python,'-B',code/'stage_training.py','--destination',source,'--split',code.parent/'split.json','--episodes',*sorted(expected)])
        stage=json.loads((source/'stage-inventory.json').read_text())
        if stage['receipt_sha256']!=expected or stage['heldout_payloads_opened'] is not False:
            raise ValueError('Staged snapshot differs from pinned union')
        (a.output/'stage.json').write_text(json.dumps(stage,indent=2))
        ready=json.loads((a.output/'ready.json').read_text())
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        tunnel=subprocess.Popen(['ssh','-N','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes',
            '-L',f'127.0.0.1:{port}:127.0.0.1:{ready["port"]}',server_host])
        for _ in range(100):
            if stopped:raise SystemExit(75)
            if tunnel.poll() is not None:raise RuntimeError('Tunnel exited')
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1):break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Tunnel unavailable')
        spec=dict(schema='clasher.v4.engineering-union.v1',receipt_sha256=expected,shards=[
            dict(kind='local',cache=str(local_cache),inventory=str(base_inventory),manifest=str(base_manifest)),
            dict(kind='remote',inventory=str(a.output/'plan.json'),manifest=str(a.output/'manifest.json'),
                ready=str(a.output/'ready.json'),token_file=str(a.output/'token'),endpoint=f'http://127.0.0.1:{port}/')])
        runtime=a.output/'runtime.json';runtime.write_text(json.dumps(spec,indent=2))
        run([python,'-B',code/'train_v4.py','--source',source,'--split',code.parent/'split.json',
             '--output',a.output/'model','--engineering-union',runtime,'--epochs','1','--steps','128','--loader-workers','6'])
        result=dict(engineering_only=True,formal_population_seal=False,heldout_payloads_opened=False,
            client_host=host,server_host=server_host,staged_matches=len(expected),
            scope='explicit cached engineering subset; cannot substitute for formal full-population fitting',
            source_sha256=sha(__file__),training_complete_sha256=sha(a.output/'model/complete.json'),
            parity_sha256=sha(a.output/'model/union-parity.json'))
        (a.output/'complete.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    finally:
        if tunnel is not None and tunnel.poll() is None:
            tunnel.terminate()
            try:tunnel.wait(timeout=10)
            except subprocess.TimeoutExpired:tunnel.kill();tunnel.wait()
        subprocess.run(['ssh',server_host,'touch',str(remote_jobs/(a.server_label+'.stop'))],check=False)


if __name__=='__main__':main()
