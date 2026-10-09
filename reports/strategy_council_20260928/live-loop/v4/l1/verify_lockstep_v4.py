"""Independent exact-record/payload qualification; never production admission.

A pinned plan must name >=3 full epochs x>=8 matches including15..24, plus
epoch1 all64 matches and the three original09 reference cells. Prefix probes
cannot pass. Every compressed byte/hash, frame ordinal and new clock is checked.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path

from clasher.vision.l1_v4 import BodyTracker
from decoder_records_v4 import RecordedEventFusion
from lockstep_replay_v4 import validate_bundle, frame_times, nonclock, sha, json_bytes
from vectorized_gate_io_v4 import json_remote, lines_remote, validate_clock, compare_records, scope

REFERENCE_ROOTS = {
    '1': '/mpac/sdicks02/repos/clasher-lease/data/t7-validation-20261008-09r1/epoch-01-event-5-body-1',
    '2': '/mpac/sdicks02/repos/clasher-lease/data/t7-validation-20261008-09r2/epoch-01-event-5-body-2',
    '3': '/mpac/sdicks02/repos/clasher-lease/data/t7-validation-20261008-09r2/epoch-01-event-5-body-3',
}


def validate_plan(plan):
    if plan.get('schema') != 'clasher.v4.lockstep-equality-plan.v1':
        raise ValueError('Externally pinned lockstep equality plan required')
    scope(plan['captures'])
    if 1 not in {row['epoch'] for row in plan['captures']}:
        raise ValueError('Epoch1 reference population required')
    if set(plan['references']) != {'1', '2', '3'}:
        raise ValueError('All three original reference cells required')
    for body, root in REFERENCE_ROOTS.items():
        target = plan['references'][body]
        if target['host'] != '127x09' or target['root'] != root:
            raise ValueError('Only original09 reference cells permitted')
    for item in plan['captures']:
        if item['original']['host'] == '127x03':
            raise ValueError('03 access prohibited')
        if item['candidate'].get('host') not in (None, 'local'):
            raise ValueError('Stage verifier on the candidate host; no new remote services')
        root = Path(item['candidate']['root']).resolve()
        if not root.is_relative_to('/mpac/sdicks02/repos/clasher-v4-cache/lockstep-20261009'):
            raise ValueError('Only isolated candidate outputs')


def fresh_json(target, name, expected=None):
    if target.get('host') in (None, 'local'):
        path = Path(target['root'])/name
        value = json.loads(path.read_text()); digest = sha(path)
    else:
        value, digest = json_remote(target['host'], target['root']+'/'+name)
    if expected is not None and digest != expected:
        raise ValueError('Pinned manifest/completion changed')
    return value, digest


@contextmanager
def stream(target, name, pin, compressed=False):
    if target.get('host') not in (None, 'local'):
        with lines_remote(target['host'], target['root']+'/'+name, pin, compressed) as lines:
            yield iter(lines)
        return
    path = Path(target['root'])/name
    if path.is_symlink() or not path.resolve().is_relative_to(Path(target['root']).resolve()) or sha(path) != pin:
        raise ValueError('Candidate stream pin/path differs')
    before = path.stat()
    with (gzip.open(path, 'rb') if compressed else path.open('rb')) as f:
        yield iter(f)
        if f.read(1):
            raise ValueError('Unconsumed stream')
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns) or sha(path) != pin:
        raise ValueError('Candidate changed during verification')


def rows(target, name, pin, compressed=False):
    with stream(target, name, pin, compressed) as lines:
        return [json.loads(line) for line in lines]


def verify(plan, bundle):
    validate_plan(plan)
    bm, receipts, frames = validate_bundle(bundle)
    all_episodes = sorted(receipts); times = {ep: frame_times(frames[ep]) for ep in all_episodes}
    results = []; epoch1 = None
    for item in plan['captures']:
        epoch = item['epoch']; episodes = item['episodes']
        if not set(episodes) <= set(all_episodes) or (epoch == 1 and episodes != all_episodes):
            raise ValueError('Wrong validation population')
        old = item['original']; new = item['candidate']
        om, oh = fresh_json(old, 'manifest.json', old['manifest_sha256'])
        oc, och = fresh_json(old, 'complete.json', old['complete_sha256'])
        nm, nh = fresh_json(new, 'manifest.json', new['manifest_sha256'])
        nc, nch = fresh_json(new, 'complete.json', new['complete_sha256'])
        checkpoint = sha(bundle/'fit/model'/f'epoch-{epoch}.pt')
        for manifest in (om, nm):
            if (manifest['epoch'] != epoch or manifest['bundle_sha256'] != sha(bundle/'manifest.json')
                    or manifest['checkpoint_sha256'] != checkpoint or manifest['heldout_payloads_opened'] is not False
                    or manifest['spells'] != om['spells'] or manifest.get('body_thresholds') != [i/10 for i in range(1, 10)]
                    or manifest.get('event_threshold') != .5 or manifest.get('selection_seal') is not False):
                raise ValueError('Scientific manifest inputs differ')
        if om['schema'] != 'clasher.v4.shared-epoch-capture.v1':
            raise ValueError('Original admitted shared path required, quarantine cannot admit lockstep')
        if om.get('equality_sha256') != 'a32a16024899545b39b35b412a91e59af1d29c5366b2e5885fe29f2c20f8fd8f':
            raise ValueError('Original three-cell proof pin differs')
        if (nm['schema'] != 'clasher.v4.lockstep-experiment.v1' or nm['formal_admitted'] is not False
                or nm['frame_limit'] != 0 or nm['selection_seal'] is not False):
            raise ValueError('Full isolated experiment required')
        expected = {ep: len(times[ep]) for ep in episodes}
        if nc['episodes'] != expected or nc['frames'] != sum(expected.values()) or nc['files_sha256']['manifest.json'] != nh:
            raise ValueError('Candidate lacks complete full-match scope')
        comparisons = []
        for ep in episodes:
            for branch in range(1, 10):
                name = f'body-{branch}/{ep}-decoder.jsonl.gz'
                clock = f'body-{branch}/{ep}-completion.jsonl'
                with stream(old, name, oc['files_sha256'][name], True) as left, stream(new, name, nc['files_sha256'][name], True) as right:
                    equality = compare_records(left, right, ep, times[ep])
                if nc['record_stream_sha256'][f'{ep}/body-{branch}'] != equality['record_sha256']:
                    raise ValueError('Candidate record hash differs')
                clocks = rows(new, clock, nc['files_sha256'][clock]); validate_clock(clocks, ep, times[ep])
                # Replay original CPU tracker and fusion independently, compare
                # persisted candidate payloads including tracks/all HUD fields.
                records = rows(new, name, nc['files_sha256'][name], True)
                payload_name = f'body-{branch}/{ep}-payload.jsonl.gz'
                payloads = rows(new, payload_name, nc['files_sha256'][payload_name], True)
                if len(payloads) != len(times[ep]):
                    raise ValueError('Incomplete non-clock payloads')
                tracker = BodyTracker(high=branch/10); fusion = RecordedEventFusion(om['spells'], {'default': .5}, {})
                for record, payload in zip(records, payloads):
                    stamp = record['timestamp_ms']; tracks, _ = tracker.update(deepcopy(record['bodies']), stamp)
                    events = [asdict(e) for e in fusion.update(record['event_peaks'], stamp, stamp, record['causal_own_hud_cards'])]
                    expected_payload = nonclock(dict(episode_id=ep, timestamp_ms=stamp, tracks=tracks,
                        event_candidates=events, **record['hud']))
                    if json_bytes(payload) != json_bytes(expected_payload):
                        raise ValueError('Non-clock payload byte mismatch')
                comparisons.append(dict(episode=ep, body=branch, **equality, nonclock_payloads_equal=True))
        if fresh_json(new, 'complete.json')[1] != nch or fresh_json(old, 'complete.json')[1] != och:
            raise ValueError('Completion changed during verification')
        results.append(dict(epoch=epoch, comparisons=comparisons, candidate_complete_sha256=nch,
                            original_complete_sha256=och))
        if epoch == 1:
            epoch1 = new, nc, nm
    cells = {}; new, nc, nm = epoch1
    for body in ('1', '2', '3'):
        ref = plan['references'][body]
        rm, rh = fresh_json(ref, 'manifest.json', ref['manifest_sha256'])
        rc, rch = fresh_json(ref, 'complete.json', ref['complete_sha256'])
        if (rm.get('schema') != 'clasher.v4.validation-replay.v1' or rm.get('epoch') != 1
                or rm.get('threshold') != .5 or rm.get('body_threshold') != int(body)/10
                or rm.get('calibration') != {} or rm.get('event_thresholds') != {'default': .5}
                or rm.get('spells') != nm['spells'] or rc['manifest_sha256'] != rh
                or set(rc['episodes']) != set(all_episodes)):
            raise ValueError('Original reference cell differs')
        for ep in all_episodes:
            pname = f'body-{body}/{ep}-payload.jsonl.gz'
            candidate = rows(new, pname, nc['files_sha256'][pname], True)
            name = ep+'-outputs.jsonl'
            original = rows(ref, name, rc['files_sha256'][name])
            if len(candidate) != len(times[ep]) or len(original) != len(times[ep]):
                raise ValueError('Incomplete reference cell')
            for seq, (a, b) in enumerate(zip(candidate, original)):
                if b['source_seq'] != seq or json_bytes(a) != json_bytes(nonclock(b['payload'])):
                    raise ValueError('Original reference non-clock payload differs')
        if fresh_json(ref, 'complete.json')[1] != rch:
            raise ValueError('Reference completion changed')
        cells[body] = dict(matches=64, frames=106744, nonclock_payloads_equal=True, reference_complete_sha256=rch)
    return dict(schema='clasher.v4.lockstep-exactness.v1', full_required_scope_equal=True,
        captures=results, cells=cells, selection_admitted=False, formal_admitted=False,
        heldout_payloads_opened=False, source_sha256={Path(__file__).name: sha(Path(__file__))})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'bundle', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--plan-sha256', required=True)
    a = p.parse_args()
    if sha(a.plan) != a.plan_sha256 or a.output.exists():
        raise ValueError('Pinned plan and fresh receipt required')
    result = verify(json.loads(a.plan.read_text()), a.bundle)
    with a.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
