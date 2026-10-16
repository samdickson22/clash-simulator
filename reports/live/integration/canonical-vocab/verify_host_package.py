"""Read-only hash guard for a reviewed combined package and its actual host base.

This validates files only. It never copies, changes environment/pins, deploys,
starts a process or authorizes detector enablement.
"""
import argparse
import hashlib
import json
from pathlib import Path

FILES = frozenset(('bot/live/translate.py', 'bot/live/births.py', 'bot/live/engine_body_aliases.json',
                   'bot/players/royalesim_translate.py', 'live/perception/yolo_units.py',
                   'yolo/classes.json', 'yolo/body-resolution-r3.json'))
ADDED_DATA = frozenset(('bot/live/engine_body_aliases.json', 'yolo/body-resolution-r3.json'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_path(name, repo_root, yolo_root):
    if name.startswith('yolo/'):
        return yolo_root / name[len('yolo/'):]
    return repo_root / name


def verify(package, repo_root, yolo_root, phase='base'):
    package, repo_root, yolo_root = map(Path, (package, repo_root, yolo_root))
    guard = json.loads((package / 'host-base-guards.json').read_text())
    if (guard.get('schema') != 'canonical-vocab-host-base-v1' or
            set(guard['release_sha256']) != FILES or
            set(guard['actual_original_sha256']) != FILES - ADDED_DATA or
            set(guard['unchanged_sha256']) != {'bot/players/royalesim_vocab.json'} or
            guard['complete_vocab_helper_sha256'] != guard['release_sha256']['bot/players/royalesim_translate.py']):
        raise ValueError('incomplete combined package/dependency guard')
    if phase not in ('base', 'released', 'rollback'):
        raise ValueError('unknown validation phase')
    for name, expected in guard['release_sha256'].items():
        p = package / 'release' / name
        if not p.is_file() or sha(p) != expected:
            raise ValueError('package payload mismatch: ' + name)
    expected = guard['release_sha256'] if phase == 'released' else guard['actual_original_sha256']
    for name, digest in expected.items():
        p = target_path(name, repo_root, yolo_root)
        if not p.is_file() or sha(p) != digest:
            raise ValueError('target mismatch: ' + name)
    for name, digest in guard['unchanged_sha256'].items():
        p = target_path(name, repo_root, yolo_root)
        if not p.is_file() or sha(p) != digest:
            raise ValueError('unchanged asset mismatch: ' + name)
    if phase != 'released':
        for name in set(guard['release_sha256']) - set(guard['actual_original_sha256']):
            p = target_path(name, repo_root, yolo_root)
            if p.exists() and (not p.is_file() or sha(p) != guard['release_sha256'][name]):
                raise ValueError('unexpected added-data file: ' + name)
    return dict(phase=phase, validated_files=len(expected), unchanged_assets=len(guard['unchanged_sha256']), read_only=True,
                deployment_authorized=False, detector_enablement_authorized=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--repo-root', type=Path, required=True)
    ap.add_argument('--yolo-root', type=Path, required=True)
    ap.add_argument('--phase', choices=('base', 'released', 'rollback'), default='base')
    args = ap.parse_args()
    print(json.dumps(verify(args.package, args.repo_root, args.yolo_root, args.phase)))


if __name__ == '__main__':
    main()
