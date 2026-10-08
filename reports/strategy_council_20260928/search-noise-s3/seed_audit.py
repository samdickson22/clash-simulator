"""Retained-evidence seed audit; Python fallback because fleet has no rg."""
from pathlib import Path
import datetime,json,re,socket
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]

def proposed_seeds():
    worlds=[9732000001+1009*i for i in range(128)]+[9730800001+1009*i for i in range(56)]
    noise=[9832000001+1009*i for i in range(128)]+[9830800001+1009*i for i in range(56)]
    return {s+o for s in worlds for o in (0,100000,100001,100002,100003)}|{s+o for s in noise for o in (0,1,500,501,700,701)}|{9731100001,9731100003}

def audit():
    proposed=proposed_seeds();used=set();fields=archives=metadata=texts=0;errors=[];overlap=[];unavailable=[]
    field=re.compile(r'"[A-Za-z_]*seed"\s*:\s*(\d+)');numbers=re.compile(r'(?<!\d)\d{10}(?!\d)')
    for p in sorted((ROOT/'reports').rglob('*')):
        if HERE in p.parents or not p.is_file() and not p.is_symlink():continue
        if p.is_symlink() and not p.exists():
            unavailable.append(dict(path=str(p),target=str(p.readlink())));continue
        try:
            if p.suffix in ('.json','.jsonl','.log','.md','.txt','.toml','.yaml','.csv','.tsv','.py','.sh'):
                texts+=1
                with p.open(errors='replace') as stream:
                    for line in stream:
                        found=list(map(int,field.findall(line)));fields+=len(found);used.update(found)
                        hits={int(n) for n in numbers.findall(line)}&proposed
                        if hits:overlap.append(dict(path=str(p),seeds=sorted(hits)))
            elif p.suffix=='.npz':
                archives+=1
                with np.load(p,allow_pickle=False) as z:
                    for key in z.files:
                        found=set(map(int,re.findall(r'seed[_-]?(\d+)',key,re.I)))
                        if any(t in key.lower() for t in ('meta','config','seed','json')):
                            a=z[key]
                            if a.dtype.kind in ('U','S'):
                                for value in a.reshape(-1):
                                    if isinstance(value,bytes):value=value.decode()
                                    found.update(map(int,field.findall(str(value))))
                            elif 'seed' in key.lower() and a.dtype.kind in ('i','u'):found.update(map(int,a.reshape(-1)))
                        used.update(found);metadata+=len(found)
                        if found&proposed:overlap.append(dict(path=str(p),seeds=sorted(found&proposed)))
        except Exception as e:errors.append(dict(path=str(p),error=str(e)))
    return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),host=socket.gethostname(),seed_fields=fields,unique_seeds=len(used),text_files=texts,npz_archives=archives,metadata_seeds=metadata,unavailable_archives=unavailable,errors=errors,overlap=overlap,passed=not errors and not overlap,proposed=sorted(proposed))
if __name__=='__main__':
    x=audit();(HERE/f'seed-audit-{socket.gethostname().split(".")[0]}.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({k:x[k] for k in ('host','seed_fields','unique_seeds','text_files','npz_archives','errors','overlap','passed')}));assert x['passed']
