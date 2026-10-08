"""Authenticate a full formal validation replay, then score it; never heldout."""
import argparse
import json
from pathlib import Path

from execution_clock_v4 import ExecutionClock
from validation_admission_v4 import read, sha, validate_run
from validation_replay_v4 import completed_predictions, frame_times, threshold_options
from scoring_v4 import score_events


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def card_kinds(cards):
    from clasher.data import CardDataLoader
    loader = CardDataLoader()
    return {card:str(loader.get_card(card).card_type).lower() for card in cards}


def mapped_truth(frames, events, episode, kinds):
    clock = ExecutionClock(frames)
    result, identities = [], set()
    for event in events:
        if type(event['accepted']) is not bool:
            raise ValueError('Invalid event acceptance status')
        if not event['accepted']:
            continue
        if event['event_id'] in identities:
            raise ValueError('Duplicate accepted event identity')
        identities.add(event['event_id'])
        kind = 'champion_ability' if event['kind'] == 'champion ability' else kinds[event['card']]
        if kind not in ('troop', 'building', 'spell', 'champion_ability'):
            raise ValueError('Unknown canonical event kind')
        result.append(dict(clock.map_tick(event['exec_tick']), episode_id=episode,
            event_id=event['event_id'], card=event['card'], side=event['side'], kind=kind,
            stratum=event['kind'], x_tiles=event['tile'][0], y_tiles=event['tile'][1]))
    return result


def load_replay(args):
    """Authenticate complete raw-score replay/truth once, for scoring or fitting."""
    admission = validate_run(args.run, args.source, args.split, args.phase_state, args.phase_exit)
    replay = args.replay
    manifest, complete = read(replay/'manifest.json'), read(replay/'complete.json')
    if (manifest.get('schema') != 'clasher.v4.validation-replay.v1'
            or manifest.get('readiness') != admission or manifest.get('calibration') != {}
            or manifest.get('heldout_payloads_opened') is not False
            or manifest.get('selection_seal') is not False
            or manifest.get('device') != 'cuda' or manifest.get('precision') != 'fp32'
            or type(manifest.get('epoch')) is not int or not 1 <= manifest['epoch'] <= 24
            or manifest.get('threshold') not in [i/10 for i in range(1, 10)]
            or type(manifest.get('body_threshold')) not in (int,float)
            or manifest['body_threshold'] not in [i/10 for i in range(1,10)]):
        raise ValueError('Replay differs from admitted formal validation configuration')
    thresholds=threshold_options(manifest['threshold'],manifest.get('event_thresholds'))
    if manifest.get('event_thresholds')!=thresholds or manifest.get('replay_mode') not in ('grid','combined'):
        raise ValueError('Explicit event threshold configuration required')
    if manifest['replay_mode']=='grid':
        if thresholds!={'default':manifest['threshold']} or manifest.get('threshold_map_sha256') is not None:
            raise ValueError('Global grid cannot contain a per-card threshold map')
    else:
        digest=manifest.get('threshold_map_sha256')
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Combined threshold input SHA required')
    if (manifest.get('driver_sha256') != sha(Path(__file__).with_name('validation_replay_v4.py'))
            or complete.get('manifest_sha256') != sha(replay/'manifest.json')
            or complete.get('heldout_payloads_opened') is not False
            or complete.get('selection_seal') is not False):
        raise ValueError('Replay source/completion changed')
    episodes = sorted(admission['validation_receipt_sha256'])
    expected = {f'{ep}-{suffix}.jsonl' for ep in episodes for suffix in ('outputs', 'completion')}
    if set(complete['files_sha256']) != expected or set(complete['episodes']) != set(episodes):
        raise ValueError('Incomplete or extra replay population')
    for name, digest in complete['files_sha256'].items():
        if sha(replay/name) != digest:
            raise ValueError('Replay file hash changed')
    predictions, truth, provenance = [], [], {}
    for ep in episodes:
        folder = args.source/ep
        if sha(folder/'receipt.json') != admission['validation_receipt_sha256'][ep]:
            raise ValueError('Validation receipt changed')
        receipt = read(folder/'receipt.json')
        if receipt['split'] != 'validation' or receipt['episode'] != ep:
            raise ValueError('Validation split isolation failure')
        for name in ('frames.jsonl', 'events.jsonl'):
            if sha(folder/name) != receipt['files'][name]:
                raise ValueError('Validation truth/frame payload changed')
        frames, events = rows(folder/'frames.jsonl'), rows(folder/'events.jsonl')
        times = frame_times(frames)
        if len(frames) != receipt['frames'] or complete['episodes'][ep]['frames'] != len(frames):
            raise ValueError('Replay frame count differs from admitted source')
        outputs, completions = rows(replay/f'{ep}-outputs.jsonl'), rows(replay/f'{ep}-completion.jsonl')
        if [r['timestamp_ms'] for r in completions] != times:
            raise ValueError('Replay production timestamps differ from source')
        pred = completed_predictions(outputs, completions, episode=ep,
                                     expected_frames=len(frames), calibration=manifest['calibration'])
        if complete['episodes'][ep]['final_available_timestamp_ms'] != completions[-1]['available_timestamp_ms']:
            raise ValueError('Replay completion summary changed')
        kinds = card_kinds({e['card'] for e in events if e['accepted'] and e['kind'] != 'champion ability'})
        mapped = mapped_truth(frames, events, ep, kinds)
        if len(mapped) != receipt['accepted_events']:
            raise ValueError('Accepted-event population differs from receipt')
        predictions.extend(pred)
        truth.extend(mapped)
        provenance[ep] = {name:receipt['files'][name] for name in ('frames.jsonl', 'events.jsonl')}
    return dict(manifest=manifest,admission=admission,predictions=predictions,truth=truth,
                provenance=provenance,episodes=episodes,thresholds=thresholds,
                replay_manifest_sha256=sha(replay/'manifest.json'),
                replay_completion_sha256=sha(replay/'complete.json'))


def score_run(args):
    loaded=load_replay(args)
    manifest,admission=loaded['manifest'],loaded['admission']
    predictions,truth,episodes=loaded['predictions'],loaded['truth'],loaded['episodes']
    return dict(schema='clasher.v4.validation-score.v1', epoch=manifest['epoch'], threshold=manifest['threshold'],
        body_threshold=manifest['body_threshold'],
        replay_mode=manifest['replay_mode'],event_thresholds=loaded['thresholds'],
        readiness=admission,
        point=score_events(predictions, truth, episodes=episodes),
        conservative=score_events(predictions, truth, episodes=episodes, timing='conservative'),
        replay_manifest_sha256=loaded['replay_manifest_sha256'], replay_completion_sha256=loaded['replay_completion_sha256'],
        sources={p.name:sha(p) for p in [Path(__file__), Path(__file__).with_name('execution_clock_v4.py'),
                                        Path(__file__).with_name('scoring_v4.py')]},
        validation_receipts=admission['validation_receipt_sha256'], truth_payloads=loaded['provenance'],
        timing_certified=False, heldout_payloads_opened=False, selection_seal=False,
        scope='single fleet validation cell; no epoch/threshold selection or formal gate certification')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('run', 'source', 'split', 'phase-state', 'phase-exit', 'replay', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    result = score_run(args)
    with args.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
