"""Fail-closed content/role guards; no model imports or held-out reads."""
import hashlib
import json
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def write_once(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def qualification(root):
    root = Path(root)
    path = root/'imitation/model/receipts/throughput-pass.json'
    r = json.loads(path.read_text())
    if (r.get('schema') != 'clasher.imitation.t4-throughput.v1' or
            r.get('passed') is not True or r.get('status') != 'PASS' or
            r.get('exit_code') != 0 or r.get('effective_batch') != 8192 or
            r.get('single', {}).get('sum_rows_per_second_including_loader', 0) < 8000):
        raise ValueError('missing explicit qualified throughput PASS/provenance')
    if canonical_hash(r['files']) != r['code_sha256']:
        raise ValueError('invalid qualified source manifest')
    for name, expected in r['files'].items():
        if sha(root/name) != expected:
            raise ValueError('qualified source changed: '+name)
    return r, sha(path)


def frozen(root, manifest_path):
    root, manifest_path = Path(root), Path(manifest_path)
    m = json.loads(manifest_path.read_text())
    r, receipt_sha = qualification(root)
    if m['throughput_receipt_sha256'] != receipt_sha or m['qualified_code_sha256'] != r['code_sha256']:
        raise ValueError('freeze/qualification mismatch')
    for name, digest in m['files'].items():
        p = (root/name).resolve()
        if not p.is_relative_to(root.resolve()) or sha(p) != digest:
            raise ValueError('frozen source changed: '+name)
    prereg = manifest_path.parent/'PREREG.md'
    freeze = json.loads((manifest_path.parent/'freeze.json').read_text())
    if sha(manifest_path) != freeze['manifest_sha256'] or sha(prereg) != freeze['prereg_sha256']:
        raise ValueError('registration freeze changed')
    return m, {'T5_manifest': sha(manifest_path), 'T5_prereg': sha(prereg),
               'T4_throughput': receipt_sha, 'T4_code': r['code_sha256']}


def role_guard(directory, role, manifest, heldout=False):
    directory = Path(directory)
    allowed = ('eval', 'eval_ood') if heldout else ('train', 'dev')
    if role not in allowed or directory.name != role:
        raise ValueError('unauthorized role')
    if sha(directory/'manifest.json') != manifest['role_manifests'][role]:
        raise ValueError('role content hash mismatch')
    if sha(directory.parent/'manifest.json') != manifest['store_manifest_sha256']:
        raise ValueError('store content hash mismatch')
