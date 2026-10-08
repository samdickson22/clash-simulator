"""Synthetic orchestration checks; real admission/scoring have separate suites."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import verify_calibration_v4 as driver


def main(root):
    checks = 0
    def check(value):
        nonlocal checks
        assert value; checks += 1
    def refuses(fn):
        nonlocal checks
        try: fn()
        except ValueError: checks += 1
        else: raise AssertionError('Invalid calibration verification accepted')
    def put(path, value): path.write_text(json.dumps(value))
    empty = SimpleNamespace(run=None, source=None, split=None, phase_state=None, phase_exit=None)
    with patch.object(driver, 'validate_run', side_effect=ValueError('Producer incomplete')):
        refuses(lambda: driver.verify_calibration(empty))
    root.mkdir(); candidate = root/'candidate'; candidate.mkdir()
    readiness = dict(checkpoint_sha256={'4': 'a'*64}, validation_receipt_sha256={'ep': 'b'*64})
    flags = dict(selection_provenance_verified=False, selection_seal=False,
                 heldout_opening_authorized=False, heldout_payloads_opened=False)
    original = dict(schema='clasher.v4.calibration-candidate.v1', readiness=readiness,
        epoch=4, body_threshold=.6, event_thresholds={'default': .5, 'Fireball': .7},
        candidate={'calibration': {'default': [[0, .2], [1, .8]]}}, **flags)
    selected = dict(readiness=readiness, epoch=4, grid_body_threshold=.6,
        event_thresholds=original['event_thresholds'], checkpoint_sha256='a'*64,
        event_selection_verified=True, body_selection_verified=False,
        selection_seal=False, heldout_opening_authorized=False, heldout_payloads_opened=False)
    def save_original(value=original):
        put(candidate/'calibration-candidate.json', value)
        put(candidate/'complete.json', dict(candidate_sha256=driver.sha(candidate/'calibration-candidate.json'), **flags))
    save_original()
    calls = []
    def events(args):
        calls.append('events'); args.output.mkdir()
        put(args.output/'event-selection-verified.json', selected)
        return deepcopy(selected)
    def calibration(args):
        calls.append('calibration'); args.output.mkdir()
        put(args.output/'calibration-candidate.json', original)
        return deepcopy(original)
    def args(name):
        return SimpleNamespace(**vars(empty), candidate=candidate, grid=root/'grid.json',
            selection=root/'selection', replay=root/'replay', output=root/name)
    with patch.object(driver, 'validate_run', return_value=readiness), \
            patch.object(driver, 'verify_events', side_effect=events), \
            patch.object(driver, 'calibrate_run', side_effect=calibration):
        result = driver.verify_calibration(args('pass'))
        check(calls == ['events', 'calibration'])
        check(result['event_selection_verified'] and result['calibration_recomputed'])
        check(all(result[k] is False for k in (*flags, 'body_selection_verified')))
        check(json.loads((root/'pass/complete.json').read_text())['verification_sha256'] == driver.sha(root/'pass/calibration-verified.json'))
        refuses(lambda: driver.verify_calibration(args('pass')))
        for i, change in enumerate(({'epoch': 3}, {'body_threshold': .7},
                {'event_thresholds': {'default': .8}}, {'readiness': {}},
                {'candidate': {'calibration': {'default': [[0, 1], [1, 1]]}}},
                {'selection_seal': True}, {'heldout_opening_authorized': True})):
            bad = deepcopy(original); bad.update(change); save_original(bad)
            refuses(lambda: driver.verify_calibration(args('bad-'+str(i))))
            check(not (root/('bad-'+str(i))/'complete.json').exists())
        save_original()
        with patch.object(driver, 'verify_events', side_effect=ValueError('Forged event selection')):
            refuses(lambda: driver.verify_calibration(args('bad-event-evidence')))
        def tamper(args):
            result = calibration(args)
            (candidate/'complete.json').write_text('{}')
            return result
        with patch.object(driver, 'calibrate_run', side_effect=tamper):
            refuses(lambda: driver.verify_calibration(args('changed-during-fit')))
        save_original()
        for i, change in enumerate(({'checkpoint_sha256': 'c'*64}, {'readiness': {}},
                                   {'body_selection_verified': True}, {'heldout_payloads_opened': True})):
            bad = deepcopy(selected); bad.update(change)
            with patch.object(driver, 'verify_events', return_value=bad):
                refuses(lambda: driver.verify_calibration(args('bad-verified-'+str(i))))
        check(json.loads((candidate/'calibration-candidate.json').read_text()) == original)
        selected['body_selection_verified']=True
        selected['body_selections']={str(i):dict(ranking=dict(readiness=readiness,
            body_threshold=.6,checkpoint_sha256='a'*64)) for i in range(1,25)}
        authenticated=driver.verify_calibration(args('body-verified'))
        check(authenticated['body_selection_verified'] is True and authenticated['selection_seal'] is False)
        check(authenticated['pending']==['final selection seal'])
    print(json.dumps(dict(checks=checks, passed=True, synthetic_only=True,
        body_selection_verified=False, selection_seal=False, heldout_payloads_opened=False)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
