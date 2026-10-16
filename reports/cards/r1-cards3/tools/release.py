"""Release only the verified cards3 dev snapshots; existing destinations always stop.

prepare runs once on08, create/verify on03/04/08. Use cpu_job.sh <=4,
single-thread libraries, -B and nice15. No hardlinks, no existing-root writes.
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
import tempfile
import time

NAMES = ('r1-cards3', 'live16402c')
ENGINE = '8eaa7d1ecac2f46a2c7d8d512a46ba4f03f7cb63'
NATIVE = '326ce6f93c4db6a7bd15b667960a2d3ed40a0d48eab3badc9ddd181521996732'
RUNTIMES = Path('/mpac/sdicks02/repos/clasher-bot-runtime')
DEVS = Path('/mpac/sdicks02/jobs/clasher/cards/runtime')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''): h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256((json.dumps(value, indent=2, sort_keys=True) + '\n').encode()).hexdigest()


def inventory(root, exclude_receipt=False):
    rows = []
    for p in [root, *sorted(root.rglob('*'))]:
        rel = str(p.relative_to(root))
        if exclude_receipt and rel == 'RECEIPT.json': continue
        row = dict(path=rel, mode=stat.S_IMODE(p.lstat().st_mode))
        if p.is_symlink(): row.update(kind='symlink', target=os.readlink(p))
        elif p.is_file(): row.update(kind='file', sha256=sha(p))
        elif p.is_dir(): row.update(kind='directory')
        else: raise RuntimeError(str(p))
        rows.append(row)
    return rows


def readonly(root):
    return all(p.is_symlink() or not p.lstat().st_mode & 0o222 for p in [root, *root.rglob('*')])


def freeze(root):
    for p in [*root.rglob('*'), root]:
        if not p.is_symlink(): p.chmod(stat.S_IMODE(p.lstat().st_mode) & ~0o222)
    assert readonly(root)


def absent(path):
    assert not os.path.lexists(path), f'TARGET_EXISTS_STOP {path}'


def no_symlink_ancestors(path):
    for p in [path, *path.parents]:
        assert not p.is_symlink(), f'SYMLINK_PATH_STOP {p}'


def write_new(path, value):
    absent(path)
    with path.open('x') as stream: stream.write(json.dumps(value, indent=2, sort_keys=True) + '\n')


def copy_tree(source, target):
    subprocess.run(['rsync', '-a', '--checksum', str(source) + '/', str(target) + '/'], check=True)


def publish(staging, target):
    rename = ctypes.CDLL(None, use_errno=True).renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(staging), -100, os.fsencode(target), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(target))


def parents():
    out = {}
    for name in ('r1-cards2-r3', 'live16402b-r3'):
        p = RUNTIMES / name
        assert readonly(p)
        r = json.loads((p / 'RECEIPT.json').read_text())
        assert digest(inventory(p, True)) == r['content_manifest_sha256']
        out[name] = dict(receipt_sha256=sha(p / 'RECEIPT.json'), inventory_sha256=digest(inventory(p)))
    return out


def prepare(job):
    target = job / 'publish-inputs'
    absent(target); no_symlink_ancestors(target)
    target.mkdir()
    assembly = json.loads((job / 'ASSEMBLY.json').read_text())
    result = dict(engine_commit=ENGINE, assembly_sha256=sha(job / 'ASSEMBLY.json'), roots={})
    for name in NAMES:
        source = DEVS / (name + '-dev')
        record = assembly['roots'][str(source)]
        assert sha(source / 'native/clasher_core.abi3.so') == record['native'] == NATIVE
        assert sha(source / 'gamedata.json') == record['gamedata']
        for path, h in record['files'].items(): assert sha(source / path) == h, path
        before = inventory(source)
        dest = target / name
        absent(dest); dest.mkdir(); copy_tree(source, dest)
        assert inventory(dest) == before
        freeze(dest)
        expected = [dict(r, mode=r['mode'] & ~0o222) if r['kind'] != 'symlink' else r for r in before]
        assert inventory(dest) == expected
        assert inventory(source) == before
        result['roots'][name] = dict(dev_root=str(source), dev_inventory_sha256=digest(before),
            content_manifest_sha256=digest(expected), native_sha256=NATIVE, gamedata_sha256=record['gamedata'],
            overlay_files=record['files'], assembler_receipts=record['receipts'])
    write_new(target / 'SOURCE.json', result)
    print('PREPARED', sha(target / 'SOURCE.json'), flush=True)


def run(job, name, mode, source_sha):
    source = job / 'publish-inputs' / name
    manifest_path = job / 'publish-inputs/SOURCE.json'
    assert sha(manifest_path) == source_sha, 'source snapshot manifest pin'
    manifest = json.loads(manifest_path.read_text()); expected = manifest['roots'][name]
    target = RUNTIMES / name
    out = job / (name + '-' + mode + '.json')
    absent(out); no_symlink_ancestors(target); no_symlink_ancestors(out)
    baseline = parents()
    if mode == 'create':
        absent(target)
        assert readonly(source)
        assert digest(inventory(source)) == expected['content_manifest_sha256']
        assert sha(source / 'native/clasher_core.abi3.so') == NATIVE
        assert sha(source / 'gamedata.json') == expected['gamedata_sha256']
        staging = Path(tempfile.mkdtemp(prefix=name + '.assembling-', dir=RUNTIMES))
        copy_tree(source, staging)
        assert inventory(staging) == inventory(source)
        staging.chmod(stat.S_IMODE(staging.stat().st_mode) | stat.S_IWUSR)
        receipt = dict(kind='cards3 B1+B2 runtime release', tier='exploration', no_sealing=True,
            host=socket.gethostname(), created_utc=subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip(),
            pins=name, path=str(target), source_commit=ENGINE,
            source_manifest_sha256=sha(manifest_path), source_snapshot=expected,
            overlay_files=expected['overlay_files'], overlay_manifest_sha256=digest(expected['overlay_files']),
            native_sha256=NATIVE, gamedata_sha256=expected['gamedata_sha256'],
            parents_on_host=baseline, copy='ordinary rsync; no hardlinks',
            verifier_runtime_sha256=sha(job / 'release-verifier/bot/players/runtime.py'),
            known_issues=['GoblinGiant public rider-graph reconstruction can reject a board; observed one root error and fast fallback, no crash. Nonblocking per CARD LEAD decision.'],
            content_manifest_sha256=expected['content_manifest_sha256'])
        write_new(staging / 'RECEIPT.json', receipt)
        freeze(staging)
        assert digest(inventory(staging, True)) == expected['content_manifest_sha256']
        assert parents() == baseline
        absent(target); publish(staging, target)
        write_new(out, receipt)
        print('CREATED', name, sha(target / 'RECEIPT.json'), flush=True)
        return
    receipt = json.loads((target / 'RECEIPT.json').read_text())
    assert receipt['pins'] == name and receipt['source_commit'] == ENGINE
    assert receipt['source_manifest_sha256'] == sha(manifest_path)
    assert receipt['parents_on_host'] == baseline
    assert readonly(target)
    assert digest(inventory(target, True)) == receipt['content_manifest_sha256'] == expected['content_manifest_sha256']
    for path, h in expected['overlay_files'].items(): assert sha(target / path) == h, path
    for path, h in expected['assembler_receipts'].items(): assert sha(target / path) == h, path
    sys.path.insert(0, str(job / 'release-verifier'))
    for key in ('CLASHER_ROOT', 'CLASHER_EVAL_RUNTIME_ROOT', 'CLASHER_DELAY_NATIVE_DIR'): os.environ.pop(key, None)
    os.environ.update(CLASHER_BOT_RUNTIME=str(target), CLASHER_BOT_RUNTIME_PINS=name)
    from bot.players.runtime import Runtime
    start = time.monotonic(); rt = Runtime(verify=True)
    assert rt.pins['card_scope'] == 'full' and rt.pins['fc_side_cut'] is True
    if name == 'live16402c': assert rt.pins['tournament_crown_from_gamedata'] == ('Fireball', 'Poison')
    assert digest(inventory(target, True)) == expected['content_manifest_sha256'] and readonly(target)
    assert parents() == baseline
    result = dict(host=socket.gethostname(), root=str(target), result='PASS', verify=True, read_only=True,
        verified_utc=subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip(),
        parents_unchanged=True, native_sha256=sha(target / 'native/clasher_core.abi3.so'),
        gamedata_sha256=sha(target / 'gamedata.json'), receipt_sha256=sha(target / 'RECEIPT.json'),
        content_manifest_sha256=expected['content_manifest_sha256'], overlay_files_verified=len(expected['overlay_files']),
        metadata_cards=len(rt.R.meta['cards']), config_cards=len(rt.R.config['cards']), templates=len(rt.R.templates),
        runtime_seconds=round(time.monotonic() - start, 3))
    write_new(out, result); print(json.dumps(result), flush=True)


def main():
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=('prepare', 'create', 'verify'))
    p.add_argument('--job', type=Path, required=True); p.add_argument('--name', choices=NAMES); p.add_argument('--source-sha')
    if not __debug__: raise RuntimeError('assertions must remain enabled')
    a = p.parse_args()
    if a.mode == 'prepare': prepare(a.job)
    else:
        assert a.name and a.source_sha; run(a.job, a.name, a.mode, a.source_sha)


if __name__ == '__main__': main()
