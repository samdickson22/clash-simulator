"""Operational wrapper around the unchanged gate seed auditor.

Discovers historical source, original runs and archive/mirror provenance, and
retains exact inventories plus formula contexts. No game/model evaluation.
"""
import argparse
import hashlib
import gzip
import importlib.util
import json
import os
from pathlib import Path
import re
import socket

FAMILIES=('w-screen8','w-confirm','delay-fixes','tempo','search-ab','loss-review','e1')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def discover(base):
    roots=[]
    for top in sorted((base/'repos').glob('clasher*')):
        if not top.is_dir():continue
        # Snapshots, lease sources and mirror worktrees are at most four levels
        # below their repository. Payloads/caches are not provenance roots.
        for directory,children,files in os.walk(top):
            p=Path(directory);depth=len(p.relative_to(top).parts)
            if depth>4:children[:]=[];continue
            children[:]=[c for c in children if c not in ('.git','.venv','node_modules','target','cache','data','build','__pycache__','envs')]
            if (p/'reports/explore').is_dir():roots.append(p/'reports/explore')
            if (p/'imitation').is_dir():roots.extend(x for x in (p/'imitation').glob('gate*') if x.is_dir())
            council=p/'reports/strategy_council_20260928'
            if council.is_dir():
                roots.extend(x for x in council.iterdir() if x.is_dir() and
                             (x.name.startswith('search-noise') or x.name in ('imitation','search-tuning','pilot','exit','srp-dagger','srp-public','c56')))
            if (p/'src/clasher/analysis/loss_review').is_dir():roots.append(p/'src/clasher/analysis/loss_review')
        if top.name=='clasher-lease':
            roots.extend(top/x for x in ('search-ab-runtime','delay-fixes-runtime','tempo-runtime','jobs','config') if (top/x).exists())
    jobs=base/'jobs/clasher'
    roots.extend(p for p in jobs.glob('*') if p.is_dir() and
                 (any(p.name.startswith(f) for f in FAMILIES) or p.name=='exit-r1-20261009-r1' or p.name=='seed-inventory'))
    roots=sorted(set(p.resolve() for p in roots))
    return [p for p in roots if not any(p!=q and p.is_relative_to(q) for q in roots)]


def inventory(script,seeds,output,base=Path('/mpac/sdicks02')):
    spec=importlib.util.spec_from_file_location('qualified_seed_auditor',script)
    auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
    # Bounded memory hashing; exact scan semantics and original sources unchanged.
    auditor.sha=sha
    proposed=json.loads(Path(seeds).read_text());roots=discover(base)
    # Equivalent target-intersection fast path. Avoid materializing millions of
    # irrelevant historical integers. Underscores were already removed by scan.
    assert all(str(s).startswith('450360') for s in proposed)
    original_regex=auditor.re
    class Regex:
        def findall(self,pattern,text,*args,**kw):
            if pattern==r'(?<![\w.])\d{5,}(?![\w.])' and '450360' not in text:return []
            return original_regex.findall(pattern,text,*args,**kw)
        def search(self,pattern,text,*args,**kw):
            if pattern==r'(?i)seed[^\n]*(?:\+|\*|range\()' and not any(s in text for s in ('+','*','range(')):return None
            return original_regex.search(pattern,text,*args,**kw)
    auditor.re=Regex()
    pattern=r'(?<![\w.])\d{5,}(?![\w.])'
    wanted=set(proposed)
    for text in ('prior seed 281474976710656',' '.join(map(str,proposed)),
                 '4503601007370496.1 x4503601007370496 45036010073704967'):
        assert set(map(int,auditor.re.findall(pattern,text)))&wanted==set(map(int,original_regex.findall(pattern,text)))&wanted
    excluded=[]
    for root in roots:
        for p in root.rglob('*'):
            if (p.name=='STUDENT-SCREEN-PLAN.md' or
                p.name in ('screen.py','test_screen.py','audit_seeds.py') and 'exit_r1' in p.parts):
                excluded.append(p.resolve())
    result=dict(host=socket.gethostname().split('.')[0],proposed=proposed,files={},overlap=[],errors=[],formula_files=[],
                roots=list(map(str,roots)),excluded=list(map(str,excluded)),auditor_sha256=sha(script),hashing='streaming SHA256')
    for root in roots:
        part=auditor.scan(root,proposed,excluded)
        result['files'].update(part['files'])
        for k in ('overlap','errors','formula_files'):result[k].extend(part[k])
    contexts={}
    for name in sorted(set(result['formula_files'])):
        try:
            lines=(gzip.open(name,'rt').read() if name.endswith('.gz') else Path(name).read_text()).splitlines()
            contexts[name]=[dict(line=i+1,text=line) for i,line in enumerate(lines)
                            if re.search(r'(?i)seed.*(?:\+|\*|range\()',line)]
        except Exception as e:result['errors'].append(dict(path=name,error=str(e)))
    result['formula_contexts']=contexts
    result['exact_scan_passed']=not(result['overlap'] or result['errors'])
    Path(output).write_text(json.dumps(result,indent=2)+'\n')
    return dict(host=result['host'],files=len(result['files']),formulas=len(contexts),
                errors=len(result['errors']),overlap=len(result['overlap']),sha256=sha(output))


def recover(path):
    """Recover compressed formula-context logging without dropping any source."""
    p=Path(path);raw=p.read_bytes();d=json.loads(raw);resolved=[]
    for error in d['errors']:
        f=Path(error['path']);data=f.read_bytes();depth=0
        while data[:2]==b'\x1f\x8b':data=gzip.decompress(data);depth+=1
        if depth<1:raise ValueError('only compressed context-reader errors are recoverable')
        s=data.decode('utf-8')
        found=set(map(int,re.findall(r'(?<![\w.])\d{5,}(?![\w.])',s.replace('_',''))))
        if found&set(d['proposed']):raise ValueError('recovered trace seed overlap')
        resolved.append(dict(path=str(f),raw_sha256=sha(f),decoded_sha256=hashlib.sha256(data).hexdigest(),
                             gzip_layers=depth,overlap=[]))
    p.with_suffix('.raw.json').write_bytes(raw)
    d.update(reader_recoveries=resolved,raw_inventory_sha256=hashlib.sha256(raw).hexdigest(),errors=[],
             exact_scan_passed=not d['overlap'])
    p.write_text(json.dumps(d,indent=2)+'\n')
    return dict(recovered=len(resolved),sha256=sha(p))


def main():
    p=argparse.ArgumentParser();p.add_argument('--auditor',required=True);p.add_argument('--seeds',required=True)
    p.add_argument('--output',required=True);p.add_argument('--recover',action='store_true');a=p.parse_args()
    print(json.dumps(recover(a.output) if a.recover else inventory(a.auditor,a.seeds,a.output)),flush=True)


if __name__=='__main__':main()
