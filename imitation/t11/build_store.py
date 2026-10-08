"""Build C56 union S122 without changing any upstream data or code.

Run only on 127x01. Source unit hashes are checked before reading. Parallel
writers own disjoint row/entity intervals; durable unit receipts permit resume.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
import math
import mmap
import multiprocessing as mp
import os
from pathlib import Path
import socket
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
IM = ROOT/'reports/strategy_council_20260928/imitation'
DATA = IM/'data'
C56 = IM.parent/'c56/data'
sys.path.insert(0, str(IM))
from replay_sidecars import sha, write
from build_store import open_column, proxy
from clasher.rl.contract_v5 import ContractV5ObservationBuilder

ROLES = ('train', 'dev', 'eval', 'eval_ood')
THIN_SALT = 't11-s122-store-waits-v1:'
META = {}
OUT = None
STORES = None
SCHEMA = None


def read(p):
    return json.loads(Path(p).read_text())


def hash64(v):
    x = np.asarray(v, np.uint64).copy()
    with np.errstate(over='ignore'):
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xbf58476d1ce4e5b9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94d049bb133111eb)
    return x ^ (x >> np.uint64(31))


def selected(summary, actions, corpus, role):
    a = summary['row_offset']; b = a + summary['rows']
    ix = np.arange(a, b, dtype=np.int64)
    if corpus == 's122' and role == 'train':
        identity = summary['match_id']+'|'+summary['side']
        salt = int.from_bytes(hashlib.sha256((THIN_SALT+identity).encode()).digest()[:8], 'little')
        keep = (hash64(np.arange(b-a, dtype=np.uint64) ^ np.uint64(salt)) >> np.uint64(63)) == 0
        ix = ix[(actions[a:b] != 2304) | keep]
    return ix


def scan_unit(job):
    number, corpus, key, raw, side, raw_hash, side_hash = job
    assert sha(raw) == raw_hash and sha(side) == side_hash, key
    with np.load(raw, allow_pickle=False) as z:
        header = json.loads(z['header_json'].item())
        actions, ec = z['expert_actions'], z['entity_counts']
        masks = z['mask_table']
    items = []
    seen = []
    for summary in header['perspectives']:
        identity = summary['match_id']+'|'+summary['side']; seen.append(identity)
        info = META[identity]
        if not info['eligible']:
            continue
        role = info['role']; ix = selected(summary, actions, corpus, role)
        assert len(ix), ('empty retained perspective', identity)
        items.append(dict(identity=identity, role=role, corpus=corpus,
                          source_start=summary['row_offset'], source_rows=summary['rows'],
                          rows=len(ix), entities=int(ec[ix].sum()),
                          retained_waits=int((actions[ix] == 2304).sum()),
                          source_waits=int((actions[summary['row_offset']:summary['row_offset']+summary['rows']] == 2304).sum()),
                          weight=info['weight'], roundtrip=info['roundtrip'], p16=info['p16'],
                          flags=info['flags'], summary=summary))
    return dict(number=number, corpus=corpus, key=key, raw=str(raw), sidecar=str(side),
                raw_sha256=raw_hash, sidecar_sha256=side_hash, perspectives=items,
                seen=seen), masks


def prepare(out, workers, smoke):
    global META
    roles = read(DATA/'roles/s122_roles_v2.json'); old = read(C56/'roles/c56_roles_v1.json')
    t9 = read(DATA/'receipts/T9-PASS.json'); t10 = read(DATA/'receipts/T10-PASS.json')
    assert t9['roles_v2_sha256'] == sha(DATA/'roles/s122_roles_v2.json')
    assert t10['passed'] and t10['errors'] == 0 and not any(t10['violations'])
    assert roles['v1_sha256'] == sha(C56/'roles/c56_roles_v1.json')
    assert all(roles['roles'][k] == v for k, v in old['roles'].items())
    assert Counter(roles['roles'].values()) == roles['counts']
    excluded = set(roles['v2_actor_ineligible_frozen_c56_keys'])
    oldmeta = read(DATA/'index/c56-v2-metadata.json')
    assert excluded == set(oldmeta['actor_excluded_3m_keys'])
    index = {}
    for corpus, base in [('c56', C56), ('s122', DATA)]:
        assert sha(base/'index/perspectives.jsonl.gz') == (old if corpus == 'c56' else roles)['index_sha256']
        with gzip.open(base/'index/perspectives.jsonl.gz', 'rt') as f:
            for line in f:
                r = json.loads(line); identity = r['tag']+'|'+r['side']
                assert identity not in index
                ineligible = 'three-musketeers' in r['own_base']+r['opponent_base']
                assert ineligible == (identity in excluded)
                r['corpus'] = corpus; index[identity] = r
    assert set(index) == set(roles['roles'])
    eligible = {k for k, r in roles['roles'].items() if r in ROLES and k not in excluded}
    train = [k for k in eligible if roles['roles'][k] == 'train']
    pc = Counter(proxy(index[k]) for k in train)
    fc = Counter(roles['family'][k] for k in train)
    sample = set(sorted(eligible, key=lambda k: hashlib.sha256(('t11-roundtrip-v1:'+k).encode()).digest())[:math.ceil(.01*len(eligible))])
    expected = {r:Counter(index[k]['corpus'] for k in eligible if roles['roles'][k] == r) for r in ROLES}
    train_matches = {k.rsplit('|', 1)[0] for k in train}
    heldout_matches = {k.rsplit('|', 1)[0] for k in eligible if roles['roles'][k] != 'train'}
    assert not train_matches & heldout_matches
    for k, r in index.items():
        role = roles['roles'][k]
        META[k] = dict(role=role, eligible=k in eligible, p16=r['p16'],
                       flags=r.get('flags', oldmeta['flagged'].get(k, {'battle_healer':False, 'mirror':False})),
                       weight=1.,
                       roundtrip=smoke or k in sample)
        if k in eligible and role == 'train':
            META[k]['weight'] = min(1/math.sqrt(pc[proxy(r)]), 1/math.sqrt(fc[roles['family'][k]]))
    del index
    cm = read(DATA/'c56-sidecars-v1/manifest.json'); sm = read(DATA/'recon/engine-v3-s122/manifest.json')
    assert cm['passed'] and sm['passed'] and cm['perspectives'] == 82231 and sm['perspectives'] == 333934
    jobs = []
    for p in sorted((C56/'recon/engine-v3').glob('*/shard-*.npz')):
        key = str(p.relative_to(C56/'recon/engine-v3')).removesuffix('.npz')
        receipt = read(DATA/'c56-sidecars-v1/units'/f'{key}.json')
        name = f'sidecar/{key}.npz'
        jobs.append((len(jobs), 'c56', key, p, DATA/'c56-sidecars-v1'/name, receipt['original_sha256'], cm['files'][name]))
    sbase = DATA/'recon/engine-v3-s122'
    for p in sorted(sbase.glob('shard-*.npz')):
        key = p.stem; name = f'recon/engine-v3-s122/{key}.npz'; side = f'recon/engine-v3-s122/sidecar/{key}.npz'
        jobs.append((len(jobs), 's122', key, p, sbase/'sidecar'/p.name, sm['files'][name]['sha256'], sm['files'][side]['sha256']))
    if smoke:
        jobs = [jobs[0], next(j for j in jobs if j[1] == 's122')]
        jobs = [(i, *j[1:]) for i,j in enumerate(jobs)]
    counts = {r:dict(rows=0, entities=0, perspectives=0, source_rows=0, retained_waits=0, source_waits=0, c56=0, s122=0) for r in ROLES}
    masks = []; mask_ids = {}; units = []; seen = set(); checked = 0
    with ProcessPoolExecutor(workers, mp_context=mp.get_context('fork')) as pool:
        for unit, table in pool.map(scan_unit, jobs, chunksize=1):
            assert not seen.intersection(unit['seen']); seen.update(unit.pop('seen'))
            mapping = []
            for row in table:
                b = row.tobytes()
                if b not in mask_ids: mask_ids[b] = len(masks); masks.append(row)
                mapping.append(mask_ids[b])
            unit['mask_mapping'] = mapping
            for item in unit['perspectives']:
                c = counts[item['role']]; item['target_start'] = c['rows']; item['entity_start'] = c['entities']
                for k in ('rows', 'entities', 'source_rows', 'retained_waits', 'source_waits'): c[k] += item[k]
                c['perspectives'] += 1; c[item['corpus']] += 1; checked += item['roundtrip']
            units.append(unit)
            if len(units)%100 == 0: print(json.dumps({'stage':'plan', 'units':len(units)}), flush=True)
    if not smoke:
        assert seen == set(roles['roles'])
        assert all(all(counts[r][corpus] == expected[r][corpus] for corpus in ('c56','s122')) for r in ROLES)
        assert checked == len(sample)
    np.save(out/'mask_table.npy', np.asarray(masks, np.uint8), allow_pickle=False)
    input_paths = [DATA/'roles/s122_roles_v2.json', C56/'roles/c56_roles_v1.json', C56/'eval/heldout_eval_spec_v1.json',
                   DATA/'index/c56-v2-metadata.json', DATA/'receipts/T9-PASS.json', DATA/'receipts/T10-PASS.json',
                   DATA/'c56-sidecars-v1/manifest.json', sbase/'manifest.json', DATA/'receipts/T3-PASS.json']
    inputs = {str(p.relative_to(ROOT)):sha(p) for p in input_paths}
    sidecar_hash = hashlib.sha256(json.dumps({k:v for k,v in inputs.items() if k.endswith('/manifest.json')}, sort_keys=True).encode()).hexdigest()
    plan = dict(schema='clasher.imitation.packed.v1', version='v2', smoke=smoke, counts=counts, units=units,
                roundtrip_perspectives=checked, inputs=inputs, builder_sha256=sha(__file__),
                role_sha256=sha(DATA/'roles/s122_roles_v2.json'), eval_spec_sha256=sha(C56/'eval/heldout_eval_spec_v1.json'),
                sidecar_manifest_sha256=sidecar_hash, raw_role_counts=roles['counts'],
                excluded_3m_by_role=dict(Counter(roles['roles'][k] for k in excluded)),
                eligible_expected_by_role=expected, leak_check={'train_heldout_match_violations':0,'v1_assignments_unchanged':True},
                thinning={'corpus':'s122','role':'train','wait_keep_probability':.5,'salt':THIN_SALT,
                          'hash':'sha256 identity first8 little-endian xor perspective-local row ordinal, SplitMix64 high bit zero',
                          'stored_wait_weight':2,'epoch_retained_wait_probability':.5,'epoch_c56_wait_probability':.25})
    write(out/'plan.json', plan)
    META = {}
    return plan


def init_writer(out, schema):
    global STORES, SCHEMA, OUT
    OUT = Path(out); SCHEMA = schema
    STORES = {r:{n:np.load(OUT/r/f'{n}.npy', mmap_mode='r+') for n in schema} for r in ROLES}


def write_unit(unit):
    receipt = OUT/'units'/f"{unit['number']:05d}.json"
    unit_hash = hashlib.sha256(json.dumps(unit, sort_keys=True).encode()).hexdigest()
    if receipt.exists():
        r = read(receipt); assert r['unit_sha256'] == unit_hash and r['complete']; return r
    assert sha(unit['raw']) == unit['raw_sha256'] and sha(unit['sidecar']) == unit['sidecar_sha256']
    with np.load(unit['raw'], allow_pickle=False) as z, np.load(unit['sidecar'], allow_pickle=False) as d:
        arrays = {n:z[n] for n in z.files if n not in ('header_json','mask_table')}; source_masks = z['mask_table']
        for n in d.files:
            if n in arrays: assert arrays[n].tobytes() == d[n].tobytes()
            arrays[n] = d[n]
    offsets = np.r_[0, np.cumsum(arrays['entity_counts'], dtype=np.int64)]
    mapping = np.asarray(unit['mask_mapping'], np.int32)
    builder = ContractV5ObservationBuilder(); spec = read(C56/'eval/heldout_eval_spec_v1.json')
    checked = 0; touched = set()
    for item in unit['perspectives']:
        role = item['role']; touched.add(role); target = STORES[role]; summary = item['summary']
        ix = selected(summary, arrays['expert_actions'], unit['corpus'], role)
        x = item['target_start']; y = x+item['rows']; ex = item['entity_start']; ey = ex+item['entities']
        ec = arrays['entity_counts'][ix].astype(np.int64)
        ends = np.r_[0, np.cumsum(ec)]
        entities = np.repeat(offsets[ix], ec) + np.arange(ends[-1]) - np.repeat(ends[:-1], ec)
        assert len(ix) == item['rows'] and len(entities) == item['entities']
        for n, v in arrays.items():
            if n.startswith('flat_entity_'): target[n][ex:ey] = v[entities]
            elif n == 'mask_index': target[n][x:y] = mapping[v[ix]]
            else: target[n][x:y] = v[ix]
        target['source_mask_index'][x:y] = arrays['mask_index'][ix]
        target['entity_offsets'][x:y] = ends[:-1]+ex
        if y == len(target['entity_offsets'])-1: target['entity_offsets'][y] = ey
        target['source_unit'][x:y] = unit['number']; target['source_row'][x:y] = ix
        target['p16'][x:y] = item['p16']; target['corpus_s122'][x:y] = unit['corpus'] == 's122'
        act = arrays['expert_actions'][ix]; weights = np.full(len(ix), item['weight'], np.float32)
        if summary['unreproduced_real_kill']: weights *= .5
        weights *= spec['bc_weighting_natural_arm']['mode'].get(summary['info'].get('battle_type','unknown'), .5)
        tokens = {builder.token_id(n, namespace='card_action') for n,f in zip(summary['own_deck'],summary['own_forms']) if f != 'base'}
        plays = np.flatnonzero(act<2304); played = arrays['hand_ids'][ix][plays, act[plays]//576]
        weights[plays[np.isin(played,list(tokens))]] *= .5
        if summary['first_clamp_tick'] is not None: weights[arrays['submitted_ticks'][ix]>=summary['first_clamp_tick']] *= .5
        weights *= arrays['expert_action_supervision_valid'][ix]
        if unit['corpus'] == 's122' and role == 'train': weights[act==2304] *= 2
        target['weights'][x:y] = weights; target['wait_ipw'][x:y] = np.where(act==2304, 4., 1.)
        if item['roundtrip']:
            for n,v in arrays.items():
                expected = v[entities] if n.startswith('flat_entity_') else v[ix]
                actual = target[n][ex:ey] if n.startswith('flat_entity_') else target['source_mask_index' if n=='mask_index' else n][x:y]
                assert actual.dtype == expected.dtype and actual.shape == expected.shape and actual.tobytes() == expected.tobytes(), (item['identity'],n)
            table = np.load(OUT/'mask_table.npy', mmap_mode='r')
            assert table[target['mask_index'][x:y]].tobytes() == source_masks[arrays['mask_index'][ix]].tobytes()
            checked += 1
    # Flush BEFORE publication; resume only skips durably completed units.
    for role in touched:
        for a in STORES[role].values():
            a.flush(); a._mmap.madvise(mmap.MADV_DONTNEED)
    r = dict(complete=True, unit_sha256=unit_hash, roundtrip_perspectives=checked, number=unit['number'])
    write(receipt,r); return r


def hash_column(job):
    role, name, out = job; p = Path(out)/role/f'{name}.npy'; a = np.load(p, mmap_mode='r')
    return role,name,dict(dtype=str(a.dtype),shape=list(a.shape),sha256=sha(p),bytes=p.stat().st_size)


def main():
    global OUT
    p = argparse.ArgumentParser(); p.add_argument('--out',type=Path,required=True); p.add_argument('--workers',type=int,default=8)
    p.add_argument('--smoke',action='store_true'); args = p.parse_args()
    assert socket.gethostname() == '127x01' and 1 <= args.workers <= 12
    OUT = args.out.resolve(); assert OUT.is_relative_to(DATA); OUT.mkdir(parents=True,exist_ok=True)
    start = time.monotonic()
    plan = read(OUT/'plan.json') if (OUT/'plan.json').exists() else prepare(OUT,args.workers,args.smoke)
    assert plan['builder_sha256'] == sha(__file__) and plan['smoke'] == args.smoke
    assert all(sha(ROOT/n) == h for n,h in plan['inputs'].items())
    first = plan['units'][0]
    with np.load(first['raw']) as z, np.load(first['sidecar']) as d:
        schema = {n:(z[n].dtype,z[n].shape[1:]) for n in z.files if n not in ('header_json','mask_table')}
        schema.update({n:(d[n].dtype,d[n].shape[1:]) for n in d.files})
    schema.update(weights=(np.dtype('float32'),()),wait_ipw=(np.dtype('float32'),()),source_mask_index=(np.dtype('int32'),()),
                  source_unit=(np.dtype('int16'),()),source_row=(np.dtype('int32'),()),p16=(np.dtype('bool'),()),
                  corpus_s122=(np.dtype('bool'),()),entity_offsets=(np.dtype('int64'),()))
    for role in ROLES:
        (OUT/role).mkdir(exist_ok=True); count = plan['counts'][role]
        for n,(dtype,tail) in schema.items():
            length = count['entities'] if n.startswith('flat_entity_') else count['rows']+int(n=='entity_offsets')
            a = open_column(OUT/role/f'{n}.npy',dtype,(length,*tail)); a.flush(); del a
    checked = 0
    with ProcessPoolExecutor(args.workers, mp_context=mp.get_context('fork'), initializer=init_writer, initargs=(str(OUT),schema)) as pool:
        for i,r in enumerate(pool.map(write_unit,plan['units'],chunksize=1)):
            checked += r['roundtrip_perspectives']
            if i%50 == 0: print(json.dumps({'stage':'build','units':i+1,'roundtrip':checked}),flush=True)
    assert checked == plan['roundtrip_perspectives']
    manifests = {r:{} for r in ROLES}
    with ProcessPoolExecutor(min(args.workers,4), mp_context=mp.get_context('fork')) as pool:
        for role,n,info in pool.map(hash_column,[(r,n,str(OUT)) for r in ROLES for n in schema]): manifests[role][n]=info
    for role in ROLES:
        count = plan['counts'][role]
        write(OUT/role/'manifest.json',dict(role=role,rows=count['rows'],entities=count['entities'],perspective_count=count['perspectives'],
              arrays=manifests[role],perspectives=[i for u in plan['units'] for i in u['perspectives'] if i['role']==role],
              mask_table='../mask_table.npy',plan_sha256=sha(OUT/'plan.json')))
    manifest = dict(passed=True,production=not args.smoke,schema=plan['schema'],version='v2',roles=plan['counts'],
                    roundtrip_perspectives=checked,roundtrip_exact=True,mask_table_sha256=sha(OUT/'mask_table.npy'),
                    role_manifests={r:sha(OUT/r/'manifest.json') for r in ROLES},plan_sha256=sha(OUT/'plan.json'),
                    role_file_sha256=plan['role_sha256'],eval_spec_sha256=plan['eval_spec_sha256'],
                    sidecar_manifest_sha256=plan['sidecar_manifest_sha256'],builder_sha256=plan['builder_sha256'],
                    inputs=plan['inputs'],leak_check=plan['leak_check'],raw_role_counts=plan['raw_role_counts'],
                    excluded_3m_by_role=plan['excluded_3m_by_role'],thinning=plan['thinning'],wall_seconds=time.monotonic()-start)
    write(OUT/'manifest.json',manifest)
    print(json.dumps({k:v for k,v in manifest.items() if k!='inputs'}),flush=True)


if __name__ == '__main__': main()
