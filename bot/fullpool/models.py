"""Use extended (full-pool) v1 / R3a checkpoints as the runtime's rt.POLICY / rt.STUDENT (exploration).

    BOT_FULLPOOL_POLICIES='v1=/path/main02-fp.pt,R3a=/path/R3a-fp.pt' python -m bot.eval.headline ...

The runtime pins main02.pt and R3a.pt by sha256 (bot/players/runtime.py), so an extended file cannot replace them
in the root. install() accepts an extended file only if its bot/fullpool/extend.py receipt says it was made from the
pinned checkpoint (source_sha256 == the pin) and the file is the receipt's output (sha256 checked), then swaps it in
for every player that reads rt.POLICY (v1, K4) or rt.STUDENT (R3a, K4S/K4C proposer and S-default). On C56 inputs the
extended model is bit-identical (parity.py), so C56 HEADLINE command hashes do not change.
Students given as 'student:<path>' need nothing: point the spec at the extended file.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from bot.fullpool.extend import sha256

PIN_KEYS = {'v1': 'v1_sha256', 'R3a': 'r3a_sha256'}


def verified(path, pin):
    path = Path(path)
    receipt = json.loads(Path(str(path) + '.fullpool.json').read_text())
    if receipt.get('source_sha256') != pin:
        raise ValueError(f'{path}: made from {receipt.get("source_sha256")}, not the pinned {pin}')
    got = sha256(path)
    if got != receipt.get('output_sha256'):
        raise ValueError(f'{path}: sha256 {got} != receipt output {receipt.get("output_sha256")}')
    return receipt


def install(rt, spec):
    """spec 'v1=PATH,R3a=PATH' (either part optional)."""
    done = {}
    for part in filter(None, spec.split(',')):
        who, _, path = part.partition('=')
        if who not in PIN_KEYS:
            raise ValueError(f'BOT_FULLPOOL_POLICIES: unknown model {who!r} (v1, R3a)')
        verified(path, rt.pins[PIN_KEYS[who]])
        if who == 'v1':
            from imitation.model import load_policy
            rt.POLICY = load_policy(path)
            assert rt.POLICY.model.temperatures.tolist() == [1., 1., 1.]
            rt.v1_path = Path(path)
        else:
            from proposals import load_student
            rt._student = load_student(path, rt.pins['r3a_threshold'])
            rt.student_path = Path(path)
        done[who] = str(path)
    rt.fullpool_policies = done
    return done


def install_from_env(rt):
    spec = os.environ.get('BOT_FULLPOOL_POLICIES')
    return install(rt, spec) if spec else {}
