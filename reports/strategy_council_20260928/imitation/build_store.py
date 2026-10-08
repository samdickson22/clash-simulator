"""Build resumable per-role NPY mmap columns, preserving all source rows."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import socket
import time
import numpy as np
from replay_sidecars import DATA, HERE, sha, write, pins
from clasher.rl.contract_v5 import ContractV5ObservationBuilder

ROLES = ('train','dev','eval','eval_ood')


def source_metadata():
    role_path = DATA/'roles/c56_roles_v1.json'
    roles = json.loads(role_path.read_text())
    spec = json.loads((DATA/'eval/heldout_eval_spec_v1.json').read_text())
    assert sha(role_path) == spec['role_file_sha256']
    assert sha(DATA/'index/perspectives.jsonl.gz') == roles['index_sha256']
    with gzip.open(DATA/'index/perspectives.jsonl.gz','rt') as f:
        index = {f"{r['tag']}|{r['side']}":r for r in map(json.loads,f)}
    return roles,spec,index


def proxy(row):
    return (tuple(row['own_levels']),row['tower'],row['tower_level'])


def prepare(out, sidecar, smoke=None):
    roles,spec,index = source_metadata()
    train = [k for k,r in roles['roles'].items() if r=='train']
    proxy_counts = Counter(proxy(index[k]) for k in train)
    family_counts = Counter(roles['family'][k] for k in train)
    sample = sorted((k for k,r in roles['roles'].items() if r in ROLES),
                    key=lambda k:hashlib.sha256(('imitation-roundtrip-v1:'+k).encode()).digest())
    sample = set(sample[:math.ceil(len(sample)*.01)])
    counts = {r:dict(rows=0,entities=0,perspectives=0) for r in ROLES}
    units = []; mask_ids = {}; masks = []
    paths = [DATA/'recon/engine-v3'/f'{smoke}.npz'] if smoke else sorted((DATA/'recon/engine-v3').glob('*/shard-*.npz'))
    for number,path in enumerate(paths):
        key = str(path.relative_to(DATA/'recon/engine-v3')).removesuffix('.npz')
        with np.load(path,allow_pickle=False) as z:
            header = json.loads(z['header_json'].item())
            offsets = np.r_[0,np.cumsum(z['entity_counts'],dtype=np.int64)]
            table = z['mask_table']; mapping = []
            for row in table:
                packed = row.tobytes()
                if packed not in mask_ids:
                    mask_ids[packed] = len(masks); masks.append(row.copy())
                mapping.append(mask_ids[packed])
        items = []
        for summary in header['perspectives']:
            identity = f"{summary['match_id']}|{summary['side']}"
            role = roles['roles'][identity]
            if role not in ROLES: continue
            a = summary['row_offset']; b = a+summary['rows']; nentities = int(offsets[b]-offsets[a])
            weight = 1.
            if role == 'train':
                weight = min(1/math.sqrt(proxy_counts[proxy(index[identity])]),
                             1/math.sqrt(family_counts[roles['family'][identity]]))
            items.append(dict(identity=identity,role=role,source_start=a,rows=b-a,entities=nentities,
                              target_start=counts[role]['rows'],entity_start=counts[role]['entities'],
                              weight=weight,roundtrip=bool(smoke) or identity in sample,p16=index[identity]['p16'],summary=summary))
            counts[role]['rows'] += b-a; counts[role]['entities'] += nentities; counts[role]['perspectives'] += 1
        units.append(dict(key=key,mask_mapping=mapping,perspectives=items))
        if number%100==0: print(json.dumps(dict(planned=number,counts=counts)),flush=True)
    if not smoke: assert all(counts[r]['perspectives']==roles['counts'][r] for r in ROLES)
    out.mkdir(parents=True,exist_ok=True)
    np.save(out/'mask_table.npy',np.asarray(masks,dtype=np.uint8),allow_pickle=False)
    sidecar_pin = sidecar/'units'/f'{smoke}.json' if smoke else sidecar/'manifest.json'
    plan = dict(schema='clasher.imitation.packed.v1',counts=counts,units=units,smoke=smoke,
                roundtrip_perspectives=sum(c['perspectives'] for c in counts.values()) if smoke else len(sample),
                role_sha256=sha(DATA/'roles/c56_roles_v1.json'),eval_spec_sha256=sha(DATA/'eval/heldout_eval_spec_v1.json'),
                sidecar_manifest_sha256=sha(sidecar_pin),pins=pins(),
                builder_sources={n:sha(HERE/n) for n in ('build_store.py','packed_store.py')},
                weighting='minimum of train-only proxy and family inverse square roots (c=1), enforcing both caps; mode, forms, clamp and kill factors; unsupervised zero; epoch wait IPW stored separately')
    write(out/'plan.json',plan)
    return plan


def open_column(path,dtype,shape):
    if path.exists():
        arr = np.load(path,mmap_mode='r+',allow_pickle=False)
        assert arr.dtype==dtype and arr.shape==shape
        return arr
    return np.lib.format.open_memmap(path,mode='w+',dtype=dtype,shape=shape)


def build(out, sidecar, smoke=None):
    start = time.perf_counter(); cpu = time.process_time()
    assert json.loads((HERE/'data/receipts/T1-PASS.json').read_text())['passed']
    sidecar_pin = sidecar/'units'/f'{smoke}.json' if smoke else sidecar/'manifest.json'
    gate = json.loads(sidecar_pin.read_text())
    assert not any(gate['violations']) if smoke else gate['passed']
    plan = json.loads((out/'plan.json').read_text()) if (out/'plan.json').exists() else prepare(out,sidecar,smoke)
    assert plan['smoke']==smoke and plan['sidecar_manifest_sha256']==sha(sidecar_pin)
    assert plan['builder_sources']=={n:sha(HERE/n) for n in ('build_store.py','packed_store.py')}
    first = plan['units'][0]['key']
    with np.load(DATA/'recon/engine-v3'/f'{first}.npz') as z, np.load(sidecar/'sidecar'/f'{first}.npz') as d:
        schema = {n:(z[n].dtype,z[n].shape[1:]) for n in z.files if n not in ('header_json','mask_table')}
        schema.update({n:(d[n].dtype,d[n].shape[1:]) for n in d.files})
    schema.update(weights=(np.dtype('float32'),()),wait_ipw=(np.dtype('float32'),()),
                  source_mask_index=(np.dtype('int32'),()),source_unit=(np.dtype('int16'),()),
                  source_row=(np.dtype('int32'),()),p16=(np.dtype('bool'),()),entity_offsets=(np.dtype('int64'),()))
    stores = {}
    for role in ROLES:
        (out/role).mkdir(exist_ok=True)
        counts = plan['counts'][role]
        stores[role] = {n:open_column(out/role/f'{n}.npy',dtype,
                        ((counts['entities'] if n.startswith('flat_entity_') else counts['rows']+int(n=='entity_offsets')), *tail))
                        for n,(dtype,tail) in schema.items()}
    builder = ContractV5ObservationBuilder()
    _,spec,_ = source_metadata()
    checked = 0
    for number,unit in enumerate(plan['units']):
        key = unit['key']; receipt = out/'units'/f'{key}.json'
        if receipt.exists():
            checked += json.loads(receipt.read_text())['roundtrip_perspectives']; continue
        with np.load(DATA/'recon/engine-v3'/f'{key}.npz') as z, np.load(sidecar/'sidecar'/f'{key}.npz') as d:
            arrays = {n:z[n] for n in z.files if n not in ('header_json','mask_table')}
            source_masks = z['mask_table']
            for n in d.files:
                if n in arrays: assert arrays[n].tobytes()==d[n].tobytes(),(key,n)
                arrays[n] = d[n]
        offsets = np.r_[0,np.cumsum(arrays['entity_counts'],dtype=np.int64)]
        mapping = np.asarray(unit['mask_mapping'],np.int32)
        unit_checked = 0
        for item in unit['perspectives']:
            role=item['role']; target=stores[role]; summary=item['summary']
            a=item['source_start']; b=a+item['rows']; x=item['target_start']; y=x+item['rows']
            ea,eb=int(offsets[a]),int(offsets[b]); ex=item['entity_start']; ey=ex+item['entities']
            for n,values in arrays.items():
                if n.startswith('flat_entity_'): target[n][ex:ey]=values[ea:eb]
                elif n=='mask_index': target[n][x:y]=mapping[values[a:b]]
                else: target[n][x:y]=values[a:b]
            target['source_mask_index'][x:y]=arrays['mask_index'][a:b]
            target['entity_offsets'][x:y+1]=offsets[a:b+1]-ea+ex
            target['source_unit'][x:y]=number;target['source_row'][x:y]=np.arange(a,b)
            target['p16'][x:y]=item['p16']
            actions=arrays['expert_actions'][a:b]
            weights=np.full(b-a,item['weight'],np.float32)
            if summary['unreproduced_real_kill']: weights *= .5
            mode=summary['info'].get('battle_type','unknown')
            weights *= spec['bc_weighting_natural_arm']['mode'].get(mode,.5)
            tokens={builder.token_id(n,namespace='card_action') for n,form in zip(summary['own_deck'],summary['own_forms']) if form!='base'}
            play=np.flatnonzero(actions<2304)
            played=arrays['hand_ids'][a:b][play,actions[play]//576]
            weights[play[np.isin(played,list(tokens))]] *= .5
            if summary['first_clamp_tick'] is not None:
                weights[arrays['submitted_ticks'][a:b]>=summary['first_clamp_tick']] *= .5
            weights *= arrays['expert_action_supervision_valid'][a:b]
            target['weights'][x:y]=weights
            target['wait_ipw'][x:y]=np.where(actions==2304,4.,1.)
            if item['roundtrip']:
                for n,values in arrays.items():
                    if n.startswith('flat_entity_'): actual=target[n][ex:ey]; expected=values[ea:eb]
                    elif n=='mask_index': actual=target['source_mask_index'][x:y]; expected=values[a:b]
                    else: actual=target[n][x:y]; expected=values[a:b]
                    assert actual.dtype==expected.dtype and actual.shape==expected.shape and actual.tobytes()==expected.tobytes(),(key,n)
                table=np.load(out/'mask_table.npy',mmap_mode='r')
                assert table[target['mask_index'][x:y]].tobytes()==source_masks[arrays['mask_index'][a:b]].tobytes()
                unit_checked += 1
        for role in ROLES:
            for arr in stores[role].values(): arr.flush()
        write(receipt,dict(complete=True,roundtrip_perspectives=unit_checked))
        checked += unit_checked
        print(json.dumps(dict(built=number+1,unit=key,roundtrip=checked)),flush=True)
    assert checked==plan['roundtrip_perspectives']
    assert plan['builder_sources']=={n:sha(HERE/n) for n in ('build_store.py','packed_store.py')}
    for role in ROLES:
        count=plan['counts'][role]
        manifest=dict(role=role,rows=count['rows'],entities=count['entities'],perspective_count=count['perspectives'],
                      arrays={n:dict(dtype=str(a.dtype),shape=list(a.shape),sha256=sha(out/role/f'{n}.npy')) for n,a in stores[role].items()},
                      perspectives=[p for u in plan['units'] for p in u['perspectives'] if p['role']==role],
                      mask_table='../mask_table.npy',plan_sha256=sha(out/'plan.json'))
        write(out/role/'manifest.json',manifest)
    write(out/'manifest.json',dict(passed=not bool(smoke),smoke_passed=bool(smoke),schema=plan['schema'],roles=plan['counts'],
        roundtrip_perspectives=checked,roundtrip_exact=True,mask_table_sha256=sha(out/'mask_table.npy'),
        role_manifests={r:sha(out/r/'manifest.json') for r in ROLES},plan_sha256=sha(out/'plan.json'),
        role_file_sha256=plan['role_sha256'],eval_spec_sha256=plan['eval_spec_sha256'],sidecar_manifest_sha256=plan['sidecar_manifest_sha256'],
        wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--sidecar',type=Path,required=True)
    ap.add_argument('--smoke-unit',help='I/O verification of a pilot unit only; never emits passed=true')
    args=ap.parse_args();assert socket.gethostname()=='127x01'
    assert args.out.resolve().is_relative_to(HERE/'data')
    args.out.mkdir(parents=True,exist_ok=True);build(args.out,args.sidecar,args.smoke_unit)
