"""Source/import/output binding for one diagnostic probe; admitted CPU job only."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import traceback

if sys.flags.optimize: raise RuntimeError('unoptimized execution required')


def main():
    job=Path(sys.argv[1]); label=sys.argv[2]; probe=Path(sys.argv[3]); extra=sys.argv[4:]
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import diagnostic_job as J
    assert label in ('shared','dash-clock','review','selectors','followup','first-update','clone-bounds','clone-recovery','terrain')
    manifest_sha=os.environ['C1_DIAG_MANIFEST_SHA256']; build_sha=os.environ['C1_DIAG_BUILD_SHA256']
    assert J.sha(job/'manifest.json')==manifest_sha and J.sha(job/'output/build.json')==build_sha
    manifest=J.validate(job)
    assert str(probe.relative_to(job/'src')) in manifest['files']
    build=json.loads((job/'output/build.json').read_text())
    assert build['commit']==manifest['commit'] and build['manifest_sha256']==manifest_sha
    assert J.sha(job/'native/clasher_core.abi3.so')==build['native_sha256']
    import differential as D
    expected={'differential':job/'src/engine-cards/differential.py',
        'clasher.battle':job/'src/engine-cards/py/src/clasher/battle.py',
        'clasher.entities':job/'src/engine-cards/py/src/clasher/entities.py',
        'clasher_core':job/'native/clasher_core.abi3.so',
        'es_common':job/'src/reports/strategy_council_20260928/engine-speed/es_common.py'}
    for name,path in expected.items(): assert Path(sys.modules[name].__file__).resolve()==path
    assert J.sha(job/'root/gamedata.json')==manifest['files']['engine-cards/py/gamedata.json']
    before={name:dict(path=str(path),sha256=J.sha(path)) for name,path in expected.items()}
    J.save(job/'output'/(label+'-imports-before.json'),before)
    output=job/'output'/(label+'.json'); assert not output.exists()
    code=0; failure=None
    try:
        sys.argv=[str(probe),str(output),*extra]
        runpy.run_path(str(probe),run_name='__main__')
    except SystemExit as error:
        code=error.code if isinstance(error.code,int) else (0 if error.code is None else 1)
        if code: failure=traceback.format_exc()
    except BaseException:
        code=1; failure=traceback.format_exc()
        roots=[]
        for frame,_ in traceback.walk_tb(sys.exc_info()[2]):
            local=frame.f_locals; battle=local.get('b'); cfg=local.get('cfg')
            if battle is None or not hasattr(battle,'entities') or not isinstance(cfg,dict): continue
            try:
                natives={name:json.loads(value.snapshot()) for name,value in local.items()
                    if hasattr(value,'snapshot') and type(value).__module__=='clasher_core'}
                roots.append(dict(function=frame.f_code.co_name,python=json.loads(D.snapshot(battle,cfg)),natives=natives))
            except Exception as error: roots.append(dict(error=repr(error)))
        J.save(job/'output'/(label+'-exception-roots.json'),dict(error=failure,roots=roots))
    after_errors=[]; modules={}
    # Collect actual module evidence before validating results. Failed/partial
    # probes are expected diagnostic outcomes and must retain the same evidence.
    for name,module in list(sys.modules.items()):
        filename=getattr(module,'__file__',None)
        if not filename: continue
        try:
            path=Path(filename).resolve()
            if path.is_file(): modules[name]=dict(path=str(path),sha256=J.sha(path))
        except Exception:
            modules[name]=dict(path=str(filename),error=traceback.format_exc(limit=4))
            after_errors.append(dict(check='module-hash',module=name,error=modules[name]['error']))
    for name,check in (
        ('source_inventory',lambda:J.validate(job)),
        ('manifest_identity',lambda:J.sha(job/'manifest.json')==manifest_sha),
        ('build_identity',lambda:J.sha(job/'output/build.json')==build_sha),
        ('loaded_initial_modules',lambda:all(J.sha(value['path'])==value['sha256'] for value in before.values())),
        ('python_source_paths',lambda:all(os.path.commonpath([module['path'],str(job/'src/engine-cards/py/src')])==str(job/'src/engine-cards/py/src')
            for name,module in modules.items() if name=='clasher' or name.startswith('clasher.')))):
        try:
            answer=check()
            assert answer is not False, name
        except BaseException: after_errors.append(dict(check=name,error=traceback.format_exc(limit=5)))
    J.save(job/'output'/(label+'-imports-after.json'),dict(modules=modules,identity_errors=after_errors))
    if after_errors:
        code=1; failure=(failure or '')+'\nafter-import identity checks failed'
    try:
        data=json.loads(output.read_text())
        if label in ('shared','selectors'):
            expected_count=32 if label=='shared' else 8
            assert data['native_sha256']==build['native_sha256'] and len(data['results'])==expected_count
            assert data['status']=='FOCUSED_PASS' and all(row['required_witness_observed'] for row in data['results'])
            if label=='shared': assert len({(row['case'],row['seat']) for row in data['results']})==32
            else: assert {(row['seat'],row['kind'],row['travel']) for row in data['results']}=={
                (seat,kind,travel) for seat in (0,1) for kind in ('secondary','chain') for travel in (True,False)}
        elif label=='dash-clock':
            assert data['native_sha256']==build['native_sha256'] and len(data['results'])==12
            assert data['status']=='FOCUSED_PASS' and all(row['status']=='FOCUSED_PASS' and
                row['required_witness_observed'] and row['ticks']==40 for row in data['results'])
            assert {(row['seat'],row['mode']) for row in data['results']}=={(seat,mode) for seat in (0,1)
                for mode in ('cold_zero','cold_equal','loaded_changed','loaded_equal','miss','missing')}
        elif label=='review':
            assert len(data)==21
            assert len({(row['case'],row.get('side'),row.get('mode'),row.get('attacker_first')) for row in data})==21
        elif label=='followup': assert len(data['cases'])==2 and data['native_sha256']==build['native_sha256']
        elif label=='first-update':
            from probe_first_update_diagnostic import validate_pair
            import probe_first_update_paths as first_update
            assert len(data)==42
            assert {row['case'] for row in data}=={name+'/'+seat for name in first_update.CASES for seat in ('blue','red')}
            for row in data: validate_pair(row)
        elif label=='clone-bounds':
            assert len(data)==6 and {(row['case'],row['seat']) for row in data}=={
                (name,seat) for name in ('back_edge','river_front','own_tower') for seat in (0,1)}
            assert all(not row.get('error') and row['first'] is None and row['cast']==[True,True] and 'pos30' in row for row in data)
        elif label=='clone-recovery':
            assert len(data)==2 and {row['seat'] for row in data}=={0,1}
            assert all(row['ok'] is True and row['ticks']==10 and len(row['positions'])==10 and not row.get('error') for row in data)
        else:
            assert len(data)==4 and {row['scenario'] for row in data}=={
                'bandit_water_end','bandit_water_end_red','mk_vs_giant','mk_vs_giant_red'}
            assert all(row['native']=='ok' and row['first_mismatch'] is None and not row.get('error')
                and all(action[3] is True and action[4] is True for action in row['deploys']) for row in data)
    except BaseException:
        code=1; failure=(failure or '')+'\n'+traceback.format_exc()
    J.save(job/'output'/(label+'-worker.json'),dict(utc=J.utc(),exit=code,error=failure,
        after_identity_errors=after_errors,
        output_sha256=J.sha(output) if output.is_file() else None,native_sha256=build['native_sha256'],
        source_commit=manifest['commit'],engine_acceptance=False))
    return code


if __name__=='__main__': raise SystemExit(main())
