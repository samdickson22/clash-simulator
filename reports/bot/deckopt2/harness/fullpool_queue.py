"""Light05 atomic case-block claims: all arms of one case stay on one host."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2/fullpool')


def utc():
    return subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], text=True).strip()


def claim(worker):
    assert re.fullmatch(r'127x0[134]-[a-zA-Z0-9_-]+', worker), worker
    if (ROOT / 'STOP').exists():
        return None
    gate = json.loads((ROOT / 'gate-approved.json').read_text())
    assert gate['approved'] is True
    bank = json.loads((ROOT / 'validation/bank.json').read_text())
    dest = ROOT / 'claims'
    dest.mkdir(exist_ok=True)
    for index in bank['dispatch_order']:
        path = dest / f'{index:04d}.json'
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(fd, 'w') as stream:
            json.dump(dict(utc=utc(), worker=worker, index=index, case_id=bank['cases'][index]['id']), stream)
        return index
    return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', required=True)
    args = parser.parse_args()
    print(json.dumps(dict(index=claim(args.worker))))
