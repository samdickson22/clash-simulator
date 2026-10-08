"""T9: pinned, hash-verified, data-only download; never imports fetched content."""
from __future__ import annotations
import concurrent.futures, hashlib, json, os, socket, time, urllib.request
from pathlib import Path
ROOT = Path('/mpac/sdicks02/repos/clasher')
OUT = Path('/mpac/sdicks02/repos/clasher-local-data/il_replay')
DATA = ROOT / 'reports/strategy_council_20260928/imitation/data'
REV = '059d43a02138a34b1b3009cc2acc7630fb99a638'
REPO = 'VanguardX101/IL_Replay'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()

def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    s=json.dumps(x,indent=2,sort_keys=True)+'\n'
    if p.exists():
        assert p.read_text()==s, f'refuse differing existing file: {p}'
    else: p.write_text(s)

def fetch(e):
    p=OUT/e['path']; p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():
        assert p.stat().st_size==e['bytes'] and sha(p)==e['sha256'],str(p)
        return e|{'reused':True}
    for attempt in range(8):
        try:
            tmp=p.with_suffix('.download')
            req=urllib.request.Request(f'https://huggingface.co/datasets/{REPO}/resolve/{REV}/{e["path"]}',headers={'User-Agent':'Clasher-pinned-data-fetch'})
            with urllib.request.urlopen(req,timeout=180) as r, tmp.open('wb') as f:
                while b:=r.read(1048576): f.write(b)
            assert tmp.stat().st_size==e['bytes'] and sha(tmp)==e['sha256'],e['path']
            os.replace(tmp,p)
            print(json.dumps({'fetched':e['path'],'bytes':e['bytes']}),flush=True)
            return e|{'reused':False}
        except Exception as exc:
            print(json.dumps({'retry':attempt,'path':e['path'],'error':repr(exc)}),flush=True)
            if attempt==7: raise
            time.sleep(5*(attempt+1))

def main():
    assert socket.gethostname()=='127x03'
    start=time.time()
    url=f'https://huggingface.co/api/datasets/{REPO}/tree/{REV}?recursive=true&limit=1000'
    with urllib.request.urlopen(url,timeout=90) as r:
        assert 'rel="next"' not in r.headers.get('Link','')
        listing=json.load(r)
    entries=[{'path':e['path'],'bytes':e['size'],'sha256':e['lfs']['oid']} for e in listing if e['path'].endswith('.parquet')]
    entries.sort(key=lambda e:e['path'])
    assert len(entries)==104 and sum(e['path'].startswith('replays/') for e in entries)==52
    for e in entries:
        assert '..' not in Path(e['path']).parts and not Path(e['path']).is_absolute()
    manifest={'dataset':REPO,'revision':REV,'files':entries,'api':url,'untrusted_data_only':True}
    write(OUT/'hf_manifest.json',manifest)
    write(DATA/'source/hf_manifest.json',manifest)
    with concurrent.futures.ThreadPoolExecutor(4) as pool: results=list(pool.map(fetch,entries))
    write(DATA/'receipts/T9-fetch.json',{'revision':REV,'dataset':REPO,'files':len(results),'bytes':sum(e['bytes'] for e in entries),'sha256_verified':True,'manifest_sha256':sha(OUT/'hf_manifest.json'),'wall_seconds':time.time()-start,'host':socket.gethostname()})
if __name__=='__main__':main()
