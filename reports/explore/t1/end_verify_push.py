"""05-only, outcome-blind post-exit verification. No network or outcome reduction."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import time

BASE = Path('/mpac/sdicks02/jobs/clasher/t1-20261010-r1')


def namespace(root):
    assert root.is_absolute() and root == root.resolve(), 'Noncanonical receive path'
    assert root.parent.name in ('127x01', '127x08'), 'Missing host namespace'
    assert root.parent.parent == BASE / 'end-received', 'Wrong receive namespace'
    assert re.fullmatch(r'[A-Za-z0-9._-]+', root.name) and '..' not in root.name


def prepare(root):
    namespace(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    assert not list(root.iterdir()), 'Receive directory must start empty'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def verify(root):
    """Return a health receipt; emit no ACK for missing or inconsistent seals."""
    namespace(root)
    assert root.is_dir()
    for name in ('TRANSFER-COMPLETE.json', 'exit.json'):
        assert (root / name).is_file() and not (root / name).is_symlink(), name
    marker = json.loads((root / 'TRANSFER-COMPLETE.json').read_text())
    exit_ = json.loads((root / 'exit.json').read_text())
    assert marker['transfer_complete'] is True
    assert marker['host'] == exit_['host'] == root.parent.name
    assert marker['attempt'] == exit_['attempt'] == root.name
    code = exit_['exit_code']
    assert type(code) is int and 0 <= code <= 255
    assert marker['measurement_exit_code'] == code
    assert type(exit_['measurement_exists']) is bool
    assert marker['measurement_exists'] == exit_['measurement_exists']
    for name in ('detach.log', 'detach.json', 'argv.nul'):
        assert (root / name).is_file() and not (root / name).is_symlink(), name
    data = root / 'durable-measurement'
    assert exit_['measurement_exists'] == data.is_dir(), 'Directory/exit observation mismatch'
    seal = data / 'receipt-manifest.json'
    stamp = data / 'receipt-manifest.sha256'
    if not seal.is_file() or not stamp.is_file():
        return dict(utc=time.time(), host=root.parent.name, attempt=root.name,
                    classification='UNSEALED', exit_code=code, ack_allowed=False)
    assert data == data.resolve(), 'Symlink measurement directory'
    fields = stamp.read_text().split()
    assert fields == [sha(seal), 'receipt-manifest.json'], 'Seal SHA mismatch'
    manifest = json.loads(seal.read_text())
    assert manifest['status'] in ('complete', 'failed')
    assert (code == 0) == (manifest['status'] == 'complete'), 'Exit/status mismatch'
    files = manifest['files']
    assert isinstance(files, dict) and files
    for name, expected in files.items():
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts
        assert str(relative) == name and name not in ('receipt-manifest.json', 'receipt-manifest.sha256')
        target = data / relative
        assert target.is_file() and not target.is_symlink()
        assert os.path.commonpath((str(data), str(target.resolve()))) == str(data)
        assert sha(target) == expected, 'File SHA mismatch: ' + name
    entries = list(data.rglob('*'))
    assert not any(p.is_symlink() for p in entries), 'Symlink in measurement'
    actual = {str(p.relative_to(data)) for p in entries if p.is_file()}
    assert actual == set(files) | {'receipt-manifest.json', 'receipt-manifest.sha256'}, 'Extra/missing files'
    return dict(utc=time.time(), host=root.parent.name, attempt=root.name,
                classification='SEALED', status=manifest['status'], exit_code=code,
                ack_allowed=True, files=len(files), all_hashes_verified=True,
                receipt_manifest_sha256=sha(seal), outcomes_sealed=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--receive', required=True, type=Path)
    p.add_argument('--prepare', action='store_true')
    a = p.parse_args()
    assert socket.gethostname() == '127x05'
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.sched_getaffinity(0) == {63}
    if a.prepare:
        prepare(a.receive)
        print(json.dumps(dict(receive=str(a.receive), created_empty=True)))
        return 0
    result = verify(a.receive)
    target = a.receive / ('DURABLE-ACK.json' if result['ack_allowed'] else 'UNSEALED.json')
    with target.open('x') as stream:
        stream.write(json.dumps(result, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))
    return 0 if result['ack_allowed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
