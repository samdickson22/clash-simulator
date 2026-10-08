"""Synthetic files exercise candidate provenance and full replay checks on01."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import calibration_candidate_v4 as driver
import validation_score_v4 as scoring
from test_validation_score_v4 import main as make_fixture


def main(root):
    checks=0
    def check(v):
        nonlocal checks
        assert v;checks+=1
    def refuses(fn):
        nonlocal checks
        try:fn()
        except ValueError:checks+=1
        else:raise AssertionError('Invalid calibration candidate accepted')
    def put(path,value):path.write_text(json.dumps(value))
    def rejecting(*args):raise ValueError('Producer incomplete')
    # Refusal must precede access to any nonexistent source/replay/output.
    with patch.object(scoring,'validate_run',rejecting):
        refuses(lambda:driver.calibrate_run(SimpleNamespace(run=None,source=None,split=None,phase_state=None,phase_exit=None)))
    root.mkdir();fixture=root/'fixture';make_fixture(fixture)
    replay=fixture/'replay';source=fixture/'source'
    manifest=json.loads((replay/'manifest.json').read_text())
    complete=json.loads((replay/'complete.json').read_text())
    admission=manifest['readiness']
    def args(name):return SimpleNamespace(run=None,source=source,split=None,phase_state=None,phase_exit=None,replay=replay,output=root/name)
    def manifest_put(value):
        put(replay/'manifest.json',value)
        changed=deepcopy(complete);changed['manifest_sha256']=scoring.sha(replay/'manifest.json')
        put(replay/'complete.json',changed)
    with patch.object(scoring,'validate_run',return_value=admission):
        refuses(lambda:driver.calibrate_run(args('grid-rejected')))
        check(not (root/'grid-rejected').exists())
        manifest.update(replay_mode='combined',event_thresholds={'default':.5,'Fireball':.7},threshold_map_sha256='a'*64)
        manifest_put(manifest)
        result=driver.calibrate_run(args('candidate'))
        check(result['candidate']['predictions']==2 and result['candidate']['matched']==1)
        check(result['abilities_excluded']==1 and result['candidate']['episodes']==['ep'])
        check(all(row[1]==.5 for row in result['candidate']['calibration']['default']))
        check(result['candidate']['support']['Fireball']['fit']=='pooled')
        check(result['event_thresholds']==manifest['event_thresholds'] and result['body_threshold']==.7)
        check(result['selection_provenance_verified'] is False and result['selection_seal'] is False)
        check(result['heldout_opening_authorized'] is False and result['heldout_payloads_opened'] is False)
        done=json.loads((root/'candidate/complete.json').read_text())
        check(done['candidate_sha256']==scoring.sha(root/'candidate/calibration-candidate.json'))
        check(result['replay_completion_sha256']==scoring.sha(replay/'complete.json'))
        refuses(lambda:driver.calibrate_run(args('candidate')))
        for change in ({'calibration':{'default':[[0.,0.],[1.,1.]]}}, {'heldout_payloads_opened':True}):
            bad=deepcopy(manifest);bad.update(change);manifest_put(bad)
            refuses(lambda:driver.calibrate_run(args('invalid')))
        manifest_put(manifest)
        file=replay/'ep-outputs.jsonl';saved=file.read_bytes();file.write_bytes(saved+b'\n')
        refuses(lambda:driver.calibrate_run(args('changed-payload')));file.write_bytes(saved)
        # Rehashed but incomplete populations still fail the authenticated loader.
        original_complete=(replay/'complete.json').read_bytes()
        bad=json.loads(original_complete);bad['episodes']={};put(replay/'complete.json',bad)
        refuses(lambda:driver.calibrate_run(args('missing-episode')))
        (replay/'complete.json').write_bytes(original_complete)
        rows=[json.loads(line) for line in saved.decode().splitlines()]
        for row in rows:row['payload']['event_candidates']=[]
        file.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        changed=json.loads(original_complete);changed['files_sha256'][file.name]=scoring.sha(file)
        put(replay/'complete.json',changed)
        refuses(lambda:driver.calibrate_run(args('empty')))
        check(not (root/'empty').exists())
        file.write_bytes(saved);(replay/'complete.json').write_bytes(original_complete)
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,
        heldout_payloads_opened=False,selection_provenance_verified=False)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
