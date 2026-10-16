"""Reject partial/mixed class receipts; aggregate only completed exact-source runs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

TARGETS={'27/AreaEffect','88/AreaEffect','147/AreaEffect','200/AreaEffect','269/AreaEffect'}


def summarize(paths, approved_source, *, pilot=False):
    runs=[json.loads(p.read_text()) for p in paths]
    expected=5 if pilot else 122
    assert len(runs)==(1 if pilot else 4),len(runs)
    assert all(r['complete'] and r['result']=='PASS' and not r['failures'] for r in runs),'incomplete/failed run'
    cards=[c for r in runs for c in r['cards']]
    assert len(cards)==len(set(cards))==expected,(len(cards),len(set(cards)))
    assert all(r['full_pool']==(not pilot) for r in runs),'wrong card selection'
    assert all(len(r['scenarios'])==r['expected_scenarios']==len(r['cards'])*3 for r in runs)
    scenarios=[(s['card'],s['mode']) for r in runs for s in r['scenarios']]
    assert set(scenarios)=={(c,m) for c in cards for m in ('combat','death','lifetime')}
    assert len(scenarios)==len(set(scenarios))==expected*3
    assert all(s['seats']==[0,1] and s['engines']==['python','native'] for r in runs for s in r['scenarios'])
    assert all(r['ticks']>=1500 for r in runs),'shortened lifetime protocol'
    assert all(s['ticks']>=(1500 if s['mode']=='lifetime' else 450) for r in runs for s in r['scenarios'])
    assert all(r['source_sha256']==runs[0]['source_sha256'] for r in runs),'mixed source'
    expected_source=json.loads(approved_source.read_text())
    for r in runs:
        assert len(r['source_sha256'])==len(expected_source['source_sha256']),'source inventory mismatch'
        for suffix,expected_hash in expected_source['source_sha256'].items():
            matches=[v for path,v in r['source_sha256'].items() if path.endswith('/'+suffix)]
            assert matches==[expected_hash],('unapproved source',suffix,matches,expected_hash)
    assert all(r['template_inventory']==runs[0]['template_inventory'] for r in runs),'mixed template table'
    objects={};counts=Counter();buffs=Counter();materialized=set();targets={}
    for r in runs:
        counts.update(r['checks']);buffs.update(r['buffs']);materialized.update(r['native_materialized_carriers'])
        for key,value in r['objects'].items():
            record=objects.setdefault(key,dict(token_name=value['token_name'],kind=value['kind'],
                **{k:[] for k in ('cards','classes','names','engines','modes')}))
            assert record['token_name']==value['token_name'] and record['kind']==value['kind']
            for field in ('cards','classes','names','engines','modes'):
                record[field]=sorted(set(record[field]+value[field]))
        for key,value in r['target_paths'].items():
            assert key not in targets,'overlapping card shard'
            targets[key]=value
    assert set(targets)==TARGETS,(set(targets),TARGETS)
    assert TARGETS<=materialized and TARGETS<=set(objects),'unmaterialized/unobserved target'
    for key,value in targets.items():
        assert set(value['exact_translator_seats'])==set(value['native_board_seats'])=={0,1},(key,value)
        assert set(value['source_motion_outputs'])=={str(m) for m in range(7)}
        assert all(len(v)==1 for v in value['source_motion_outputs'].values()),(key,value)
        value['native_gameplay_emitted']='native' in objects[key]['engines']
        value['native_constructor_materialized']=True
        value['source_schema_exact']=all(v==[key] for v in value['source_motion_outputs'].values())
    if not pilot:
        assert set(runs[0]['config_objects'])<=set(objects),'config identity never observed'
        assert set(objects)<=materialized,'observed identity never materialized'
    return dict(result='PASS',scope='five-target pilot' if pilot else 'full class',cards=expected,
        scenarios=expected*3,seats=[0,1],failures=[],checks=dict(counts),total_checks=sum(counts.values()),
        source_sha256=runs[0]['source_sha256'],templates=runs[0]['templates'],
        approved_source_commit=expected_source['commit'],
        approved_source_manifest_sha256=hashlib.sha256(approved_source.read_bytes()).hexdigest(),
        translator_tables=runs[0]['translator_tables'],config_objects=len(runs[0]['config_objects']),
        objects=objects,object_kinds=dict(Counter(v['kind'] for v in objects.values())),
        buffs=dict(buffs),native_materialized_carriers=sorted(materialized),target_paths=targets,
        historical_template_kind_aliases=runs[0]['historical_template_kind_aliases'],
        native_actions='121/122 admitted; MergeMaiden excluded by frozen v5, Python zero-object definition audited',
        root_scope='Projected synthetic public-carrier board stress; native constructor materialization is distinct from native gameplay emission',
        inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pilot',action='store_true')
    ap.add_argument('--approved-source',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('inputs',type=Path,nargs='+');a=ap.parse_args()
    result=summarize(a.inputs,a.approved_source,pilot=a.pilot)
    with a.out.open('x') as f:f.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k in ('result','scope','cards','scenarios','total_checks','object_kinds')}))


if __name__=='__main__':main()
