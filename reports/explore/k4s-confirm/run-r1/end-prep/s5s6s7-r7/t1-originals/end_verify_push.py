"""05-only, outcome-blind post-exit verification. No network or outcome reduction."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import time
import datetime
import uuid

if not __debug__:
    raise SystemExit("END verifier refuses optimized Python")


def require(condition, message):
    if not condition:
        raise ValueError(message)

BASE = Path('/mpac/sdicks02/jobs/clasher/t1-20261010-r1')


def namespace(root):
    require(root.is_absolute() and root == root.resolve(), 'Noncanonical receive path')
    require(root.parent.name in ('127x01', '127x08'), 'Missing host namespace')
    require(root.parent.parent == BASE / 'end-received', 'Wrong receive namespace')
    require(re.fullmatch(r'[A-Za-z0-9._-]+', root.name) and '..' not in root.name, 'Verification check failed')


def prepare(root):
    namespace(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    require(not list(root.iterdir()), 'Receive directory must start empty')
    proof = dict(receive=str(root), host=root.parent.name, attempt=root.name,
                 created_empty=True, nonce=uuid.uuid4().hex,
                 utc=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    with (root / 'PREPARED.json').open('x') as stream:
        stream.write(json.dumps(proof, sort_keys=True) + '\n')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def verify(root, launch, prepared):
    """Return a health receipt; emit no ACK for missing or inconsistent seals."""
    namespace(root)
    require(root.is_dir(), 'Verification check failed')
    if (root / 'PUSH-FAILED.json').exists():
        failure = json.loads((root / 'PUSH-FAILED.json').read_text())
        code = failure.get('rsync_exit_code', 'legacy-unspecified')
        raise ValueError('PUSH-FAILED prohibits ACK; rsync_exit_code=' + str(code))
    require((root / 'PREPARED.json').is_file() and not (root / 'PREPARED.json').is_symlink(), 'Receive was not prepared')
    proof = json.loads((root / 'PREPARED.json').read_text())
    require(proof == prepared, 'Receive preparation proof changed')
    require(proof['created_empty'] is True and re.fullmatch(r'[0-9a-f]{32}', proof['nonce']), 'Invalid preparation proof')
    require(proof['receive'] == str(root) and proof['host'] == root.parent.name and proof['attempt'] == root.name, 'Preparation namespace mismatch')
    require(launch['host'] == root.parent.name and Path(launch['job']).name == root.name, 'Launch namespace mismatch')
    for name in ('TRANSFER-COMPLETE.json', 'exit.json'):
        require((root / name).is_file() and not (root / name).is_symlink(), name)
    marker = json.loads((root / 'TRANSFER-COMPLETE.json').read_text())
    exit_ = json.loads((root / 'exit.json').read_text())
    require(marker['transfer_complete'] is True, 'Verification check failed')
    require(marker['host'] == exit_['host'] == root.parent.name, 'Verification check failed')
    require(marker['attempt'] == exit_['attempt'] == root.name, 'Verification check failed')
    code = exit_['exit_code']
    require(type(code) is int and 0 <= code <= 255, 'Verification check failed')
    require(marker['measurement_exit_code'] == code, 'Verification check failed')
    exit_epoch = datetime.datetime.strptime(exit_['utc'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp()
    require((root / 'TRANSFER-COMPLETE.json').stat().st_mtime >= exit_epoch, 'Transfer marker predates recorded exit')
    require(proof['utc'] < launch['utc'] <= exit_['utc'] <= marker['utc'], 'Preparation must precede launch; transfer must follow exit')
    require(launch['wrapper_sha256'] == '0a87166f23f1eec742605da1f15e94f40602546a6926c7a53bc15d2a6b8d61b1', 'Unapproved END campaign wrapper')
    expected_argv = b''.join(value.encode() + b'\0' for value in launch['measurement_argv'])
    require((root / 'argv.nul').read_bytes() == expected_argv, 'Recorded argv differs from approved launch')
    require(type(exit_['measurement_exists']) is bool, 'Verification check failed')
    require(marker['measurement_exists'] == exit_['measurement_exists'], 'Verification check failed')
    for name in ('detach.log', 'detach.json', 'argv.nul'):
        require((root / name).is_file() and not (root / name).is_symlink(), name)
    data = root / 'durable-measurement'
    require(exit_['measurement_exists'] == data.is_dir(), 'Directory/exit observation mismatch')
    seal = data / 'receipt-manifest.json'
    stamp = data / 'receipt-manifest.sha256'
    if not seal.is_file() or not stamp.is_file():
        return dict(utc=time.time(), host=root.parent.name, attempt=root.name,
                    classification='UNSEALED', exit_code=code, ack_allowed=False)
    require(data == data.resolve(), 'Symlink measurement directory')
    fields = stamp.read_text().split()
    require(fields == [sha(seal), 'receipt-manifest.json'], 'Seal SHA mismatch')
    manifest = json.loads(seal.read_text())
    require(manifest['status'] in ('complete', 'failed'), 'Verification check failed')
    require((code == 0) == (manifest['status'] == 'complete'), 'Exit/status mismatch')
    files = manifest['files']
    require(isinstance(files, dict) and files, 'Verification check failed')
    for name, expected in files.items():
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'Verification check failed')
        require(str(relative) == name and name not in ('receipt-manifest.json', 'receipt-manifest.sha256'), 'Verification check failed')
        target = data / relative
        require(target.is_file() and not target.is_symlink(), 'Verification check failed')
        require(os.path.commonpath((str(data), str(target.resolve()))) == str(data), 'Verification check failed')
        require(sha(target) == expected, 'File SHA mismatch: ' + name)
    entries = list(data.rglob('*'))
    require(not any(p.is_symlink() for p in entries), 'Symlink in measurement')
    actual = {str(p.relative_to(data)) for p in entries if p.is_file()}
    require(actual == set(files) | {'receipt-manifest.json', 'receipt-manifest.sha256'}, 'Extra/missing files')
    return dict(utc=time.time(), host=root.parent.name, attempt=root.name,
                classification='SEALED', status=manifest['status'], exit_code=code,
                ack_allowed=True, files=len(files), all_hashes_verified=True,
                receipt_manifest_sha256=sha(seal), outcomes_sealed=True,
                legacy_PUSH_FAILED_without_exit_code_is_failure=True,
                prepared_nonce=proof['nonce'], approved_legacy_wrapper=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--receive', required=True, type=Path)
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--launch-receipt', type=Path)
    p.add_argument('--launch-receipt-sha256')
    p.add_argument('--prepare-proof', type=Path)
    p.add_argument('--prepare-proof-sha256')
    a = p.parse_args()
    require(socket.gethostname() == '127x05', 'Verification check failed')
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.sched_getaffinity(0) == {63}, 'Verification check failed')
    if a.prepare:
        prepare(a.receive)
        print(json.dumps(dict(receive=str(a.receive), created_empty=True)))
        return 0
    require(all((a.launch_receipt, a.launch_receipt_sha256, a.prepare_proof, a.prepare_proof_sha256)), 'Verification requires pinned launch and preparation proofs')
    require(sha(a.launch_receipt) == a.launch_receipt_sha256, 'Launch receipt SHA mismatch')
    require(sha(a.prepare_proof) == a.prepare_proof_sha256, 'Preparation proof SHA mismatch')
    result = verify(a.receive, json.loads(a.launch_receipt.read_text()), json.loads(a.prepare_proof.read_text()))
    target = a.receive / ('DURABLE-ACK.json' if result['ack_allowed'] else 'UNSEALED.json')
    with target.open('x') as stream:
        stream.write(json.dumps(result, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))
    return 0 if result['ack_allowed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
