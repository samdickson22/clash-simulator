"""SHA256 verification of imitation output manifests on a LAN destination."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import time


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4<<20),b''):digest.update(block)
    return digest.hexdigest()


def verify(root,kind):
    start=time.perf_counter();manifest=json.loads((root/'manifest.json').read_text())
    assert manifest['passed']
    if kind=='sidecars':
        assert json.loads((root/'header-contract-audit.json').read_text())['passed'], 'header provenance decision pending'
        files=manifest['files']
    else:
        files={'mask_table.npy':manifest['mask_table_sha256'],'plan.json':manifest['plan_sha256']}
        for role,digest in manifest['role_manifests'].items():
            files[f'{role}/manifest.json']=digest
            local=json.loads((root/role/'manifest.json').read_text())
            files.update({f'{role}/{name}.npy':info['sha256'] for name,info in local['arrays'].items()})
    for number,(name,digest) in enumerate(files.items()):
        assert sha(root/name)==digest,(name,'checksum mismatch')
        if number%200==0: print(json.dumps(dict(verified=number,files=len(files))),flush=True)
    result=dict(passed=True,host=socket.gethostname(),kind=kind,root=str(root),files=len(files),
                bytes=sum((root/n).stat().st_size for n in files),manifest_sha256=sha(root/'manifest.json'),
                wall_seconds=time.perf_counter()-start)
    target=root/f'copy-verified-{socket.gethostname()}.json'
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(target)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['store','sidecars']);p.add_argument('root',type=Path)
    args=p.parse_args();verify(args.root,args.kind)
