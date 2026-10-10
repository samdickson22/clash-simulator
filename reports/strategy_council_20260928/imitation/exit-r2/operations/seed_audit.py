"""Read only Clasher provenance; stream hashes and literal/range evidence."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import socket
import subprocess
import time

RANGES={'h2h':(4503601507370496,256),'paired':(4503601517370496,600),
        'smoke':(4503601527370496,32),'dagger':(4503601707370496,32768)}
OFFSETS=(0,13,100000,100001,100002,100003,271828,271829)
TEXT={'.json','.jsonl','.log','.md','.txt','.toml','.yaml','.yml','.csv','.tsv','.py','.sh','.gz'}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1<<20),b''):h.update(data)
    return h.hexdigest()

def hits(seed):
    return [name for name,(base,count) in RANGES.items()
            if any(base+offset<=seed<base+offset+count for offset in OFFSETS)]

def within(path,root):return path==root or root in path.parents

def provenance_roots(base):
    """Same provenance families as the sealed r1 auditor; no bulk decision traces."""
    roots=[]
    families=('w-screen8','w-confirm','delay-fixes','tempo','search-ab','loss-review','e1','exit-r1')
    for top in sorted((base/'repos').glob('clasher*')):
        if not top.is_dir():continue
        for directory,children,names in os.walk(top):
            p=Path(directory);depth=len(p.relative_to(top).parts)
            if depth>4:children[:]=[];continue
            children[:]=[c for c in children if c not in ('.git','.venv','node_modules','target','cache','data','build','__pycache__','envs')]
            if (p/'reports/explore').is_dir():roots.append(p/'reports/explore')
            if (p/'imitation').is_dir():roots.extend(x for x in (p/'imitation').glob('gate*') if x.is_dir())
            council=p/'reports/strategy_council_20260928'
            if council.is_dir():roots.extend(x for x in council.iterdir() if x.is_dir() and
                (x.name.startswith('search-noise') or x.name in ('imitation','search-tuning','pilot','exit','srp-dagger','srp-public','c56')))
            if (p/'src/clasher/analysis/loss_review').is_dir():roots.append(p/'src/clasher/analysis/loss_review')
        if top.name=='clasher-lease':roots.extend(top/x for x in ('search-ab-runtime','delay-fixes-runtime','tempo-runtime','jobs','config') if (top/x).exists())
    roots.extend(x for x in (base/'jobs/clasher').glob('*') if x.is_dir() and
        (x.name.startswith(families) or x.name=='seed-inventory'))
    unique=sorted(set(x.resolve() for x in roots))
    return [x for x in unique if not any(x!=y and within(x,y) for y in unique)]

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    p.add_argument('--root',action='append',default=[]);p.add_argument('--discover',action='store_true');p.add_argument('--exclude',action='append',default=[])
    a=p.parse_args();started=time.monotonic();excluded=[Path(x).resolve() for x in a.exclude]
    if a.discover:a.root.extend(map(str,provenance_roots(Path('/mpac/sdicks02'))))
    if not a.root:p.error('at least one provenance root required')
    files={};overlap=[];errors=[];declarations=[];formulas=[];seen=set()
    for root in map(Path,a.root):
        if not root.exists():errors.append({'path':str(root),'error':'missing root'});continue
        for directory,children,names in os.walk(root):
            children[:]=[c for c in children if c not in ('.git','.venv','venv','cache','envs','node_modules','target','__pycache__','build','data','datasets')
                         and not any(within((Path(directory)/c).resolve(),x) for x in excluded)]
            for name in names:
                path=Path(directory)/name
                if path.suffix not in TEXT:continue
                resolved=path.resolve()
                if resolved in seen or any(within(resolved,x) for x in excluded):continue
                seen.add(resolved)
                try:
                    files[str(resolved)]=sha(path)
                    opener=gzip.open if name.endswith(('.json.gz','.jsonl.gz')) else open
                    if path.suffix=='.gz' and opener is open:continue
                    with opener(path,'rt',encoding='utf-8') as f:
                        for line_no,line in enumerate(f,1):
                            compact=line.replace('_','')
                            if '450360' in compact:
                                for value in re.findall(r'(?<![\w.])450360\d{10}(?![\w.])',compact):
                                    seed=int(value)
                                    declarations.append({'path':str(resolved),'line':line_no,'seed':seed})
                                    if hits(seed):overlap.append({'path':str(resolved),'line':line_no,'seed':seed,'ranges':hits(seed)})
                            if 'seed' in line.lower() and any(s in line for s in ('+','*','range(')):
                                formulas.append({'path':str(resolved),'line':line_no,'text':line.rstrip()[:1000]})
                except Exception as e:errors.append({'path':str(resolved),'error':str(e)})
    usage=resource.getrusage(resource.RUSAGE_SELF)
    result={'utc':subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),
            'host':socket.gethostname(),'roots':a.root,'excluded':a.exclude,'ranges':RANGES,'helper_offsets':OFFSETS,
            'files':files,'overlap':overlap,'errors':errors,'declarations':declarations,'formula_contexts':formulas,
            'exact_scan_passed':not(overlap or errors),'cpu_seconds':usage.ru_utime+usage.ru_stime,
            'wall_seconds':time.monotonic()-started}
    Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('utc','host','exact_scan_passed','errors','overlap','cpu_seconds','wall_seconds')}),flush=True)

if __name__=='__main__':main()
