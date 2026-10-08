"""Fit an unsealed calibration candidate from authenticated combined replay.

Formal producer/full-fit admission and complete validation replay checks run
before fitting. This driver verifies data provenance, NOT that the checkpoint,
event map or body threshold won their selection procedures. The eventual seal
must authenticate those choices and require exactly this replay/configuration.
There is no heldout input or opening authority here.
"""
import argparse
import json
from pathlib import Path

from calibration_v4 import fit_validation_calibration
from validation_admission_v4 import sha
from validation_score_v4 import load_replay


def calibrate_run(args):
    loaded=load_replay(args)  # Authentic completion/full fit before any other I/O.
    manifest=loaded['manifest']
    if manifest['replay_mode']!='combined':
        raise ValueError('Fresh combined-threshold validation replay required')
    if args.output.exists():raise ValueError('Fresh candidate output required; retain prior attempts')
    code=Path(__file__).parent
    paths=[code/n for n in ('calibration_candidate_v4.py','calibration_v4.py','validation_score_v4.py',
        'validation_replay_v4.py','validation_admission_v4.py','scoring_v4.py','execution_clock_v4.py')]
    paths.append(code.parents[4]/'src/clasher/vision/l1_v4.py')
    pins={str(p):sha(p) for p in paths}
    # Abilities have a separate registered reporting path, not card-play labels.
    truth=[r for r in loaded['truth'] if r['kind']!='champion_ability']
    candidate=fit_validation_calibration(loaded['predictions'],truth,
        episodes=loaded['episodes'],split_by_episode={ep:'validation' for ep in loaded['episodes']})
    result=dict(schema='clasher.v4.calibration-candidate.v1',candidate=candidate,
        epoch=manifest['epoch'],event_thresholds=loaded['thresholds'],body_threshold=manifest['body_threshold'],
        readiness=loaded['admission'],validation_receipts=loaded['admission']['validation_receipt_sha256'],
        truth_payloads=loaded['provenance'],replay_manifest_sha256=loaded['replay_manifest_sha256'],
        replay_completion_sha256=loaded['replay_completion_sha256'],sources=pins,
        abilities_excluded=len(loaded['truth'])-len(truth),
        selection_provenance_verified=False,selection_seal=False,heldout_opening_authorized=False,
        heldout_payloads_opened=False,pending=['authenticate epoch/event/body selection','selection seal'],
        scope='authenticated combined validation data; unsealed calibration candidate only')
    if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('Calibration sources changed during fit')
    if (sha(args.replay/'manifest.json')!=loaded['replay_manifest_sha256']
            or sha(args.replay/'complete.json')!=loaded['replay_completion_sha256']):
        raise ValueError('Replay completion changed during fit')
    args.output.mkdir()
    with (args.output/'calibration-candidate.json').open('x') as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    with (args.output/'complete.json').open('x') as f:
        json.dump(dict(candidate_sha256=sha(args.output/'calibration-candidate.json'),
            selection_provenance_verified=False,selection_seal=False,
            heldout_opening_authorized=False,heldout_payloads_opened=False),f,indent=2);f.write('\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('run','source','split','phase-state','phase-exit','replay','output'):
        p.add_argument('--'+name,type=Path,required=True)
    calibrate_run(p.parse_args())
