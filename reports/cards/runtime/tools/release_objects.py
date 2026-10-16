"""Copy an existing immutable card root to a NEW r3 root, apply committed Python patches, receipt and verify.
Run each operation under cpu_job.sh 1 on 04/08. No hardlinks; never writes parent roots.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import time
import tempfile

PATCHES = {
    'engine-cards/differential.py': 'engine-rs/differential.py',
    'reports/strategy_council_20260928/engine-speed/stage5/fair_player.py':
        'reports/strategy_council_20260928/engine-speed/stage5/fair_player.py',
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
    from bot.cards.build_runtime import write_text
    write_text(Path(path), json.dumps(obj, sort_keys=True, indent=2) + '\n')


def validate_layout(source, parent, target, out, *, creating):
    from bot.cards.build_runtime import base_inputs, reject_symlink_ancestors, validate_paths
    inputs = dict(base_inputs(parent), source=source)
    outputs = dict(receipt=out)
    if creating:
        outputs['target'] = target
    else:
        inputs['released root'] = target
    validate_paths(inputs, outputs)
    reject_symlink_ancestors(Path('/'), [out, target])
    assert not os.path.lexists(out), f'OUTPUT_EXISTS_STOP {out}'
    assert out.parent.is_dir(), f'output parent must exist: {out.parent}'


def publish_new(staging, target):
    """Linux atomic rename with NOREPLACE: even an empty existing root survives."""
    rename = ctypes.CDLL(None, use_errno=True).renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(staging), -100, os.fsencode(target), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(target))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('create', 'verify'))
    ap.add_argument('--name', required=True, choices=('live16402b-r3', 'r1-cards2-r3'))
    ap.add_argument('--source', type=Path, required=True, help='git archive of the source commit')
    ap.add_argument('--commit', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    roots = Path('/mpac/sdicks02/repos/clasher-bot-runtime')
    target, parent = roots / a.name, roots / (a.name.removesuffix('-r3') + '-r2')
    sys.path.insert(0, str(a.source))
    from bot.cards.build_runtime import install, reject_symlink_ancestors, validate_paths
    validate_layout(a.source, parent, target, a.out, creating=a.mode == 'create')
    from bot.players.runtime import PIN_SETS
    pins = PIN_SETS[a.name]
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
        assert digest(inventory(parent, exclude_receipt=True)) == original['content_manifest_sha256']
        final_target = target
        target = Path(tempfile.mkdtemp(prefix=a.name + '.assembling-', dir=roots))
        validate_paths(dict(parent=parent, source=a.source), dict(staging=target, target=final_target, receipt=a.out))
        subprocess.run(['nice', '-n', '15', 'rsync', '-a', '--checksum', str(parent) + '/', str(target) + '/'], check=True)
        assert digest(inventory(target)) == before
        target.chmod(target.stat().st_mode | stat.S_IWUSR)
        destinations=[target / dst for dst in PATCHES.values()]
        reject_symlink_ancestors(target, destinations + [target/'RECEIPT.json',target/'PARENT-R2-RECEIPT.json'])
        install(parent / 'RECEIPT.json', target / 'PARENT-R2-RECEIPT.json')
        changed = {}
        for src, dst in PATCHES.items():
            p = target / dst
            assert p.is_file() and not p.is_symlink(), f'patch must be a regular file: {p}'
            old = sha(p)
            p.parent.chmod(p.parent.stat().st_mode | stat.S_IWUSR)
            install(a.source / src, p)
            changed[dst] = dict(source=src, before=old, after=sha(p))
        overlay = {p: sha(target / p) for p in original['overlay_files']}
        overlay.update({dst: sha(target / dst) for dst in PATCHES.values()})
        receipt = dict(kind='released public-object identity closure', tier='exploration', no_sealing=True, pins=a.name, path=str(final_target),
                       created_utc=subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], text=True).strip(),
                       built_on=socket.gethostname(), source_commit=a.commit, runtime_pins_commit=a.commit,
                       parent=dict(path=str(parent), receipt_sha256=sha(parent / 'RECEIPT.json'), inventory_sha256=before),
                       native=dict(path='native/clasher_core.abi3.so', sha256=sha(target / 'native/clasher_core.abi3.so')),
                       gamedata=dict(path='gamedata.json', sha256=sha(target / 'gamedata.json')),
                       source_files={src:sha(a.source/src) for src in PATCHES},
                       overlay_manifest_sha256=digest(overlay),
                       changed_files=changed, overlay_files=overlay,
                       assembler_receipts=original['assembler_receipts'], base_r1_receipt=original['base_r1_receipt'])
        p = target / 'RECEIPT.json'
        assert p.is_file() and not p.is_symlink(), f'receipt must be a regular file: {p}'
        # Final manifest includes immutable modes and excludes this receipt to avoid self-reference.
        subprocess.run(['chmod', '-R', 'a-w', str(target)], check=True)
        receipt['content_manifest_sha256'] = digest(inventory(target, exclude_receipt=True))
        target.chmod(target.stat().st_mode | stat.S_IWUSR)
        write(p, receipt)
        p.chmod(p.stat().st_mode & ~0o222)
        target.chmod(target.stat().st_mode & ~0o222)
        assert readonly(target) and digest(inventory(parent)) == before
        assert not os.path.lexists(final_target), f'TARGET_EXISTS_STOP {final_target}'
        publish_new(target, final_target)
        write(a.out, receipt)
        print('CREATED', a.name, sha(final_target / 'RECEIPT.json'), flush=True)
        return
    receipt = json.loads((target / 'RECEIPT.json').read_text())
    assert receipt['source_commit'] == a.commit
    assert receipt['pins'] == a.name
    before = digest(inventory(parent))
    assert before == receipt['parent']['inventory_sha256']
    assert sha(parent / 'RECEIPT.json') == receipt['parent']['receipt_sha256']
    assert sha(target / 'PARENT-R2-RECEIPT.json') == receipt['parent']['receipt_sha256']
    assert readonly(target)
    assert digest(inventory(target, exclude_receipt=True)) == receipt['content_manifest_sha256']
    for path, expected in receipt['overlay_files'].items():
        assert sha(target / path) == expected, path
    assert digest(receipt['overlay_files']) == receipt['overlay_manifest_sha256']
    for path, expected in receipt['assembler_receipts'].items():
        assert sha(target / path) == expected, path
    for src, dst in PATCHES.items():
        assert sha(target / dst) == sha(a.source / src)
        assert receipt['source_files'][src] == sha(a.source / src)
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
               overlay_manifest_sha256=receipt['overlay_manifest_sha256'], source_files=receipt['source_files'],
               config_sha256=digest(rt.R.config),
               overlay_files_verified=len(receipt['overlay_files']), runtime_seconds=round(time.monotonic()-start, 3),
               metadata_cards=len(rt.R.meta['cards']), config_cards=len(rt.R.config['cards']), templates=len(rt.R.templates))
    write(a.out, out)
    print(json.dumps(out), flush=True)


if __name__ == '__main__':
    main()
