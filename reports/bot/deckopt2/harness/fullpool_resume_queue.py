"""Resume reviewed partial blocks on their original host, then claim new blocks."""
import json,os
from pathlib import Path
import fullpool_queue as original
D=original.ROOT

def claim(worker):
    if (D/'STOP').exists():return None
    meta=json.loads((D/'resume-manifest.json').read_text())
    for item in meta['partial_blocks']:
        if item['host']!=worker.split('-')[0]:continue
        path=D/'recovery-claims'/f"{item['index']:04d}.json"
        try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:continue
        with os.fdopen(fd,'w') as stream:json.dump(dict(utc=original.utc(),worker=worker,index=item['index'],reviewed_claim=item),stream)
        return item['index']
    return original.claim(worker)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--worker',required=True);a=p.parse_args()
    assert original.re.fullmatch(r'127x0[134]-[a-zA-Z0-9_-]+',a.worker)
    print(json.dumps(dict(index=claim(a.worker))))
