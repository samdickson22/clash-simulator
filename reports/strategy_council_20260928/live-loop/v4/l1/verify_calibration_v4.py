"""Recompute event selection and calibration, retaining an unsealed result.

Body-threshold selection is deliberately still required. No heldout entry point
or seal is provided by this intermediate verification.
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from calibration_candidate_v4 import calibrate_run
from validation_admission_v4 import read, sha, validate_run
from verify_event_selection_v4 import verify_run as verify_events


def verify_calibration(args):
    readiness = validate_run(args.run, args.source, args.split, args.phase_state, args.phase_exit)
    candidate_path = args.candidate/'calibration-candidate.json'
    completion_path = args.candidate/'complete.json'
    pins = {p.name: sha(p) for p in (candidate_path, completion_path)}
    original, complete = read(candidate_path), read(completion_path)
    if (original.get('schema') != 'clasher.v4.calibration-candidate.v1'
            or original.get('readiness') != readiness
            or complete.get('candidate_sha256') != pins[candidate_path.name]):
        raise ValueError('Calibration candidate provenance differs')
    for record in (original, complete):
        for key in ('selection_provenance_verified', 'selection_seal',
                    'heldout_opening_authorized', 'heldout_payloads_opened'):
            if record.get(key) is not False:
                raise ValueError('Unsealed validation-only candidate required')
    if args.output.exists():
        raise ValueError('Fresh verification output required; retain prior attempts')
    args.output.mkdir()
    common = dict(run=args.run, source=args.source, split=args.split,
                  phase_state=args.phase_state, phase_exit=args.phase_exit)
    selected = verify_events(SimpleNamespace(**common, grid=args.grid,
        selection=args.selection, output=args.output/'recomputed-event-selection'))
    if (selected.get('event_selection_verified') is not True
            or selected.get('readiness') != readiness
            or type(selected.get('body_selection_verified')) is not bool
            or any(selected.get(k) is not False for k in
                   ('selection_seal', 'heldout_opening_authorized', 'heldout_payloads_opened'))):
        raise ValueError('Authenticated unsealed event selection required')
    body_verified = selected['body_selection_verified']
    if body_verified:
        bodies = selected.get('body_selections',{})
        if set(bodies) != {str(i) for i in range(1,25)}:
            raise ValueError('All authenticated body selections required')
        chosen = bodies[str(selected['epoch'])]['ranking']
        if (chosen['body_threshold'] != selected['grid_body_threshold']
                or chosen['checkpoint_sha256'] != selected['checkpoint_sha256']
                or chosen['readiness'] != readiness):
            raise ValueError('Selected body configuration differs')
    if (original['epoch'] != selected['epoch']
            or original['event_thresholds'] != selected['event_thresholds']
            or original['body_threshold'] != selected['grid_body_threshold']
            or selected['checkpoint_sha256'] != readiness['checkpoint_sha256'][str(original['epoch'])]):
        raise ValueError('Calibration replay differs from verified selection configuration')
    recomputed = calibrate_run(SimpleNamespace(**common, replay=args.replay,
        output=args.output/'recomputed-calibration'))
    if original != recomputed:
        raise ValueError('Calibration candidate differs from authenticated recomputation')
    if any(sha(args.candidate/name) != digest for name, digest in pins.items()):
        raise ValueError('Original candidate changed during verification')
    result = dict(schema='clasher.v4.calibration-verification.v1', readiness=readiness,
        epoch=selected['epoch'], checkpoint_sha256=selected['checkpoint_sha256'],
        event_thresholds=selected['event_thresholds'], body_threshold=original['body_threshold'],
        input_sha256=pins,
        event_verification_sha256=sha(args.output/'recomputed-event-selection/event-selection-verified.json'),
        recomputed_candidate_sha256=sha(args.output/'recomputed-calibration/calibration-candidate.json'),
        verifier_sha256=sha(Path(__file__)),
        event_selection_verified=True, calibration_recomputed=True,
        body_selection_verified=body_verified, selection_provenance_verified=False,
        selection_seal=False, heldout_opening_authorized=False, heldout_payloads_opened=False,
        pending=['authenticate body threshold selection', 'final selection seal'])
    if body_verified:
        result['pending'].remove('authenticate body threshold selection')
    with (args.output/'calibration-verified.json').open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    with (args.output/'complete.json').open('x') as f:
        json.dump(dict(verification_sha256=sha(args.output/'calibration-verified.json'),
            body_selection_verified=body_verified, selection_seal=False,
            heldout_opening_authorized=False, heldout_payloads_opened=False), f, indent=2)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('run', 'source', 'split', 'phase-state', 'phase-exit', 'grid',
                 'selection', 'replay', 'candidate', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    verify_calibration(parser.parse_args())
