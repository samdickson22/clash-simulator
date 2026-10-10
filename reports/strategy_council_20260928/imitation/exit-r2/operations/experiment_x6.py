"""Compose the coordinator's X6 addendum without replacing the X1–X5 freeze."""
import hashlib
import json

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_experiment(job):
    original = json.loads((job/'freeze.json').read_text())
    amendment = json.loads((job/'x6-addendum.json').read_text())
    assert amendment['committed_before_launch']
    assert amendment['base_freeze_sha256'] == sha(job/'freeze.json')
    assert amendment['seed_audit_sha256'] == sha(job/'x6-seed-audit.json')
    audit = json.loads((job/'x6-seed-audit.json').read_text())
    assert audit['passed']
    for relative, expected in amendment['files'].items():
        assert sha(job/relative) == expected, relative
    assert 'X6' not in original['arms']
    original['arms']['X6'] = amendment['arm']
    return original
