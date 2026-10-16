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
    assert label in ('shared','review','followup','first-update')
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
    try:
        data=json.loads(output.read_text())
        if label=='shared':
            assert data['native_sha256']==build['native_sha256'] and len(data['results'])==32
            assert data['status']=='FOCUSED_PASS' and all(row['required_witness_observed'] for row in data['results'])
        elif label=='review': assert len(data)==21
        elif label=='followup': assert len(data['cases'])==2 and data['native_sha256']==build['native_sha256']
        else:
            assert len(data)==42
            assert all(row['native']=='ok' and row['first_mismatch'] is None and not row.get('error')
                and row['victim_death'] is not None and row['victim_death']!=row['control_death']
                and all(action[3] and action[4] for action in row['actions']) for row in data)
        J.validate(job)
        assert J.sha(job/'manifest.json')==manifest_sha and J.sha(job/'output/build.json')==build_sha
        assert all(J.sha(value['path'])==value['sha256'] for value in before.values())
        modules={name:dict(path=str(Path(module.__file__).resolve()),sha256=J.sha(Path(module.__file__).resolve()))
                 for name,module in list(sys.modules.items()) if getattr(module,'__file__',None) and Path(module.__file__).is_file()}
        for name,module in modules.items():
            if name=='clasher' or name.startswith('clasher.'):
                assert Path(module['path']).is_relative_to(job/'src/engine-cards/py/src'),name
        J.save(job/'output'/(label+'-imports-after.json'),modules)
    except BaseException:
        code=1; failure=(failure or '')+'\n'+traceback.format_exc()
    J.save(job/'output'/(label+'-worker.json'),dict(utc=J.utc(),exit=code,error=failure,
        output_sha256=J.sha(output) if output.is_file() else None,native_sha256=build['native_sha256'],
        source_commit=manifest['commit'],engine_acceptance=False))
    return code


if __name__=='__main__': raise SystemExit(main())
