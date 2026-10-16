#!/usr/bin/env python3
"""Check completeness, deploy acceptance, provenance and cited source symbols."""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def main():
    p=argparse.ArgumentParser();p.add_argument('--dir',type=Path,default=Path(__file__).parent)
    p.add_argument('--source-root',type=Path);a=p.parse_args()
    rows=[json.loads(l) for l in (a.dir/'results.jsonl').read_text().splitlines()]
    pool=json.loads((a.dir/'pool.json').read_text());names={r['name'] for r in pool}
    assert len(names)==66
    keys=[(r['card'],r['scenario'],r['table'],r.get('offset_tiles')) for r in rows]
    assert len(keys)==len(set(keys))==620,(len(keys),len(set(keys)))
    hashes=set();interventions=Counter()
    for table in ('adapter','160402'):
        rr=[r for r in rows if r['table']==table]
        assert len(rr)==310
        natural=[r for r in rr if r['scenario']!='stationary_knight']
        assert len(natural)==196
        assert {r['card'] for r in natural}==names
        assert len([r for r in rr if r['scenario']=='stationary_knight'])==114
        for r in rr:
            for k in ('ours','rsim'):
                assert 'error' not in r[k],(r['card'],r['scenario'],table,k)
                if r['scenario']=='stationary_knight':
                    assert r[k]['deploy_ok']
                else:
                    assert all(d[-1] for d in r[k]['deployments'])
                    interventions.update({f'{k}:{n}':v for n,v in r[k]['counters'].items()})
            if r['scenario']!='stationary_knight':
                assert '/clasher-bot-runtime/r1/src/' in r['ours']['source']
                hashes.add(r['ours']['r1_battle_sha256'])
    assert len(hashes)==1
    summary=json.loads((a.dir/'summary.json').read_text())
    assert set(summary['cards'])==names
    causes=json.loads((a.dir/'causes.json').read_text())
    assert set(causes)==names,(names-set(causes),set(causes)-names)
    if a.source_root:
        assert hashlib.sha256((a.source_root/'src/clasher/battle.py').read_bytes()).hexdigest() in hashes
        for text in causes.values():
            for file,symbol in re.findall(r'`(src/clasher/[^`:]+)::([^`]+)`',text):
                path=a.source_root/file
                assert path.exists(),str(path)
                tree=ast.parse(path.read_text())
                symbols=set()
                def walk(nodes,prefix=''):
                    for node in nodes:
                        if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                            qual=prefix+node.name;symbols.update((qual,node.name));walk(node.body,qual+'.')
                        elif isinstance(node,ast.Assign):
                            symbols.update(prefix+t.id for t in node.targets if isinstance(t,ast.Name))
                walk(tree.body)
                assert symbol in symbols,(file,symbol)
    print(json.dumps(dict(rows=len(rows),cards=len(names),counts=summary['counts'],
                          accepted_all_deployments=True,r1_battle_sha256=next(iter(hashes)),
                          interventions=dict(interventions),source_symbols_checked=bool(a.source_root)),indent=2))


if __name__=='__main__':main()
