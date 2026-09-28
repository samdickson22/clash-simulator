"""Record both idle Tesla trapdoors and HUD bars in the offline native renderer."""
import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from smoke_reference_battle import request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--adb', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.config.read_text())
    configured = request(26789, 'configure-native ' + json.dumps(config, separators=(',', ':')))
    for _ in range(100):
        status = request(26789, 'status')
        if status['nativeRenderLoaded'] == configured['sequence'] and status['nativeRenderReady']:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError('native renderer did not load requested scene')
    paused = request(26789, 'pause')
    tick = paused['tick']
    if tick > 200:
        raise RuntimeError('render startup exceeded deterministic command boundary')
    if tick < 200:
        assert request(26789, f'advance-native {200-tick}')['tick'] == 200
    before = request(26789, 'observe')
    for player in before['players']:
        assert any(c['cardId'] == 27000006 for c in player['hand'])
    receipts = []
    for owner, x, y in [(0, 5500, 11500), (1, 12500, 20500)]:
        receipts.append(request(26789, f'replay-schedule-card {owner} 27000006 {x} {y} 201'))
    advance = request(26789, 'advance-native 50')
    ordinary = request(26789, 'observe')
    assert ordinary['tick'] == 250
    teslas = [obj for obj in ordinary['objects'] if obj['cardId'] == 27000006]
    assert len(teslas) == 2 and {obj['owner'] for obj in teslas} == {0, 1}
    rich = request(26789, 'observe-rich')
    with (args.output / 'idle.png').open('xb') as target:
        subprocess.run([str(args.adb), '-s', 'emulator-5580', 'exec-out', 'screencap', '-p'], stdout=target, check=True)
    assert request(26789, 'observe') == ordinary
    result = {'config': config, 'before': before, 'receipts': receipts, 'advance': advance,
              'ordinary': ordinary, 'rich': rich, 'attestation': request(26789, 'attest'),
              'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'screenshot_sha256': hashlib.sha256((args.output / 'idle.png').read_bytes()).hexdigest(),
              'scope': 'Rendered native evidence; screenshot requires visual review, not automatic appearance acceptance.'}
    (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Captured paused rendered frame at tick250')


if __name__ == '__main__':
    main()
