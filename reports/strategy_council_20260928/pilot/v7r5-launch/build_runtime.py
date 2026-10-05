"""Copy v5 and overlay only the four requested learner modules; never overwrite a snapshot."""
import ast
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/sam/Desktop/code/clasher')
RC = ROOT / 'reports/strategy_council_20260928'
BASE = RC / 'm0/runtime-snapshots/pilot-runtime-v5'
OUT = BASE.with_name('pilot-runtime-v6')
KIT = Path(__file__).resolve().parent
OVERLAY = tuple(f'src/clasher/rl/{name}.py' for name in ('train_recurrent', 'parallel_rollout', 'tbptt', 'imitation'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise FileExistsError(f'refusing existing snapshot: {OUT}')
    manifest = json.loads((BASE / 'pilot-runtime.json').read_text())
    admission = json.loads(Path(manifest['admission_path']).read_text())
    before = {p.relative_to(BASE).as_posix(): sha(p) for p in BASE.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts}
    for relative in OVERLAY:
        if manifest['files'].get(relative, {}).get('class') == 'ADMISSION_BOUND':
            raise RuntimeError(f'STOP: overlay is admission-bound: {relative}')
    for relative, entry in manifest['files'].items():
        assert sha(BASE / relative) == entry['sha256'], relative
    shutil.copytree(BASE, OUT, symlinks=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.nbc', '*.nbi'))
    for relative in OVERLAY:
        target = OUT / relative
        if target.exists():
            target.chmod(0o644)
        shutil.copyfile(ROOT / relative, target)
        assert sha(target) == sha(ROOT / relative)
    bound = {}
    for relative, entry in manifest['files'].items():
        if entry['class'] == 'ADMISSION_BOUND':
            digest = sha(OUT / relative)
            assert digest == sha(BASE / relative) == entry['admission_sha256'] == admission['source_pins'][str(Path(manifest['base_snapshot']) / relative)], relative
            bound[relative] = digest
    assert len(bound) == 342
    actual_delta = sorted(relative for relative, digest in before.items() if sha(OUT / relative) != digest)
    assert actual_delta == sorted(set(OVERLAY) & before.keys()), actual_delta
    added = sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob('*.py') if p.relative_to(OUT).as_posix() not in before)
    assert added == ['src/clasher/rl/tbptt.py'], added
    manifest.update(created_at=datetime.now(timezone.utc).isoformat(), snapshot_root=str(OUT),
                    status='v7r5 learner overlay candidate; source-scope admission NOT passed',
                    parent_runtime=str(BASE), parent_manifest_sha256=sha(BASE / 'pilot-runtime.json'),
                    parent_pins_sha256=sha(BASE / 'pilot-source-pins.json'),
                    overlay={r: {'workspace_sha256': sha(ROOT / r), 'v5_sha256': before.get(r), 'v6_sha256': sha(OUT / r)} for r in OVERLAY},
                    test_log=None, bound_symbols_checked=None)
    for relative in OVERLAY:
        admitted_sha = manifest['files'].get(relative, {}).get('admission_sha256')
        manifest['files'][relative] = dict(class_='TRAINING_ONLY', sha256=sha(OUT / relative), admission_sha256=admitted_sha,
                                         changed_from_admission=admitted_sha != sha(OUT / relative))
        manifest['files'][relative]['class'] = manifest['files'][relative].pop('class_')
    pins = {str(OUT / r): e['sha256'] for r, e in sorted(manifest['files'].items())}
    pinpath = OUT / 'pilot-source-pins.json'
    pinpath.chmod(0o644)
    pinpath.write_text(json.dumps(pins, indent=2) + '\n')
    manifest['pilot_source_pins_path'] = str(pinpath)
    manifest['pilot_source_pins_sha256'] = sha(pinpath)
    manifest['counts'] = {'ADMISSION_BOUND': 342, 'TRAINING_ONLY': 10,
                          'TRAINING_ONLY_changed': sum(e['class'] == 'TRAINING_ONLY' and e['changed_from_admission'] for e in manifest['files'].values())}
    manifest['environment'] = {'CLASHER_ROOT': str(OUT), 'PYTHONPATH': f'{OUT}/src:{OUT}/scripts', 'PYTHONDONTWRITEBYTECODE': '1'}
    manifest['v5_admission_module_equality'] = bound
    path = OUT / 'pilot-runtime.json'
    path.chmod(0o644)
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    for directory, dirs, names in os.walk(OUT, followlinks=False):
        for name in names:
            p = Path(directory) / name
            if not p.is_symlink():
                p.chmod(0o444)
    assert (OUT / '.venv').is_symlink() and (OUT / '.venv').resolve() == (BASE / '.venv').resolve()
    assert all(sha(BASE / r) == d for r, d in before.items()), 'v5 changed during build'
    receipt = {'created_utc': datetime.now(timezone.utc).isoformat(), 'runtime': str(OUT),
               'manifest_sha256': sha(path), 'pins_sha256': sha(pinpath),
               'admission_bound_equal': len(bound), 'v5_files_unchanged_during_build': True,
               'overlay': manifest['overlay'], 'shared_venv': str((OUT / '.venv').resolve()),
               'counts': manifest['counts'], 'admission_status': 'not passed; scope verifier still rejects new tbptt module'}
    (KIT / 'logs/runtime-build.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
