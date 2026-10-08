"""Engineering-only cross-host parity and six-thread data-throughput probe."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import random
import re
import socket
import subprocess
import time

from cache_transport_v4 import RemotePixelCache
from pixel_cache import sha


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--server-label',required=True)
    p.add_argument('--output',type=Path,required=True)
    for name in ('union-local-cache','union-base-inventory','union-base-manifest','union-source'):
        p.add_argument('--'+name,type=Path)
    p.add_argument('--union-remote-prefix')
    a=p.parse_args()
    if not re.fullmatch(r'v4-cache-transport-server-[a-zA-Z0-9-]+',a.server_label):
        raise ValueError('Owned server label required')
    a.output.mkdir(exist_ok=False)
    jobs='/mpac/sdicks02/repos/clasher-lease/jobs/'
    prefix=jobs+a.server_label
    union_args=[a.union_local_cache,a.union_base_inventory,a.union_base_manifest,a.union_source,a.union_remote_prefix]
    if any(union_args) and not all(union_args):raise ValueError('All union probe paths required')
    if a.union_remote_prefix and not re.fullmatch(r'v4-cache-unique-[a-zA-Z0-9-]+',a.union_remote_prefix):
        raise ValueError('Owned extension prefix required')
    tunnel=None;cache=None
    try:
        for suffix in ('ready.json','reference.json','token'):
            dst=a.output/suffix
            if suffix=='token':dst.touch(mode=0o600,exist_ok=False)
            subprocess.run(['scp','-q','127x16:'+prefix+'.'+suffix,str(dst)],check=True)
        token_path=a.output/'token'
        if token_path.stat().st_mode&0o077:raise ValueError('Token permissions')
        ready=json.loads((a.output/'ready.json').read_text())
        ref=json.loads((a.output/'reference.json').read_text())
        if (ready['payloads_verified'] is not True or ready['heldout_payloads_opened'] is not False
                or ref['heldout_payloads_opened'] is not False
                or ready['manifest_sha256']!=ref['manifest_sha256']
                or ready['index_sha256']!=ref['index_sha256']):raise ValueError('Reference pin mismatch')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        tunnel=subprocess.Popen(['ssh','-N','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes',
            '-L',f'127.0.0.1:{port}:127.0.0.1:{ready["port"]}','127x16'])
        for _ in range(100):
            if tunnel.poll() is not None:raise RuntimeError('Tunnel exited')
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1):break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Tunnel did not start')
        cache=RemotePixelCache(f'http://127.0.0.1:{port}/',token_path.read_text().strip(),ref['receipts'],ref['index_sha256'])
        benchmark_rows=ref['receipts'];union_initialization_seconds=None
        if all(union_args):
            from cache_union_v4 import UnionPixelCache
            for suffix in ('plan.json','manifest.json'):
                subprocess.run(['scp','-q','127x16:'+jobs+a.union_remote_prefix+'-'+suffix,str(a.output/suffix)],check=True)
            base=json.loads(a.union_base_inventory.read_text());local_rows=[]
            for ep,digest in base['receipt_sha256'].items():
                if '/' in ep or not ep.startswith('v4-phase-a-'):raise ValueError('Invalid base episode')
                path=a.union_source/ep/'receipt.json'
                if sha(path)!=digest:raise ValueError('Base receipt changed')
                row=json.loads(path.read_text());local_rows.append(dict(row,receipt_sha256=digest))
            benchmark_rows=local_rows+ref['receipts'];start=time.monotonic()
            cache=UnionPixelCache(benchmark_rows,[
                dict(kind='local',cache=a.union_local_cache,inventory=a.union_base_inventory,manifest=a.union_base_manifest),
                dict(kind='remote',inventory=a.output/'plan.json',manifest=a.output/'manifest.json',
                    ready=a.output/'ready.json',token_file=token_path,endpoint=f'http://127.0.0.1:{port}/')])
            union_initialization_seconds=time.monotonic()-start
        checked=0;start=time.monotonic()
        for check in ref['checks']:
            samples=cache.get(check['episode'],check['indices'],raw=check['raw'])
            hashes=[hashlib.sha256(x.tobytes() if check['raw'] else x[0].tobytes()+x[1].tobytes()).hexdigest() for x in samples]
            if hashes!=check['sha256']:raise ValueError('Cross-host pixel mismatch')
            checked+=len(hashes)
        parity_seconds=time.monotonic()-start
        rng=random.Random(6113);windows=[]
        for i in range(128):
            r=rng.choice(benchmark_rows);end=rng.randrange(15,r['frames'])
            windows.append((r['episode'],list(range(end-15,end+1)),bool(i%2)))
        def load(item):
            ep,indices,raw=item
            result=cache.get(ep,indices,raw=raw)
            return len(result)
        start=time.monotonic()
        with ThreadPoolExecutor(max_workers=6) as pool:
            counts=list(pool.map(load,windows))
        elapsed=time.monotonic()-start
        assert counts==[16]*128
        result=dict(engineering_only=True,matches=len(benchmark_rows),remote_matches=len(ref['receipts']),
            union_initialization_seconds=union_initialization_seconds,
            union_provenance=getattr(cache,'provenance',None),
            raw_and_model_samples_checked=checked,equality_mismatches=0,parity_seconds=parity_seconds,
            windows=128,window_frames=16,threads=6,raw_fraction=.5,
            data_only_windows_per_second=128/elapsed,elapsed_seconds=elapsed,
            manifest_sha256=ref['manifest_sha256'],reference_sha256=sha(a.output/'reference.json'),
            probe_source_sha256=sha(__file__),heldout_payloads_opened=False,
            gpu_training_measured=False,formal_population_seal=False)
        with (a.output/'result.json').open('x') as f:json.dump(result,f,indent=2)
        print(json.dumps(result),flush=True)
    finally:
        if cache is not None and hasattr(cache,'close'):cache.close()
        if tunnel is not None and tunnel.poll() is None:
            tunnel.terminate()
            try:tunnel.wait(timeout=10)
            except subprocess.TimeoutExpired:tunnel.kill();tunnel.wait()
        subprocess.run(['ssh','127x16','touch',prefix+'.stop'],check=False)


if __name__=='__main__':main()
