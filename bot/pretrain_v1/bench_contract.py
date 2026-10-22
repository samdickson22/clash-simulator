"""Frozen input and source identities for selected-checkpoint latency measurements."""
import hashlib
import json
from pathlib import Path
import re


def digest(data):
    return hashlib.sha256(data).hexdigest()


def manifest(path):
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or not data:
        raise ValueError('record manifest must be a nonempty mapping')
    for name, sha in data.items():
        p = Path(name)
        if (not isinstance(name, str) or p.is_absolute() or '..' in p.parts or p.name != 'records.jsonl'
                or p.as_posix() != name or not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha)):
            raise ValueError('invalid record manifest entry')
    return data


def manifest_sha(data):
    return digest(json.dumps(data, sort_keys=True, separators=(',', ':')).encode())


def record_payloads(root, manifest_path):
    root = Path(root).resolve()
    expected = manifest_path if isinstance(manifest_path, dict) else manifest(manifest_path)
    paths = sorted(root.rglob('records.jsonl'))
    actual = {p.relative_to(root).as_posix(): p for p in paths}
    if set(actual) != set(expected):
        raise ValueError('staged records differ from exact manifest file set')
    payloads = []
    for name, p in sorted(actual.items()):
        if p.resolve() != p or not p.is_file():
            raise ValueError('record path is not a physical file under its root')
        raw = p.read_bytes()
        if digest(raw) != expected[name]:
            raise ValueError(f'staged record bytes changed: {name}')
        payloads.append((p, raw))
    return payloads


def runtime_sha():
    root = Path(__file__).resolve().parent
    names = ['bench_contract.py', 'bench_device.py', 'bench_selected.py', 'policy.py', 'model.py',
             'featurize.py', 'catalog/catalog.json']
    return manifest_sha({n: digest((root/n).read_bytes()) for n in names})
