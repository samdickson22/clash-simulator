"""Validate immutable stage provenance and create the final reducer's envelope."""
import argparse
import hashlib
import json
from pathlib import Path
from imitation.exit_r1 import screen
from imitation.exit_r1.rows import sha,write_json

def canonical_record(raw,stage,stage_sha,final,final_sha,raw_sha):
    assert raw['freeze_sha256']==stage_sha
    for key in ('plan_sha256','plan','seed_audit','native','seed_bases','counts'):
        assert stage[key]==final[key],key
    assert all(final['files'].get(k)==v for k,v in stage['files'].items())
    assert all(final['checkpoints'].get(k)==v for k,v in stage['checkpoints'].items())
    mode,arm,index=raw['mode'],raw['arm'],raw['index']
    assert mode in ('h2h','fallback') and arm in (*screen.ARMS,'init')
    assert mode!='h2h' or arm in screen.ARMS
    assert 0<=index<screen.COUNTS[mode]
    assert raw['seed']==screen.BASES[mode]+index and raw['seat']==index%2 and raw['terminal'] is True
    assert set(stage['checkpoints'])==({'init'} if arm=='init' else {'init',arm})
    result=dict(raw,freeze_sha256=final_sha,stage_freeze_sha256=stage_sha,stage_case_sha256=raw_sha)
    assert {k:v for k,v in result.items() if k not in ('stage_freeze_sha256','stage_case_sha256','freeze_sha256')}=={
        k:v for k,v in raw.items() if k!='freeze_sha256'}
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args();job=Path(a.job)
    final_sha=sha(job/'execution-freeze.json');final=screen.verify_freeze(job/'execution-freeze.json',final_sha)
    expected={(m,a,i) for m,arms in [('h2h',screen.ARMS),('fallback',('init',*screen.ARMS))]
              for a in arms for i in range(screen.COUNTS[m])}
    seen=set();manifest={};stages={}
    dest=job/'cases';dest.mkdir(exist_ok=False)
    for path in sorted((job/'stage-cases').glob('*/*.json')):
        stage_name=path.parent.name
        if stage_name not in stages:
            freeze=job/'stage-freezes'/f'{stage_name}.json';stage_sha=sha(freeze)
            stages[stage_name]=(screen.verify_freeze(freeze,stage_sha),stage_sha)
        stage,stage_sha=stages[stage_name];raw=json.loads(path.read_text());raw_sha=sha(path)
        key=(raw['mode'],raw['arm'],raw['index']);assert key in expected and key not in seen,key
        record=canonical_record(raw,stage,stage_sha,final,final_sha,raw_sha);seen.add(key)
        name=f'{key[0]}-{key[1]}-{key[2]:04d}.json';assert path.name==name
        write_json(dest/name,record);manifest[str(path)]=raw_sha
    assert seen==expected,(len(seen),len(expected))
    write_json(job/'stage-case-sha-manifest.json',manifest)
    write_json(job/'staged-provenance.json',dict(schema='clasher.exit-r1.staged-provenance.v1',
        stage_freeze_sha256={k:v[1] for k,v in stages.items()},final_freeze_sha256=final_sha,
        raw_case_count=len(manifest),raw_case_sha_manifest_sha256=sha(job/'stage-case-sha-manifest.json'),
        scientific_fields_unchanged=True,common_reference_cases=600,
        analysis_gate='All final4883 fits and all3232 reporting tasks complete before canonicalization/analysis.'))
    print(json.dumps(dict(cases=len(seen),provenance_sha256=sha(job/'staged-provenance.json'))))

if __name__=='__main__':main()
