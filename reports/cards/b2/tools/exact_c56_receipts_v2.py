"""Fail-closed receipts for a fresh, unmodified canonical C56 two-arm gate.

Only exact C56 equality is certified; B2/C1 semantic failures remain separate.
This file imports no engine. identity/validate run inside the claimed CPU job.
"""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import socket
import sys

if not __debug__ or sys.flags.optimize:
    raise SystemExit('optimized gate validation forbidden')

PIN = '681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b'
TOTAL = '76f873f1fcd2e1f5056ea792fe14828af2c0b60ba72579ecf28d6c1ba4fb7054'
BUILD_SHA256 = 'adcd109b3482984c322af61fa2adbae8c8380fbc42cb3f8404603d304273daf0'
AFFECTED_SHA256 = 'AFFECTED_RECEIPT_PENDING'
SOURCE_COMMIT = '55bac129b93a055898524b53cc350091fb65259e'
ARGS=dict(command_delay=27,opponent_delay=27,horizon=160,interval=10,elixir_weight=1.0)
LABELS = ['fixtures-pinned', 'fixtures-total'] + [f'roots-{arm}-{i}' for arm in ('pinned','total') for i in range(2)]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1<<20),b''): h.update(block)
    return h.hexdigest()


def utc(): return datetime.now(timezone.utc).isoformat()


def validate_candidate_binding(manifest):
    assert TOTAL!='0'*64 and 'PENDING' not in BUILD_SHA256 and 'PENDING' not in AFFECTED_SHA256
    candidate=manifest['candidate08'];build=candidate['build'];affected=candidate['affected']
    assert candidate['build_sha256']==BUILD_SHA256 and candidate['affected_sha256']==AFFECTED_SHA256
    assert manifest['source_commit']==build['source_commit']==SOURCE_COMMIT
    assert build['source_engine_files']==manifest['engine_files'] and len(manifest['engine_files'])==504
    assert manifest['native_sha256']==dict(pinned=PIN,total=TOTAL)
    assert build['native_sha256']['out4']==TOTAL and affected['native_sha256']==build['native_sha256']
    assert affected['status']=='AFFECTED_CHECKS_COMPLETE' and affected['build_sha256']==BUILD_SHA256
    assert affected['rage_matching_continuations']==80 and affected['rage_impact_matching_continuations']==8
    assert affected['rage_mirror_matching_continuations']==2 and affected['unchanged_critical_guard_continuations']==560
    assert affected['retained_semantic_failures']==56
    assert affected['semantic_status']=='FAIL retained; no full sweep/engine acceptance'


def check_canonical(directory,provenance):
    for name in ('parity_fixtures.py','parity_roots.py','compare.py'):
        assert sha(directory/name)==provenance['gate_tools'][name], ('historical canonical script changed',name)


def output_hashes(job):
    return {str(p.relative_to(job)):sha(p) for p in sorted((job/'gate').rglob('*')) if p.is_file()}


def unique(rows,key,expected,label):
    keys=[key(row) for row in rows]
    assert len(keys)==len(set(keys)), ('duplicate',label)
    assert set(keys)==set(expected), ('wrong denominator',label,len(keys),len(expected))
    return dict(zip(keys,rows))


def root_sample(directory):
    rows=[]
    for path in sorted(directory.glob('roots-*.jsonl.gz')):
        with gzip.open(path,'rt') as source:
            rows.extend(json.loads(line) for line in source)
    assert len(rows)==1043 and len({(r['index'],r['tick'],r['seat']) for r in rows})==1043
    indices=sorted(random.Random(20261015).sample(range(len(rows)),min(300,len(rows))))
    assert len(indices)==300, ('insufficient root corpus',len(rows))
    for index in indices:
        row=rows[index]
        config=directory/f"config-{row['config'][:16]}.json"
        assert sha(config)==row['config'], ('root config',config)
    assert len({rows[index]['index'] for index in indices})==12
    return rows,indices


def identity(job):
    manifest=json.loads((job/'manifest.json').read_text())
    inputs=dict(manifest['inputs'])
    inputs[str(job/'manifest.json')]=os.environ['B2_C56_MANIFEST_SHA256']
    assert sha(job/'manifest.json')==os.environ['B2_C56_MANIFEST_SHA256']
    for name,expected in inputs.items(): assert sha(Path(name))==expected, ('input changed',name)
    assert manifest['native_sha256']==dict(pinned=PIN,total=TOTAL)
    validate_candidate_binding(manifest)
    corpus=json.loads((job/'gate-provenance.json').read_text())['roots']
    check_canonical(job/'canonical',json.loads((job/'gate-provenance.json').read_text()))
    assert {p.name for p in (job/'roots').iterdir()}==set(corpus)
    for name,expected in corpus.items():assert sha(job/'roots'/name)==expected, ('historical corpus changed',name)
    assert len(manifest['episodes'])==577 and len(set(manifest['episodes']))==577
    _,indices=root_sample(job/'roots')
    with (job/'identity.json').open('x') as out:
        json.dump(dict(utc=utc(),host=socket.gethostname(),pid=os.getpid(),pgid=os.getpgid(0),
                       contract='b2-exact-c56-v2',inputs=inputs,episodes=manifest['episodes'],
                       sampled_indices=indices,python=sys.version,executable=sys.executable),out,indent=1)


def validate_records(fixtures,roots,headers,episodes,source_rows,indices):
    assert len(source_rows)==1043 and len({(r['index'],r['tick'],r['seat']) for r in source_rows})==1043
    assert len(indices)==len(set(indices))==300
    expected_keys={(index,variant) for index in indices for variant in ('full','cut')}
    fx,rt={},{}
    for arm,expected_native in (('pinned',PIN),('total',TOTAL)):
        fx[arm]=unique(fixtures[arm],lambda r:r['episode'],episodes,arm+' fixtures')
        rt[arm]=unique(roots[arm],lambda r:(r['k'],r['variant']),expected_keys,arm+' roots')
        assert len(headers[arm])==2, ('root shard header count',arm)
        for header in headers[arm]:
            assert header['native_sha256']==expected_native
            assert header['roots_total']==len(source_rows) and header['sampled']==300
            assert header['args']==ARGS, 'frozen rollout argument drift'
        parity=0
        for episode,row in fx[arm].items():
            rs,native=row['rs'],row['rust_only']
            assert rs['episode']==episode and rs['split'] in ('train','validation')
            assert 'error' not in native and isinstance(native.get('chain'),str) and len(native['chain'])==64
            assert isinstance(native.get('final'),str) and len(native['final'])==64
            assert native['ticks']>0 and 0<=native['accepted']<=native['plays']
            if rs.get('start_match') and rs.get('first_mismatch') is None and not rs.get('action_mismatch') and 'error' not in rs:
                parity+=1
        assert parity==429, ('reference parity denominator',arm,parity)
        for (index,variant),row in rt[arm].items():
            source=source_rows[index]
            assert all(row[key]==source[key] for key in ('index','tick','seat'))
            assert len(row['select'])==3 and len(row['step'])==3 and len(row['view'])==len(row['mask'])==2
            assert row['actions'][:2]==[2304,2401] and len(row['actions'])==len(set(row['actions']))
            assert all(0<=action<2304 for action in row['actions'][2:])
            assert len(row['rollout_e1'])==len(row['actions'])*3
            assert isinstance(row.get('root_snapshot'),str) and len(row['root_snapshot'])==64
            assert ('apply' in row)==(len(row['actions'])>2)
    assert fx['pinned']==fx['total'], 'fixture records differ; retain both raw arms'
    assert rt['pinned']==rt['total'], 'root records differ; retain both raw arms'
    return dict(fixtures=577,identical_fixture_records=577,identical_native_chains=577,
                reference_parity=dict(pinned=429,total=429),native_errors=0,roots=600,
                full=300,cut=300,games=12,selections=1800,step_checks=1800,
                native_sha256=dict(pinned=PIN,total=TOTAL))


def validate_audit(records,episodes,native_sha):
    audit=unique(records,lambda row:row['episode'],episodes,'native exception audit')
    for row in audit.values():
        assert row['native_sha256']==native_sha and row['optimized']==0
        assert row['errors']==[], ('native exception caught by canonical code',row)
        assert row['calls'].get('constructor',0)>=1
        assert all(row['calls'].get(name,0)>0 for name in ('step','snapshot','digest'))
    return len(audit)


def validate(job):
    ident=json.loads((job/'identity.json').read_text())
    for name,expected in ident['inputs'].items(): assert sha(Path(name))==expected, ('input changed during gate',name)
    for label in LABELS:
        assert (job/f'gate/{label}.exit').read_text().strip()=='0', ('nonzero child',label)
    fixtures,roots,headers={},{},{}
    for arm in ('pinned','total'):
        fixtures[arm]=[json.loads(line) for line in (job/f'gate/fixtures-{arm}.jsonl').read_text().splitlines()]
        log_header=json.loads((job/f'gate/fixtures-{arm}.log').read_text().splitlines()[0])
        assert log_header['fixtures']==577
        assert sha(Path(log_header['native']))=={'pinned':PIN,'total':TOTAL}[arm]
        roots[arm],headers[arm]=[],[]
        for index in range(2):
            rows=[json.loads(line) for line in (job/f'gate/roots-{arm}-{index}.jsonl').read_text().splitlines()]
            headers[arm].append(rows[0]); roots[arm].extend(rows[1:])
        audit=[]
        for path in sorted((job/f'gate/audit-{arm}').glob('worker-*.jsonl')):
            audit.extend(json.loads(line) for line in path.read_text().splitlines())
        assert validate_audit(audit,ident['episodes'],{'pinned':PIN,'total':TOTAL}[arm])==577
    source,indices=root_sample(job/'roots')
    assert indices==ident['sampled_indices']
    result=validate_records(fixtures,roots,headers,ident['episodes'],source,indices)
    result.update(status='C56_EXACT_PASS',utc=utc(),identity_sha256=sha(job/'identity.json'),
                  scope='Exact B2 C56 only; retained strict/semantic FAILs and final B2-C1 engine acceptance unchanged')
    result['outputs']=output_hashes(job)
    with (job/'gate/exact-pass.tmp').open('x') as out: json.dump(result,out,indent=1)
    os.rename(job/'gate/exact-pass.tmp',job/'gate/exact-pass.json')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    job=Path(sys.argv[2])
    if sys.argv[1]=='identity': identity(job)
    elif sys.argv[1]=='validate': validate(job)
    else: raise SystemExit('expected identity or validate')
