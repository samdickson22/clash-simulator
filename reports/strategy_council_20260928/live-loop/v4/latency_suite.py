"""Sequential fleet/Mac replay suite, frozen train membership before media access."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--matches', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--minimum-matches', type=int, default=6)
    p.add_argument('--minimum-taps', type=int, default=200)
    p.add_argument('--maximum-matches', type=int, default=16)
    p.add_argument('--device', choices=('cpu', 'mps'), default='cpu')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    root = Path.cwd()
    env = dict(os.environ, PYTHONPATH=f'{root}/src:{root}/engine-rs:{a.data}/python-deps',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               VECLIB_MAXIMUM_THREADS='1', YOLO_AUTOINSTALL='false')
    split = a.data/'registration/split.json'
    members = [r for r in json.loads(split.read_text())['matches'] if r['split'] == 'train']
    selected = []
    for row in sorted(members, key=lambda r: r['seed']):
        name = f"v4-phase-a-{row['seed']}"
        path = a.data/'matches'/name if (a.data/'matches'/name).exists() else a.matches/name
        if (path/'receipt.json').exists():
            selected.append((row['seed'], path))
    assert [s for s, _ in selected[:2]] == [1975100700, 1975100701]
    taps = 0
    receipts = []
    for seed, match in selected[:a.maximum_matches]:
        users = (len(subprocess.check_output(['who'], text=True).splitlines()) if sys.platform == 'darwin'
                 else int(subprocess.check_output([str(Path.home()/'.local/bin/fleet-console-users')], text=True).strip()))
        # Count all Python processes for this Unix account, including loaders.
        commands = subprocess.check_output(['ps', '-u', str(os.getuid()), '-o', 'comm='], text=True).splitlines()
        processes = sum('python' in c.lower() for c in commands)
        cap = 16 if users else 96
        if processes+7 > cap:
            raise RuntimeError(f'Fleet process capacity: {processes}+7 > {cap}')
        target = a.output/str(seed)
        cmd = [sys.executable, '-B', '-m', 'clasher.live', '--replay', str(match), '--split', str(split),
               '--prior', str(root/'reports/strategy_council_20260928/search-noise-s4/runtime/support/human_deck_catalog.json'),
               '--body', str(a.data/'weights/body.pt'), '--hud', str(a.data/'weights/hud.npz'),
               '--device', a.device, '--mock-input', '--output', str(target)]
        print(json.dumps(dict(seed=seed, started=time.time(), console_users=users, python_processes=processes,
                              load=os.getloadavg(), command=cmd)), flush=True)
        with (a.output/f'{seed}.log').open('x') as log:
            subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        metrics = json.loads((target/'metrics.json').read_text())
        assert not metrics['failures'] and not metrics['log_drops']
        taps += metrics['counts'].get('frame_to_tap', 0)
        receipts.append(dict(seed=seed, first_taps=metrics['counts'].get('frame_to_tap', 0),
                             processed=metrics['processed'], captured=metrics['captured']))
        (a.output/'suite.json').write_text(json.dumps(dict(matches=receipts, first_taps=taps), indent=2)+'\n')
        print(json.dumps(receipts[-1], sort_keys=True), flush=True)
        if len(receipts) >= a.minimum_matches and taps >= a.minimum_taps:
            break
    assert len(receipts) >= a.minimum_matches and taps >= a.minimum_taps, 'Insufficient first-attempt samples'


if __name__ == '__main__':
    main()
