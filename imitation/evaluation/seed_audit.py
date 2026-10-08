"""Hash and scan host seed provenance; fail closed on unreviewed formula ranges.

Run once on each authorized host. Merge checks raw inventories, all five hosts,
all proposed integers, and an explicit pre-outcome range-review receipt. This
separates automated exact scans from seed formulas that need human review.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import numpy as np

HOSTS={'127x01','127x03','127x04','127x05','127x08'}
TEXT={'.json','.jsonl','.log','.md','.txt','.toml','.yaml','.yml','.csv','.tsv','.py','.sh'}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def scan(root, seeds, excludes):
    result=dict(host=os.uname().nodename,proposed=seeds,files={},overlap=[],errors=[],formula_files=[])
    wanted=set(seeds)
    for path in sorted(root.rglob('*')):
        if not path.is_file() or any(path.resolve().is_relative_to(p) for p in excludes):continue
        if path.suffix not in TEXT|{'.npz','.gz'}:continue
        try:
            result['files'][str(path.resolve())]=sha(path)
            found=set()
            if path.suffix=='.npz':
                with np.load(path,allow_pickle=False) as z:
                    for key in z.files:
                        if not any(s in key.lower() for s in ('seed','meta','config','json')):continue
                        a=z[key]
                        if 'seed' in key.lower() and a.dtype.kind in 'iu':found.update(map(int,a.flat))
                        elif a.dtype.kind in 'SU':
                            found.update(map(int,re.findall(r'(?<![\w.])\d{5,}(?![\w.])',str(a.tolist()))))
            else:
                if path.suffix=='.gz':
                    if not path.name.endswith(('.json.gz','.jsonl.gz')):continue
                    with gzip.open(path,'rt') as f: text=f.read()
                else:text=path.read_text(errors='strict')
                # Exact literals in any receipt field, including nested/list seeds.
                found.update(map(int,re.findall(r'(?<![\w.])\d{5,}(?![\w.])',text.replace('_',''))))
                if re.search(r'(?i)seed[^\n]*(?:\+|\*|range\()',text):
                    result['formula_files'].append(str(path.resolve()))
            for s in sorted(found&wanted):result['overlap'].append({'path':str(path),'seed':s})
        except Exception as error:result['errors'].append({'path':str(path),'error':str(error)})
    result['exact_scan_passed']=not(result['errors'] or result['overlap'])
    return result


def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('scan');p.add_argument('--root',type=Path,action='append',required=True)
    p.add_argument('--seeds',type=Path,required=True);p.add_argument('--exclude',type=Path,action='append',default=[])
    p.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('merge');p.add_argument('--inventory',type=Path,action='append',required=True)
    p.add_argument('--range-review',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.command=='scan':
        seeds=json.loads(args.seeds.read_text());parts=[scan(root,seeds,[p.resolve() for p in args.exclude]) for root in args.root]
        value=parts[0]
        for part in parts[1:]:
            value['files'].update(part['files'])
            for key in ('errors','overlap','formula_files'):value[key]+=part[key]
        value['exact_scan_passed']=not(value['errors'] or value['overlap'])
    else:
        inventories=[json.loads(p.read_text()) for p in args.inventory]
        review=json.loads(args.range_review.read_text())
        hosts={r['host'] for r in inventories}
        if hosts!=HOSTS or len(inventories)!=5:raise ValueError('exactly five authorized host inventories required')
        if any(r['proposed']!=inventories[0]['proposed'] for r in inventories):raise ValueError('seed sets differ')
        hashes={str(p):sha(p) for p in args.inventory}
        if not(review.get('complete') and review.get('no_overlap') and review.get('inventory_hashes')==hashes
               and review.get('reviewed_formula_files')=={r['host']:r['formula_files'] for r in inventories}):
            raise ValueError('missing or mismatched seed range review')
        value=dict(hosts=sorted(hosts),proposed=inventories[0]['proposed'],files=hashes,
                   errors=[e for r in inventories for e in r['errors']],
                   overlap=[e for r in inventories for e in r['overlap']],complete_inventory=True,
                   range_review_sha256=sha(args.range_review))
        value['passed']=not(value['errors'] or value['overlap'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with open(args.output,'x') as f:json.dump(value,f,indent=2)
    print(json.dumps({k:v for k,v in value.items() if k in ('host','hosts','passed','exact_scan_passed','errors','overlap')}))


if __name__=='__main__':main()
