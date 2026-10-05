"""One canonical pilot, with at most two owned heavy jobs across all stages."""
import json
import os
import hashlib
from pathlib import Path
from run import HERE, ROOT, note, launch, finish


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    marker = HERE.parent/'GAMEDATA_CANONICAL_READY'
    if not marker.is_file():
        raise RuntimeError('wait for GAMEDATA_CANONICAL_READY')
    if (HERE/'preflight.json').exists():
        raise RuntimeError('pilot already initialized; inspect owned jobs before resuming')
    admitted = HERE.parent/'m0/runtime-snapshots/pilot-runtime-v5/gamedata.json'
    data = ROOT/'gamedata.json'
    ready = json.loads(marker.read_text())
    assert digest(data) == ready['gamedata_sha256']
    assert digest(admitted) == ready['admitted_gamedata_sha256']
    assert digest(ROOT/'engine-rs/clasher_core.abi3.so') == ready['rust_binary_sha256']
    assert digest(ROOT/ready['report']) == ready['report_sha256']
    current, reference = json.loads(data.read_text()), json.loads(admitted.read_text())
    assert {k:v for k,v in current.items() if k != 'meta'} == {k:v for k,v in reference.items() if k != 'meta'}
    cards = {c['name']: c for c in current['items']['spells']}
    assert cards['IceSpirits']['summonCharacterData']['hitpoints'] == 84
    assert cards['Goblins']['summonCharacterData']['damage'] == 49
    proof_dir = HERE.parent/'engine-speed/canonical'
    proofs = {}
    for name, count in (('stage3_planner.json', 50), ('stage3_games.json', 8)):
        path = proof_dir/name
        receipt = json.loads(path.read_text())
        assert len(receipt['results']) == count, name
        for source, expected in receipt['fingerprint'].items():
            assert digest(ROOT/source) == expected, source
        proofs[str(path.relative_to(ROOT))] = digest(path)
    # Stage 2 also binds the Python native adapters, which Stage 3's map omits.
    paths = [*(ROOT/'src/clasher').rglob('*.py'), *(ROOT/'engine-rs/src').glob('*.rs'),
             *(ROOT/'engine-rs').glob('*.py'), ROOT/'engine-rs/clasher_core.abi3.so']
    fingerprint = hashlib.sha256(data.read_bytes() + b''.join(
        str(p.relative_to(ROOT)).encode()+p.read_bytes() for p in sorted(paths))).hexdigest()
    stage2 = json.loads((proof_dir/'stage2_games.json').read_text())
    assert stage2['fingerprint'] == fingerprint and len(stage2['results']) == 64
    proofs[str((proof_dir/'stage2_games.json').relative_to(ROOT))] = digest(proof_dir/'stage2_games.json')
    native_paths = [*(ROOT/'engine-rs/src').glob('*.rs'), ROOT/'engine-rs/clasher_core.abi3.so',
        ROOT/'engine-rs/differential.py', ROOT/'engine-rs/live_snapshot.py',
        ROOT/'src/clasher/rl/script_rollout_planner.py', HERE.parent/'engine-speed/es_common.py']
    runtime = dict(verified_hashes={str(p.relative_to(ROOT)): digest(p) for p in native_paths},
        canonical_proofs=proofs, stage2_fingerprint=fingerprint, marker_sha256=digest(marker))
    canonical = dict(gamedata_sha256=digest(data), admitted_sha256=digest(admitted),
        admitted_path=str(admitted), non_meta_equal=True, ice_spirit_hp=84, goblin_damage=49,
        marker_sha256=digest(marker))
    for name, value in (('native-runtime.json', runtime), ('canonical-data.json', canonical)):
        (HERE/name).write_text(json.dumps(value, indent=2)+'\n')
    teacher = json.loads((HERE/'archive/noncanonical-3d99987c/teacher.json').read_text())
    teacher.pop('pilot_backend_history', None)
    teacher.update(backend='native', gamedata_sha256=digest(data),
        native_runtime_sha256=digest(HERE/'native-runtime.json'))
    (HERE/'teacher.json').write_text(json.dumps(teacher, indent=2)+'\n')
    note(f'Canonical data matches admitted non-meta data; digest {digest(data)}. '
         'Post-fix native binary and source fingerprints match canonical Stage 2/3 receipts; no rebuild needed.')
    finish('preflight', launch('preflight', [HERE/'kit.py', 'preflight']))


def main():
    prepare()
    note(f'Canonical coordinator PID {os.getpid()}. Start fresh baseline (one worker) '
         'alongside parity, then native collection and the sole canonical fit.')
    initial = launch('eval-initial', [HERE/'evaluate.py', '--checkpoint',
        HERE.parent/'pilot/v7r4h-launch/runs/s2902/seed-2902/scripted/policy_decisions_001000000.pt',
        '--name', 'srp-dagger-initial-s2902', '--parallel', '1', '--trace-games', '0'])
    finish('native-parity', launch('native-parity', [HERE/'native_parity.py']))
    finish('collect-canonical', launch('collect-canonical', [HERE/'kit.py', 'collect', '--start', '0', '--stop', '40']))
    finish('verify-all', launch('verify-all', [HERE/'verify.py']))
    finish('fit', launch('fit', [HERE/'fit.py']))
    finish('eval-initial', initial)
    finish('eval-final', launch('eval-final', [HERE/'evaluate.py', '--checkpoint', HERE/'student.pt',
        '--name', 'srp-dagger-it1-s2902', '--parallel', '2', '--trace-games', '0']))
    finish('report', launch('report', [HERE/'report.py']))
    note('Done: canonical parity, 40 native games, one canonical fit, two fresh 192-game '
         'evaluations and paired report. No owned heavy jobs remain.')
    (HERE/'completion.json').write_text(json.dumps({'complete': True, 'canonical': True, 'pid': os.getpid()})+'\n')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        note(f'FAILED canonical pilot: {exc!r}. Inspect owned child state before resuming.')
        raise
