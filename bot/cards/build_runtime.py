"""Assemble a card-scope runtime root (r1-cards1): a copy of r1 plus the engine-cards overlays, with a receipt.

    # on the git host (05): export a commit's engine-cards (git archive: uncommitted edits never ship)
    python bot/cards/build_runtime.py --rev HEAD --export-only /mpac/sdicks02/jobs/clasher/cards/runtime/src-<sha>
    # on the runtime host, with that tree copied over:
    python bot/cards/build_runtime.py --tree SRC --target DIR --native SO        # prebuilt native, or
    python bot/cards/build_runtime.py --tree SRC --target DIR --build-dir OUT    # cargo-build SRC/engine-cards first
    (--rev REV instead of --tree does both on a host with the git worktree.)

1. Copies BASE (default clasher-bot-runtime/r1) to TARGET with rsync; BASE is only read. --link hardlinks unchanged
   files instead (rsync --link-dest): overlays are written as new files, so linked BASE inodes are never touched,
   but anything that later writes into TARGET in place would write into BASE too, so a copy is the default.
2. Overlays, from the exported tree (the commit's tracked files only):
   engine-cards/py/src/clasher/**   -> TARGET/src/clasher/**   (base-only files are kept and listed)
   engine-cards/py/gamedata.json    -> TARGET/gamedata.json
   engine-cards/*.py (glue)         -> TARGET/engine-rs/*.py
   native .so                       -> TARGET/native/clasher_core.abi3.so (BASE's native build-tiers.* dropped)
3. Writes TARGET/CARDS-RUNTIME-RECEIPT.json: source commit (+ the worktree's uncommitted engine-cards paths, which
   are NOT included), native sha256 and origin, sha256 of every overlay file and of the manifest, which overlays
   changed a base file, base path and base native sha256.
Select it with CLASHER_BOT_RUNTIME=TARGET CLASHER_BOT_RUNTIME_PINS=r1-cards1 (no CLASHER_DELAY_NATIVE_DIR).
TARGET must not exist, or must hold a previous receipt (then it moves to TARGET.old). Staging uses a unique
TARGET.assembling-* sibling. A target under clasher-bot-runtime/ (the real r1-cards1) needs --release.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[2]
RUNTIMES = Path('/mpac/sdicks02/repos/clasher-bot-runtime')
RECEIPT = 'CARDS-RUNTIME-RECEIPT.json'
CARGO = dict(CARGO_HOME='/mpac/sdicks02/tools/cargo', RUSTUP_HOME='/mpac/sdicks02/tools/rustup')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def git(*args):
    return subprocess.run(['git', '-C', str(SOURCE), *args], check=True, capture_output=True, text=True).stdout


def export(rev, out):
    """git archive REV engine-cards -> OUT/engine-cards (committed files only: uncommitted edits never ship), plus
    OUT/SOURCE-GIT.json {commit, tracked, dirty_at_export}."""
    validate_paths({'engine source': SOURCE / 'engine-cards', 'git metadata': SOURCE / '.git'},
                   {'source export': out})
    commit = git('rev-parse', rev).strip()
    if out.exists() and any(out.iterdir()):
        if not (out / 'SOURCE-GIT.json').exists():
            sys.exit(f'{out} exists and is not an export: refusing to replace it')
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(['git', '-C', str(SOURCE), 'archive', '--format=tar', commit, 'engine-cards'],
                             check=True, capture_output=True).stdout
    subprocess.run(['tar', '-x', '-C', str(out)], input=archive, check=True)
    tracked = [x for x in git('ls-tree', '-r', '-z', '--name-only', commit, 'engine-cards').split('\0') if x]
    dirty = [line[3:] for line in git('status', '--porcelain', '--', 'engine-cards').splitlines()]
    (out / 'SOURCE-GIT.json').write_text(json.dumps(dict(commit=commit, tracked=tracked, dirty_at_export=dirty,
                                                         worktree=str(SOURCE))) + '\n')
    return out


def source_info(tree):
    info = json.loads((tree / 'SOURCE-GIT.json').read_text())
    for rel in info['tracked']:
        assert (tree / rel).is_file(), rel
    return info


def build_native(tree, out):
    """TREE/engine-cards -> OUT/clasher_core.abi3.so, the recipe that reproduces 681b5f2c (jobs/clasher/cards/build.sh)."""
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, **CARGO, PATH=f"{CARGO['CARGO_HOME']}/bin:{os.environ['PATH']}",
               CARGO_TARGET_DIR=str(out / 'target'), CARGO_INCREMENTAL='0',
               PYO3_PYTHON=os.environ.get('PYO3_PYTHON', '/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'))
    subprocess.run(['nice', '-n', '15', 'cargo', '+1.97.1', 'build', '--offline', '--manifest-path',
                    str(tree / 'engine-cards/Cargo.toml'), '--release', '--features', 'extension-module,gil-release',
                    '-j', '16'], check=True, env=env)
    so = out / 'clasher_core.abi3.so'
    shutil.copyfile(out / 'target/release/libclasher_core.so', str(so) + '.tmp')
    os.replace(str(so) + '.tmp', so)
    return so


def overlays(tracked):
    """[(source path, target-relative path)] from the git-tracked engine-cards files."""
    out = []
    for rel in tracked:
        if rel == 'engine-cards/py/gamedata.json':
            out.append((rel, 'gamedata.json'))
        elif rel.startswith('engine-cards/py/src/clasher/'):
            out.append((rel, 'src/' + rel[len('engine-cards/py/src/'):]))
        elif rel.endswith('.py') and '/' not in rel[len('engine-cards/'):]:
            out.append((rel, 'engine-rs/' + rel[len('engine-cards/'):]))
    return out


def base_inputs(base):
    """Include aliases copied by rsync so cleanup cannot remove their referents."""
    inputs = dict(base=base, base_gamedata=base / 'gamedata.json',
                  base_native=base / 'native/clasher_core.abi3.so')
    for path in base.rglob('*'):
        if path.is_symlink():
            inputs[f'base symlink {path.relative_to(base)}'] = path
    return inputs


def validate_paths(inputs, outputs):
    """Reject every output/input or output/output overlap before changing any path."""
    for name, path in outputs.items():
        if Path(path).is_symlink():
            sys.exit(f'symlinked output path: {name}: {path}')
    inputs = {k: Path(v).resolve() for k, v in inputs.items()}
    outputs = {k: Path(v).resolve() for k, v in outputs.items()}
    def overlap(a, b):
        return a == b or a in b.parents or b in a.parents
    for name, path in outputs.items():
        for other, source in inputs.items():
            if overlap(path, source):
                sys.exit(f'{name} overlaps {other}: {path} / {source}')
    pairs = list(outputs.items())
    for i, (name, path) in enumerate(pairs):
        for other, dest in pairs[i + 1:]:
            if overlap(path, dest):
                sys.exit(f'{name} overlaps {other}: {path} / {dest}')


def staging_dir(target, inputs, outputs):
    """A new sibling cannot alias an existing input or an abandoned staging tree."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=target.name + '.assembling-', dir=target.parent))
    validate_paths(inputs, dict(outputs, staging=tmp))
    return tmp


def reject_symlink_ancestors(root, destinations):
    """Check all destination parents before installing any overlay into a copied base."""
    for destination in destinations:
        parent = root
        for part in destination.relative_to(root).parts[:-1]:
            parent = parent / part
            if parent.is_symlink():
                sys.exit(f'symlinked destination ancestor: {parent}')


def install(src, dst):
    """New inode (unique temp + rename): never writes through a BASE hardlink or temp symlink."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=dst.name + '.cards-', dir=dst.parent)
    os.close(fd)
    tmp = Path(name)
    try:
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)


def write_text(dst, text):
    """Write metadata as a new inode, including when BASE contains a symlink at dst."""
    fd, name = tempfile.mkstemp(prefix=dst.name + '.cards-', dir=dst.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
        os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target')
    ap.add_argument('--base', default=str(RUNTIMES / 'r1'))
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--rev', help='git revision of this worktree to overlay (exported with git archive)')
    src.add_argument('--tree', help='an exported tree (--export-only on the git host, then copied here)')
    ap.add_argument('--export-only', help='with --rev: export to this dir and stop')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--native', help='prebuilt clasher_core.abi3.so built from engine-cards/')
    g.add_argument('--build-dir', help='cargo-build engine-cards/ here first')
    ap.add_argument('--link', action='store_true', help='hardlink unchanged files (rsync --link-dest) instead of copying')
    ap.add_argument('--release', action='store_true', help='allow a target under clasher-bot-runtime/')
    a = ap.parse_args()
    if a.export_only:
        if not a.rev:
            sys.exit('--export-only needs --rev')
        print(export(a.rev, Path(a.export_only).resolve()))
        return
    if not a.target or not (a.native or a.build_dir):
        sys.exit('need --target and one of --native / --build-dir')
    base, target = Path(a.base).resolve(), Path(a.target).resolve()
    old = target.with_name(target.name + '.old')
    tree = target.with_name(target.name + '.source') if a.rev else Path(a.tree).resolve()
    inputs = base_inputs(base)
    outputs = dict(target=target, backup=old)
    if a.rev:
        inputs['engine source'] = SOURCE / 'engine-cards'
        outputs['source export'] = tree
    else:
        inputs['overlay tree'] = tree
    if a.native:
        inputs['native'] = Path(a.native).resolve()
    if a.build_dir:
        outputs['native build'] = Path(a.build_dir).resolve()
    validate_paths(inputs, outputs)
    if RUNTIMES in target.parents and not a.release:
        sys.exit(f'{target} is a live runtime path: pass --release')
    replacing = target.exists() and any(target.iterdir())
    if replacing and not (target / RECEIPT).exists():
        sys.exit(f'{target} exists and holds no {RECEIPT}: refusing to replace it')
    if a.rev:
        tree = export(a.rev, target.with_name(target.name + '.source'))
    else:
        tree = Path(a.tree).resolve()
    info = source_info(tree)
    inputs.update({f'overlay {rel}': tree / rel for rel in info['tracked']})
    validate_paths(inputs, {k: v for k, v in outputs.items() if k != 'source export'})
    if replacing:
        if old.exists():
            subprocess.run(['chmod', '-R', 'u+w', str(old)], check=True)
            shutil.rmtree(old)
        target.rename(old)
    native = build_native(tree, Path(a.build_dir).resolve()) if a.build_dir else Path(a.native).resolve()
    native_sha = sha256(native)

    inputs['overlay tree'] = tree
    tmp = staging_dir(target, inputs, {k: v for k, v in outputs.items() if k != 'source export'})
    cmd = ['rsync', '-a', f'{base}/', f'{tmp}/']
    if a.link:
        cmd[2:2] = [f'--link-dest={base}']
    subprocess.run(cmd, check=True)

    destinations = [tmp / dst for _, dst in overlays(info['tracked'])]
    reject_symlink_ancestors(tmp, destinations + [tmp / 'native/clasher_core.abi3.so'])
    files = []
    for rel, dst in overlays(info['tracked']):
        src = tree / rel
        d = tmp / dst
        before = sha256(d) if d.exists() else None
        install(src, d)
        files.append(dict(path=dst, source=rel, sha256=sha256(d), changed=before != sha256(d)))
    overlaid = {f['path'] for f in files}
    base_only = sorted(str(p.relative_to(tmp)) for p in (tmp / 'src/clasher').rglob('*')
                       if p.is_file() and str(p.relative_to(tmp)) not in overlaid and '__pycache__' not in p.parts)
    for stale in ('build-tiers.json', 'build-tiers.sha256'):
        if (tmp / 'native' / stale).exists():
            (tmp / 'native' / stale).unlink()
    install(native, tmp / 'native/clasher_core.abi3.so')
    assert sha256(tmp / 'native/clasher_core.abi3.so') == native_sha
    manifest = json.dumps(sorted((f['path'], f['sha256']) for f in files))
    receipt = dict(
        kind='clasher card-scope runtime root', pins='r1-cards1', created=datetime.datetime.now(
            datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), host=socket.gethostname(),
        base=str(base), base_native_sha256=sha256(base / 'native/clasher_core.abi3.so'), copy='hardlink' if a.link else 'copy',
        source=info.get('worktree'), source_tree=str(tree), source_commit=info['commit'],
        source_dirty_at_export_not_included=info.get('dirty_at_export'),
        native=dict(sha256=native_sha, origin=str(native), built_here=bool(a.build_dir)),
        overlay_manifest_sha256=hashlib.sha256(manifest.encode()).hexdigest(),
        overlay_files=len(files), overlay_changed=[f['path'] for f in files if f['changed']],
        src_base_only=base_only, files=files)
    write_text(tmp / RECEIPT, json.dumps(receipt, indent=1) + '\n')
    tmp.rename(target)
    print(json.dumps({k: receipt[k] for k in ('source_commit', 'source_dirty_at_export_not_included', 'native', 'overlay_files',
                                               'overlay_changed', 'overlay_manifest_sha256')}, indent=1))
    print(f'base-only src files kept: {len(base_only)}')


if __name__ == '__main__':
    main()
