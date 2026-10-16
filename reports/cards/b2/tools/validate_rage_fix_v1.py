"""Fresh Rage correction build/affected receipts; semantic-v1 remains unchanged.

No whole-engine or filtered semantic PASS. Unchanged critical guard records must
match the retained old arm exactly, including every existing failure.
"""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

if not __debug__ or sys.flags.optimize:raise SystemExit('optimized validation forbidden')

from validate_semantic_v1 import (check_sweep,check_descendants,check_original_parity,check_ledger)
from validate_r2 import SHARDS,exact_keys

GROUPS=[['rage','lightning'],['poison','log'],['vines','void'],['goblin_curse','barblog']]
LABELS=[f'baseline-{i}' for i in range(1,5)]+['mutA','mutB','descendants','fu-paths','clone-checks','scen-b2-root','scen-b2-stats','scen-batchA']
MODULE_LABELS=set(LABELS)-{'clone-checks'}|{'clone-bounds','clone-recovery','rage-impact','rage-mirror'}
OLD=Path('/mpac/sdicks02/jobs/clasher/cards/b2-semv1-20261016T1052Z')
OLD_TAG='semv1-20261016T1052Z'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def utc():return datetime.now(timezone.utc).isoformat()


def read(job,tag,label):return json.loads((job/f'fid/{tag}-{label}.json').read_text())


def mutation(source,arm):
    if arm=='mutA':
        marker='''                        && !e.dash_travel() // Batch B2 r2: dash travel excluded (Python can_receive_area_damage / can_receive_effect).
                        && (e.class == "Troop" || e.class == "Building")
                        && !self.entities[i].hit_ids.contains(&e.id)'''
        replacement='''                        && (e.class == "Troop" || e.class == "Building")
                        && !self.entities[i].hit_ids.contains(&e.id)'''
    elif arm=='mutB':
        marker='''                || target.dash_travel() // Batch B2 r2: dash travel excluded (Python can_receive_area_damage / can_receive_effect).
'''
        replacement=''
    else:raise ValueError(arm)
    assert source.count(marker)==1, ('intended mutation not unique',arm)
    changed=source.replace(marker,replacement)
    assert changed!=source
    return changed


def prepare(job,tag):
    manifest=json.loads((job/'source-and-tools.json').read_text())
    assert sha(job/'source-and-tools.json')==os.environ['B2_RAGE_MANIFEST_SHA256']
    for name,expected in manifest['inputs'].items():assert sha(Path(name))==expected, ('changed prebuild input',name)
    sources={}
    for arm,tree,path in [('mutA','treeA','src/c56.rs'),('mutB','treeB','src/lib.rs')]:
        shutil.copytree(job/'tree',job/tree)
        target=job/tree/path;target.write_text(mutation(target.read_text(),arm))
        sources[arm]={name:sha(job/tree/name) for name in manifest['engine_files']}
        changed={name for name in manifest['engine_files'] if sources[arm][name]!=manifest['engine_files'][name]}
        assert changed=={path},('mutant source drift',arm,changed)
    for arm in ('out4','mutA','mutB'):(job/arm).mkdir()
    # Copy the cache; never build into or mutate an old frozen directory.
    cache=Path('/mpac/sdicks02/jobs/clasher/cards/b2m/out4/target')
    cache_hashes={str(p.relative_to(cache)):sha(p) for p in cache.rglob('*') if p.is_file()}
    shutil.copytree(cache,job/'target')
    assert {str(p.relative_to(job/'target')):sha(p) for p in (job/'target').rglob('*') if p.is_file()}==cache_hashes
    sources['out4']=manifest['engine_files']
    with (job/'prebuild.json').open('x') as out:
        json.dump(dict(utc=utc(),sources=sources,cache_source=str(cache),cache_hashes=cache_hashes,
                       cargo=subprocess.check_output(['cargo','+1.97.1','--version'],text=True).strip(),
                       rustc=subprocess.check_output(['rustc','+1.97.1','--version','--verbose'],text=True).strip()),out,indent=1)


def identity(job,tag):
    manifest=json.loads((job/'source-and-tools.json').read_text())
    prebuild=json.loads((job/'prebuild.json').read_text());inputs=dict(manifest['inputs'])
    natives={}
    for arm,tree in [('out4','tree'),('mutA','treeA'),('mutB','treeB')]:
        assert (job/f'build-{arm}.exit').read_text().strip()=='0'
        for name,expected in prebuild['sources'][arm].items():
            path=job/tree/name;assert sha(path)==expected, ('source changed during build',path)
            inputs[str(path)]=expected
        native=job/arm/'clasher_core.abi3.so';natives[arm]=sha(native);inputs[str(native)]=natives[arm]
    assert len(set(natives.values()))==3,'mutants did not produce distinct libraries'
    inputs[str(job/'source-and-tools.json')]=os.environ['B2_RAGE_MANIFEST_SHA256']
    inputs[str(job/'prebuild.json')]=sha(job/'prebuild.json')
    for name,expected in inputs.items():assert sha(Path(name))==expected, ('input changed before probes',name)
    with (job/'build.json').open('x') as out:
        json.dump(dict(utc=utc(),source_commit=manifest['source_commit'],source_engine_files=manifest['engine_files'],
                       native_sha256=natives,prebuild_sha256=sha(job/'prebuild.json'),inputs=inputs,
                       scope='Rage source correction plus unchanged r2 guards; not engine acceptance'),out,indent=1)


def execute(job,tag,arm,label,args):
    assert label in MODULE_LABELS and arm in ('out4','mutA','mutB')
    assert sha(job/'build.json')==os.environ['B2_RAGE_BUILD_SHA256']
    import clasher_core,differential,clasher
    build=json.loads((job/'build.json').read_text())
    native=Path(clasher_core.__file__).resolve()
    assert native==(job/arm/'clasher_core.abi3.so').resolve() and sha(native)==build['native_sha256'][arm]
    assert Path(differential.__file__).resolve()==(job/'tree/differential.py').resolve()
    assert Path(clasher.__file__).resolve()==(job/'tree/py/src/clasher/__init__.py').resolve()
    root='rootstats' if label=='scen-b2-stats' else 'root'
    assert Path(os.environ['CLASHER_ROOT']).resolve()==(job/root).resolve()
    assert Path(args[0]).resolve().parent==(job/'fid').resolve()
    with (job/f'fid/{tag}-{label}-module.json').open('x') as out:
        json.dump(dict(native=str(native),native_sha256=sha(native),python=sys.executable,optimized=sys.flags.optimize,
                       differential=differential.__file__,clasher=clasher.__file__,root=os.environ['CLASHER_ROOT'],
                       probe_sha256=sha(Path(args[0]))),out,indent=1)
    sys.argv=args
    runpy.run_path(args[0],run_name='__main__')


def check_baselines(rows,old):
    names=[name for group in GROUPS for name in group]
    exact_keys(rows,[(name,seat) for name in names for seat in ('blue','red')],lambda r:(r['case'],r['seat']))
    old_by={(r['case'],r['seat']):r for r in old}
    check_sweep([r for r in rows if r['case']=='rage'],['rage'])
    retained=0
    for row in rows:
        if row['case']=='rage':continue
        assert row==old_by[(row['case'],row['seat'])],('critical guard record changed',row['case'],row['seat'])
        assert row['query_count']>0
        retained+=row['mismatches']
    return retained


def check_impact(rows):
    exact_keys(rows,[(lead,seat) for lead in (6,8,9,10) for seat in (0,1)],lambda r:(r['lead'],r['seat']))
    for row in rows:
        assert row['contract']=='b2-semantic-snapshot-v1' and row['fresh_troop_templates']
        check_ledger(row['applicability'])
        assert all(t<45 for item in row['applicability'] for t in item['ticks'])
        assert 'error' not in row and row['first'] is None and not row['differences'] and row['compared_ticks']==45,row
        assert row['cast']['python'] is True and (row['cast']['before_export'] or row['cast']['native'] is True)
    for seat in (0,1):
        assert any(q['allowed'] is False and str(q['source']).replace('_','').lower()=='ragedamage'
                   for row in rows if row['seat']==seat for q in row['gate_queries']),('Rage impact guard never queried',seat)


def check_mirror(rows):
    exact_keys(rows,[0,1],lambda r:r['seat'])
    for row in rows:
        assert 'error' not in row and row['contract']=='b2-semantic-snapshot-v1'
        assert row['case']=='rage_mirror' and row['ticks']==140 and row['expired'] is True
        assert row['first'] is None and not row['differences'] and row['fresh_troop_templates']
        assert row['actions']==[[0,row['seat'],'Rage',True,True],[4,row['seat'],'Mirror',True,True]]
        check_ledger(row['applicability'])
        assert all(t<140 for item in row['applicability'] for t in item['ticks'])


def validate(job,tag):
    assert sha(job/'build.json')==os.environ['B2_RAGE_BUILD_SHA256']
    build=json.loads((job/'build.json').read_text())
    for name,expected in build['inputs'].items():assert sha(Path(name))==expected,('changed input',name)
    for label in LABELS:assert (job/f'fid/{tag}-{label}.exit').read_text().strip()=='0',label
    for label in MODULE_LABELS:
        module=read(job,tag,label+'-module')
        expected='mutA' if label=='mutA' else 'mutB' if label=='mutB' else 'out4'
        assert module['native_sha256']==build['native_sha256'][expected] and module['optimized']==0,label
    rows=[row for i in range(1,5) for row in read(job,tag,f'baseline-{i}')]
    old=[row for i in range(1,5) for row in json.loads((OLD/f'fid/{OLD_TAG}-semantic-{i}.json').read_text())]
    retained=check_baselines(rows,old)
    check_sweep(read(job,tag,'mutA'),['lightning'],('Lightning','RankedStrikeArea',False))
    check_sweep(read(job,tag,'mutB'),['log'],('Log','RollingProjectile',True))
    check_descendants(read(job,tag,'descendants'));check_original_parity(job/'fid',tag)
    check_impact(read(job,tag,'rage-impact'))
    check_mirror(read(job,tag,'rage-mirror'))
    paths=list((job/'fid').glob(tag+'*'))+[job/'build.json',job/'prebuild.json']
    paths += [job/f'build-{arm}.{ext}' for arm in ('out4','mutA','mutB') for ext in ('log','exit')]
    result=dict(status='AFFECTED_CHECKS_COMPLETE',utc=utc(),rage_matching_continuations=80,
                rage_impact_matching_continuations=8,
                rage_mirror_matching_continuations=2,
                unchanged_critical_guard_continuations=560,retained_semantic_failures=retained,
                semantic_status='FAIL retained; no full sweep/engine acceptance',native_sha256=build['native_sha256'],
                build_sha256=sha(job/'build.json'),outputs={str(p.relative_to(job)):sha(p) for p in sorted(set(paths)) if p.is_file()})
    with (job/'affected.tmp').open('x') as out:json.dump(result,out,indent=1)
    os.rename(job/'affected.tmp',job/'affected.json');print(json.dumps(result),flush=True)


if __name__=='__main__':
    mode,job,tag=sys.argv[1],Path(sys.argv[2]),sys.argv[3]
    assert tag.startswith('ragefixv1-') and tag.replace('-','').isalnum()
    if mode=='prepare':prepare(job,tag)
    elif mode=='identity':identity(job,tag)
    elif mode=='exec':execute(job,tag,sys.argv[4],sys.argv[5],sys.argv[6:])
    elif mode=='validate':validate(job,tag)
    else:raise SystemExit('unknown mode')
