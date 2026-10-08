"""Copy only explicitly enumerated T9 products, then independently verify SHA256."""
import json,socket,subprocess
from pathlib import Path
from fetch_source import ROOT,DATA,sha,write

def main():
    assert socket.gethostname()=='127x03'
    assert json.loads((DATA/'receipts/T9-PASS.json').read_text())['status']=='PASS'
    products=[DATA/'source/hf_manifest.json',DATA/'index/perspectives.jsonl.gz',DATA/'index/c56-v2-metadata.json',DATA/'roles/s122_roles_v2.json',DATA/'qa/s122-sample.json']
    for pattern in ('payloads/shard-*.jsonl.gz','index/shards/shard-*.jsonl.gz','inputs/**/*.json.gz','inputs/*-plan.json','receipts/T9-*.json','receipts/payload-shards/*.json'):
        products.extend(sorted(DATA.glob(pattern)))
    products=[p for p in products if not p.name.startswith('T9-copy-')]
    manifest={str(p.relative_to(DATA)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in products}
    write(DATA/'receipts/T9-copy-manifest.json',manifest)
    names=sorted(manifest)+['receipts/T9-copy-manifest.json']
    filelist=DATA/'receipts/T9-copy-files.txt';filelist.write_text('\n'.join(names)+'\n')
    for host in ('127x01','127x04'):
        subprocess.run(['ssh',host,'mkdir','-p',str(DATA)],check=True)
        subprocess.run(['rsync','-c','--files-from='+str(filelist),str(DATA)+'/',host+':'+str(DATA)+'/'],check=True)
        code='import hashlib,json;from pathlib import Path;p=Path('+repr(str(DATA))+');m=json.loads((p/"receipts/T9-copy-manifest.json").read_text());bad=[n for n,v in m.items() if not (p/n).exists() or (p/n).stat().st_size!=v["bytes"] or hashlib.sha256((p/n).read_bytes()).hexdigest()!=v["sha256"]];print(json.dumps({"files":len(m),"mismatches":bad}));assert not bad'
        result=subprocess.run(['ssh',host,str(ROOT/'.venv/bin/python'),'-'],input=code,text=True,capture_output=True,check=True)
        verdict=json.loads(result.stdout);write(DATA/f'receipts/T9-copy-{host}.json',verdict|{'host':host,'checksum_verified':True,'bytes':sum(v['bytes'] for v in manifest.values())})
        print(result.stdout,flush=True)
if __name__=='__main__':main()
