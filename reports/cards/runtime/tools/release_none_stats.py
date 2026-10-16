"""Copy an existing immutable card root to a NEW r2 root, apply committed Python patches, receipt and verify.
Run each operation under cpu_job.sh 1 on 04/08. No hardlinks; never writes parent roots.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import time

PATCHES = {
    'engine-cards/py/src/clasher/rl/c56_scripted.py': 'src/clasher/rl/c56_scripted.py',
    'engine-cards/c56_controller.py': 'engine-rs/c56_controller.py',
    'engine-cards/py/src/clasher/rl/public_scripted_opponent.py': 'src/clasher/rl/public_scripted_opponent.py',
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def digest(obj):
    return hashlib.sha256((json.dumps(obj, sort_keys=True, indent=2) + '\n').encode()).hexdigest()


def inventory(root, *, modes=True, exclude_receipt=False):
    rows = []
    for p in [root, *sorted(root.rglob('*'))]:
        rel = str(p.relative_to(root))
        if exclude_receipt and rel == 'RECEIPT.json':
            continue
        row = dict(path=rel)
        if modes:
            row['mode'] = stat.S_IMODE(p.lstat().st_mode)
        if p.is_symlink():
            row.update(kind='symlink', target=os.readlink(p))
        elif p.is_file():
            row.update(kind='file', sha256=sha(p))
        elif p.is_dir():
            row.update(kind='directory')
        else:
            raise RuntimeError(str(p))
        rows.append(row)
    return rows


def readonly(root):
    return all(p.is_symlink() or not p.stat().st_mode & 0o222 for p in [root, *root.rglob('*')])


def write(path, obj):
    Path(path).write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('create', 'verify', 'correct-assembly'))
    ap.add_argument('--name', required=True, choices=('live16402b-r2', 'r1-cards2-r2'))
    ap.add_argument('--source', type=Path, required=True, help='git archive of the source commit')
    ap.add_argument('--commit', required=True)
    ap.add_argument('--canonical-receipt', type=Path, help='byte-identical receipt from the corrected 08 assembly')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    roots = Path('/mpac/sdicks02/repos/clasher-bot-runtime')
    target, parent = roots / a.name, roots / a.name.removesuffix('-r2')
    sys.path.insert(0, str(a.source))
    from bot.players.runtime import PIN_SETS
    pins = PIN_SETS[a.name]
    if a.mode == 'correct-assembly':
        # Only this task's newly reserved, still-unreleased r2 assemblies qualify.
        # Parent roots are immutable inputs and are never opened for writing.
        previous = json.loads((target / 'RECEIPT.json').read_text())
        previous_sha = sha(target / 'RECEIPT.json')
        assert previous['source_commit'] == '9133b634ba1c20ea5e441014b8d4cb7c1db39f5d'
        assert previous_sha == {'r1-cards2-r2': 'b2c1a2e46585df1089781f7b064f834ed9dc9f28874add1cefcef1561b408ced',
                                'live16402b-r2': '92338abb973ef1100ca3969ec404346317135c915a0f27bfc754fe816eb022a0'}[a.name]
        assert readonly(target)
        assert digest(inventory(target, exclude_receipt=True)) == previous['content_manifest_sha256']
        before = digest(inventory(parent))
        assert before == previous['parent']['inventory_sha256']
        src = 'engine-cards/py/src/clasher/rl/public_scripted_opponent.py'
        dst = PATCHES[src]
        p = target / dst
        assert sha(p) == sha(parent / dst)
        old_hash = sha(p)
        p.chmod(p.stat().st_mode | stat.S_IWUSR)
        shutil.copyfile(a.source / src, p)
        p.chmod(p.stat().st_mode & ~0o222)
        receipt = json.loads(json.dumps(previous))
        receipt.update(source_commit=a.commit, runtime_pins_commit=a.commit)
        receipt['assembly_correction'] = dict(previous_receipt_sha256=previous_sha,
            previous_source_commit=previous['source_commit'],
            reason='Second audit finding before final release: ThreeMusketeers public body None HP; match engine fallback 100')
        receipt['changed_files'][dst] = dict(source=src, before=old_hash, after=sha(p))
        receipt['overlay_files'][dst] = sha(p)
        receipt['content_manifest_sha256'] = digest(inventory(target, exclude_receipt=True))
        if a.canonical_receipt:
            canonical = json.loads(a.canonical_receipt.read_text())
            assert canonical == receipt
            receipt = canonical
        p = target / 'RECEIPT.json'
        p.chmod(p.stat().st_mode | stat.S_IWUSR)
        write(p, receipt)
        p.chmod(p.stat().st_mode & ~0o222)
        assert readonly(target) and digest(inventory(parent)) == before
        assert digest(inventory(target, exclude_receipt=True)) == receipt['content_manifest_sha256']
        write(a.out, receipt)
        print('CORRECTED_ASSEMBLY', a.name, sha(p), flush=True)
        return
    if a.mode == 'create':
        assert not os.path.lexists(target), f'TARGET_EXISTS_STOP {target}'
        before = digest(inventory(parent))
        original = json.loads((parent / 'RECEIPT.json').read_text())
        assert readonly(parent)
        assert sha(parent / 'native/clasher_core.abi3.so') == pins['native_sha256']
        assert sha(parent / 'gamedata.json') == pins['gamedata_sha256']
        for path, expected in original['overlay_files'].items():
            assert sha(parent / path) == expected, path
        # Validate the parent's recorded full content with its historical manifest format.
        assert digest(inventory(parent, modes=False, exclude_receipt=True)) == original['source_content_manifest_sha256']
        target.mkdir()
        subprocess.run(['nice', '-n', '15', 'rsync', '-a', '--checksum', str(parent) + '/', str(target) + '/'], check=True)
        assert digest(inventory(target)) == before
        target.chmod(target.stat().st_mode | stat.S_IWUSR)
        shutil.copyfile(parent / 'RECEIPT.json', target / 'PARENT-RECEIPT.json')
        changed = {}
        for src, dst in PATCHES.items():
            p = target / dst
            old = sha(p)
            p.chmod(p.stat().st_mode | stat.S_IWUSR)
            shutil.copyfile(a.source / src, p)
            changed[dst] = dict(source=src, before=old, after=sha(p))
        overlay = {p: sha(target / p) for p in original['overlay_files']}
        receipt = dict(kind='released Python None-stat patch', pins=a.name, path=str(target),
                       created_utc=subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], text=True).strip(),
                       built_on=socket.gethostname(), source_commit=a.commit, runtime_pins_commit=a.commit,
                       parent=dict(path=str(parent), receipt_sha256=sha(parent / 'RECEIPT.json'), inventory_sha256=before),
                       native=dict(path='native/clasher_core.abi3.so', sha256=sha(target / 'native/clasher_core.abi3.so')),
                       gamedata=dict(path='gamedata.json', sha256=sha(target / 'gamedata.json')),
                       changed_files=changed, overlay_files=overlay,
                       assembler_receipts=original['assembler_receipts'], base_r1_receipt=original['base_r1_receipt'])
        p = target / 'RECEIPT.json'
        p.chmod(p.stat().st_mode | stat.S_IWUSR)
        # Final manifest includes immutable modes and excludes this receipt to avoid self-reference.
        subprocess.run(['chmod', '-R', 'a-w', str(target)], check=True)
        receipt['content_manifest_sha256'] = digest(inventory(target, exclude_receipt=True))
        p.chmod(p.stat().st_mode | stat.S_IWUSR)
        write(p, receipt)
        p.chmod(p.stat().st_mode & ~0o222)
        assert readonly(target) and digest(inventory(parent)) == before
        write(a.out, receipt)
        print('CREATED', a.name, sha(p), flush=True)
        return
    receipt = json.loads((target / 'RECEIPT.json').read_text())
    assert receipt['source_commit'] == a.commit
    assert receipt['pins'] == a.name
    before = digest(inventory(parent))
    assert before == receipt['parent']['inventory_sha256']
    assert sha(parent / 'RECEIPT.json') == receipt['parent']['receipt_sha256']
    assert sha(target / 'PARENT-RECEIPT.json') == receipt['parent']['receipt_sha256']
    assert readonly(target)
    assert digest(inventory(target, exclude_receipt=True)) == receipt['content_manifest_sha256']
    for path, expected in receipt['overlay_files'].items():
        assert sha(target / path) == expected, path
    for path, expected in receipt['assembler_receipts'].items():
        assert sha(target / path) == expected, path
    for src, dst in PATCHES.items():
        assert sha(target / dst) == sha(a.source / src)
    for key in ('CLASHER_ROOT', 'CLASHER_EVAL_RUNTIME_ROOT', 'CLASHER_DELAY_NATIVE_DIR'):
        os.environ.pop(key, None)
    os.environ['CLASHER_BOT_RUNTIME'] = str(target)
    os.environ['CLASHER_BOT_RUNTIME_PINS'] = a.name
    from bot.players.runtime import Runtime
    start = time.monotonic()
    rt = Runtime(verify=True)
    assert readonly(target) and digest(inventory(target, exclude_receipt=True)) == receipt['content_manifest_sha256']
    assert digest(inventory(parent)) == before
    out = dict(host=socket.gethostname(), root=str(target), result='PASS', verify=True,
               created_utc=subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], text=True).strip(),
               receipt_sha256=sha(target / 'RECEIPT.json'), native_sha256=sha(target / 'native/clasher_core.abi3.so'),
               gamedata_sha256=sha(target / 'gamedata.json'), source_commit=a.commit,
               content_manifest_sha256=receipt['content_manifest_sha256'], parent_unchanged=True, read_only=True,
               overlay_files_verified=len(receipt['overlay_files']), runtime_seconds=round(time.monotonic()-start, 3),
               metadata_cards=len(rt.R.meta['cards']), config_cards=len(rt.R.config['cards']), templates=len(rt.R.templates))
    write(a.out, out)
    print(json.dumps(out), flush=True)


if __name__ == '__main__':
    main()
