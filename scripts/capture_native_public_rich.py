"""Replay opened commands and bind paused rich frames to verified checkpoints."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from smoke_reference_battle import request

from clasher.data import CardDataLoader


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--level-adb', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    producer_digest = digest(Path(__file__))
    plan_path, result_path = args.capture / 'plan.json', args.capture / 'result.json'
    plan, result = json.loads(plan_path.read_text()), json.loads(result_path.read_text())
    loader = CardDataLoader()
    commands = {}
    for command in result['commands']:
        if command['execution_tick'] != command['submitted_tick'] + 1:
            raise ValueError('unsupported command delay')
        commands.setdefault(command['submitted_tick'], []).append(command)
    checkpoints = {c['tick']: c['native'] for c in result['checkpoints']}
    request(26789, 'configure ' + json.dumps(plan['config'], separators=(',', ':')))
    attestation = request(26789, 'attest')
    (args.output / 'attestation.json').write_text(json.dumps(attestation, indent=2) + '\n')
    tick, verified = 0, []
    output = args.output / 'frames.jsonl.gz'
    try:
        with gzip.open(output, 'xt') as stream:
            for target in sorted(set(commands) | set(checkpoints)):
                if target > max(checkpoints):
                    break
                if target > tick:
                    assert request(26789, f'step {target - tick}')['tick'] == target
                    tick = target
                if target in checkpoints:
                    ordinary = request(26789, 'observe')
                    for key in ('objects', 'players', 'tick', 'ended', 'winner', 'worldResult'):
                        if ordinary[key] != checkpoints[target][key]:
                            raise ValueError(f'replay mismatch at {target}: {key}')
                    rich = request(26789, 'observe-rich')
                    if ordinary != request(26789, 'observe') or rich['tick'] != tick or rich['truncated']:
                        raise ValueError('snapshot changed while paused or was truncated')
                    row = {'ordinary': ordinary, 'rich': rich}
                    if args.level_adb is not None:
                        from read_native_public_levels import read_levels
                        row['level_source'] = read_levels(args.level_adb)
                        if row['level_source']['ordinary'] != ordinary:
                            raise ValueError('level source frame changed')
                    stream.write(json.dumps(row, separators=(',', ':')) + '\n')
                    verified.append(tick)
                    if len(verified) % 10 == 0:
                        print('verified', len(verified), 'tick', tick, flush=True)
                for command in commands.get(target, []):
                    card = loader.get_card(command['name'])._raw_entry['id']
                    x, y = (round(v * 1000) for v in command['xy'])
                    request(26789, f"replay-schedule-card {command['owner']} {card} {x} {y} {tick + 1}")
    finally:
        manifest = {'source_plan_sha256': digest(plan_path), 'source_result_sha256': digest(result_path),
                    'producer_sha256': producer_digest, 'producer_unchanged': digest(Path(__file__)) == producer_digest, 'verified_checkpoint_ticks': verified,
                    'complete': len(verified) == len(checkpoints), 'actual_tick': tick,
                    'frames_sha256': digest(output), 'attestation_unchanged': request(26789, 'attest') == attestation,
                    'scope': 'Paused ordinary/rich diagnostic join; native private fields remain diagnostic only.'}
        (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if not manifest['complete'] or not manifest['attestation_unchanged'] or not manifest['producer_unchanged']:
        raise RuntimeError('capture validation incomplete')
    (args.output / 'producer.py').write_bytes(Path(__file__).read_bytes())
    print('verified', len(verified), 'checkpoints', flush=True)


if __name__ == '__main__':
    main()
