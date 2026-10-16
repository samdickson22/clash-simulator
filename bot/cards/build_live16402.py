"""Assemble a live16402 runtime root: an assembled r1-cards1 root (bot/cards/build_runtime.py) + the balance overlay.

    python3 -I bot/cards/build_live16402.py --base <r1-cards1 root> --target DIR \
        --rs16 cards-160402017-20261006.json --rs15 cards-15.535.json --calibration <main root gamedata.json>

1. Copies BASE (must hold build_runtime's CARDS-RUNTIME-RECEIPT.json) to a unique TARGET.assembling-* sibling
   with rsync (BASE is only read; --link hardlinks unchanged files, safe because the one changed file is written as a new inode).
2. Writes TARGET/gamedata.json = balance_overlay(BASE/gamedata.json, RoyaleSim 16.402 / 15.535, calibration).
   The overlay detail (per-slot values) goes to TARGET/LIVE16402-OVERLAY-DETAIL.json: it stays in the runtime dir.
3. Writes TARGET/LIVE16402-RECEIPT.json: the overlay receipt (sha256 of the RoyaleSim file, input and output
   gamedata, counts, names) + the native sha256 + the base root and its receipt sha256. Then renames into place
   and removes write permission (the runtime root is read-only by contract; not with --link).
Select it with CLASHER_BOT_RUNTIME=TARGET CLASHER_BOT_RUNTIME_PINS=live16402 (native in TARGET/native).
TARGET must not exist, or must hold a previous LIVE16402-RECEIPT.json (then it moves to TARGET.old). A target under
clasher-bot-runtime/ (the real live16402) needs --release.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bot.cards import balance_overlay as bo  # noqa: E402
from bot.cards.build_runtime import base_inputs, staging_dir, validate_paths, write_text  # noqa: E402

RUNTIMES = Path('/mpac/sdicks02/repos/clasher-bot-runtime')
RECEIPT = 'LIVE16402-RECEIPT.json'
DETAIL = 'LIVE16402-OVERLAY-DETAIL.json'
BASE_RECEIPT = 'CARDS-RUNTIME-RECEIPT.json'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True, help='an assembled r1-cards1 root')
    ap.add_argument('--target', required=True)
    ap.add_argument('--rs16', required=True)
    ap.add_argument('--rs15', required=True)
    ap.add_argument('--calibration', required=True)
    ap.add_argument('--link', action='store_true')
    ap.add_argument('--release', action='store_true', help='allow a target under clasher-bot-runtime/')
    a = ap.parse_args()
    base, target = Path(a.base).resolve(), Path(a.target).resolve()
    old = target.with_name(target.name + '.old')
    inputs = base_inputs(base)
    inputs.update(base_receipt=base / BASE_RECEIPT,
                  rs16=Path(a.rs16), rs15=Path(a.rs15), calibration=Path(a.calibration))
    outputs = dict(target=target, backup=old)
    validate_paths(inputs, outputs)
    if RUNTIMES in target.parents and not a.release:
        sys.exit(f'{target} is a live runtime path: pass --release')
    if not (base / BASE_RECEIPT).exists():
        sys.exit(f'{base} holds no {BASE_RECEIPT}: not an assembled card-scope root')
    if target.exists() and any(target.iterdir()):
        if not (target / RECEIPT).exists():
            sys.exit(f'{target} exists and holds no {RECEIPT}: refusing to replace it')
        if old.exists():
            subprocess.run(['chmod', '-R', 'u+w', str(old)], check=True)
            shutil.rmtree(old)
        subprocess.run(['chmod', 'u+w', str(target)], check=True)
        target.rename(old)
    tmp = staging_dir(target, inputs, outputs)
    cmd = ['rsync', '-a', f'{base}/', f'{tmp}/']
    if a.link:
        cmd[2:2] = [f'--link-dest={base}']
    subprocess.run(cmd, check=True)

    gd = tmp / 'gamedata.json'
    fd, name = tempfile.mkstemp(prefix='gamedata.json.live16402-', dir=tmp)
    os.close(fd)
    out = Path(name)
    receipt, detail = bo.run(base / 'gamedata.json', a.rs16, a.rs15, a.calibration, out, c56=bo.c56_names())
    out.replace(gd)                       # new inode: never writes through a hardlink into BASE
    receipt['output']['path'] = str(target / 'gamedata.json')
    assert bo.sha256(gd) == receipt['output']['sha256']
    native = tmp / 'native/clasher_core.abi3.so'
    receipt.update(
        pins='live16402', created=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        host=socket.gethostname(), base=str(base), base_receipt_sha256=bo.sha256(base / BASE_RECEIPT),
        base_gamedata_sha256=bo.sha256(base / 'gamedata.json'), copy='hardlink' if a.link else 'copy',
        native=dict(path=str(target / 'native/clasher_core.abi3.so'), sha256=bo.sha256(native)))
    write_text(tmp / RECEIPT, json.dumps(receipt, indent=1, sort_keys=True, default=list) + '\n')
    write_text(tmp / DETAIL, json.dumps(detail, indent=1, sort_keys=True) + '\n')
    tmp.rename(target)
    if not a.link:                        # chmod on hardlinked files would change BASE's modes too
        subprocess.run(['chmod', '-R', 'a-w', str(target)], check=True)
    print(json.dumps({k: receipt[k] for k in ('inputs', 'output', 'native', 'actions', 'applied_slots',
                                               'comparer_check')}, indent=1))


if __name__ == '__main__':
    main()
