"""05 metadata-only timing freeze, from sealed Stage1 and unchanged sources.

Never reads weights, arrays or native binaries. Requires independently admitted
03 qualification receipts before constructing the final game freeze. Caller
must then commit, secret-scan, push and verify deployed prelaunch bytes.
"""
import hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OWN=ROOT/'timing03'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def verified(p):
    v=json.loads(p.read_text())
    assert hashlib.sha256(v['raw'].encode()).hexdigest()==v['sha256']
    assert json.loads(v['raw'])==v['value']
    return v['value'],v['sha256']


def main():
    old=json.loads((ROOT/'receipts/evaluation-freeze.json').read_text())
    snapshots=ROOT/'receipts/evaluation-snapshots/127x03'
    stage1,stage1_sha=verified(snapshots/'stage1-results.json')
    assert set(stage1)=={'R3c','R3d','R3e'} and all(v['stage1_complete'] for v in stage1.values())
    survivors=[a for a,v in stage1.items() if v['survives']]
    assert survivors,'All killed: no Stage2 freeze or games needed'
    qualification,qualification_sha=verified(snapshots/'timing03--CODE-QUALIFICATION.json')
    assert qualification['passed'] and qualification['no_games'] and qualification['native_startup']
    admitted,admitted_sha=verified(snapshots/'timing03--CPU-RELEASE-ADMITTED.json')
    assert admitted['explicit_coordinator_G_release'] and admitted['independent_full_drain']
    assert admitted['host']=='127x03' and admitted['physical_cores']==list(range(56))
    assert admitted['stage1_results_sha256']==stage1_sha
    # Bind the byte-identical science, not a reconstructed or simplified runner.
    for name in ('block.py','game.py','journal.py','proposals.py','protocol.py','test_hook.py','test_protocol.py','test_proposals.py'):
        assert sha(OWN/'eval-ops'/name)==old['files']['eval-ops/'+name],name
    files={name:want for name,want in old['home_files'].items()
           if name.split('/')[0] in ('eval-source','student-source','inputs','reporting-native')}
    files.update({'eval-ops/'+p.name:sha(p) for p in (OWN/'eval-ops').iterdir() if p.is_file()})
    files['CODE-QUALIFICATION.json']=qualification_sha
    files['stage1-results.json']=stage1_sha
    for arm in stage1:
        merged,want=verified(snapshots/'offline--'+arm+'.json')
        assert merged==stage1[arm]
        files['offline/'+arm+'.json']=want
    bindings={}
    for arm in survivors:
        v,want=verified(snapshots/'offline--'+arm+'.json')
        assert v==stage1[arm] and v['survives']
        calibration,cal_sha=verified(snapshots/'offline--'+arm+'-calibration.json')
        assert calibration['checkpoint_sha256']==v['checkpoint_sha256']
        files['offline/'+arm+'-calibration.json']=cal_sha
        files['fits/'+arm+'/step-'+str(old['arms'][arm]['steps']).zfill(8)+'.pt']=v['checkpoint_sha256']
        bindings[arm]=dict(checkpoint_sha256=v['checkpoint_sha256'],merged_offline_sha256=want,calibration_sha256=cal_sha)
    freeze=dict(schema=1,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),
                protocol=old['protocol'],timing_host='127x03',physical_cores=list(range(56)),manager_core=55,
                inherited_evaluation_freeze_sha256=sha(ROOT/'receipts/evaluation-freeze.json'),
                training_freeze_sha256=old['training_freeze_sha256'],seed_audit_sha256=old['seed_audit_sha256'],
                operational_addendum_sha256=sha(ROOT/'STAGE2-HOST03-ADDENDUM.md'),
                admission_sha256=admitted_sha,authority_sha256=admitted['authority_sha256'],
                stage1_results_sha256=stage1_sha,survivors=survivors,student_bindings=bindings,
                arms=old['arms'],files=files,stage1=old['stage1'],stage2={**old['stage2'],'host':'127x03','physical_cores':list(range(56)),'manager_core':55},
                unchanged_scientific_game_ranking_seeds_gates=True,committed_before_games=True,
                source_and_native_qualification_sha256=qualification_sha,
                qualification_reporting_bank=4503602417370496,reporting_bank=4503602407370496,
                live_adoption=False)
    (OWN/'receipts/evaluation-freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
    print(json.dumps(dict(survivors=survivors,evaluation_freeze_sha256=sha(OWN/'receipts/evaluation-freeze.json'),
                         commit_push_prelaunch_still_required=True)))


if __name__=='__main__':main()
