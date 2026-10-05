"""Admitted-runtime identity for recorded OQ games and public-mask placements."""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import random
import sys

import numpy as np
from clasher.paths import gamedata_path
import clasher.battle

ES = Path(__file__).resolve().parent
ROOT = ES.parents[2]
OQ = ES.parent / 'oracle-qualification'
spec = importlib.util.spec_from_file_location('p16_identity', ES.parent / 'c56/engine/tools/p16_identity.py')
p16 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p16)
FIELDS = ('outcome', 'candidate_crowns', 'opponent_crowns', 'ticks', 'planner_calls')


def provenance():
    data = json.loads(gamedata_path().read_text())
    data.pop('meta', None)
    source = Path(clasher.battle.__file__).resolve().parent
    return dict(driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                gamedata=str(gamedata_path()), gamedata_sha256=hashlib.sha256(gamedata_path().read_bytes()).hexdigest(),
                data_sha256=hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                source=str(source), source_sha256=hashlib.sha256(b''.join(str(p.relative_to(source)).encode()+p.read_bytes() for p in sorted(source.rglob('*.py')))).hexdigest())


def recorded_specs(count):
    cells = {}
    for path in sorted((OQ / 'games/srp_xm_c256').glob('*.json')):
        rec = json.loads(path.read_text())
        s = rec['spec']
        if s['role'] == 'holdout':
            cells.setdefault((s['opponent'], s['game'] % 2), []).append(path)
    selected = []
    for i in range(count):
        key = sorted(cells)[i % len(cells)]
        selected.append(cells[key][i // len(cells)])
    return selected


def random_episode(index):
    res = p16.resources()
    loader, builder, masks, space = res
    ep = p16.episodes()[index % 12].copy()
    ep['seed'] += 100000 + index
    battle = p16.new_battle(ep, loader)
    # Deterministic pocket fixture: both left Princess towers die through normal cleanup.
    pocket = index >= 12
    if pocket:
        for entity in list(battle.entities.values()):
            if getattr(entity, '_crown_tower_slot', None) == 'left':
                entity.take_damage(entity.hitpoints)
        battle.step()
    rng = random.Random(20261004 + index)
    trace = []
    pocket_counts = [0, 0]
    card_counts = {}
    while battle.tick < 90:
        battle.step()
    while battle.tick < 1800 and not battle.game_over:
        views = [p16.reference_public_observation(builder.build_actor(battle, seat)) for seat in (0, 1)]
        actions = []
        for seat, view in enumerate(views):
            mask = masks.build(p16.PublicActionMaskInput.from_confidence_observation(view))
            legal = list(map(int, np.flatnonzero(mask)))
            pocket_actions = []
            for action in legal:
                choice = space.decode_action(action, seat)
                if choice.is_no_op:
                    continue
                name = builder.card_name_for_token_id(int(view.observation.hand_ids[choice.slot]))
                if name not in ('Zap', 'Fireball', 'Log') and ((seat == 0 and choice.position.y >= 15) or (seat == 1 and choice.position.y < 17)):
                    pocket_actions.append(action)
            action = rng.choice(pocket_actions if pocket and pocket_actions else legal)
            if action in pocket_actions:
                pocket_counts[seat] += 1
            actions.append(action)
        trace.append([battle.tick, actions, [p16.packet_sha(v) for v in views], p16.state_digest(battle)])
        for seat, action in enumerate(actions):
            choice = space.decode_action(action, seat)
            if not choice.is_no_op:
                name = builder.card_name_for_token_id(int(views[seat].observation.hand_ids[choice.slot]))
                assert battle.deploy_card(seat, name, choice.position), (index, battle.tick, seat, action)
                card_counts[name] = card_counts.get(name, 0) + 1
        for _ in range(5):
            if not battle.game_over:
                battle.step()
    trace.append([battle.tick, None, None, p16.state_digest(battle)])
    if pocket:
        assert all(pocket_counts), (index, pocket_counts)
    return dict(episode=ep, pocket_fixture=pocket, pocket_placements=pocket_counts, cards=card_counts,
                boundaries=len(trace), trace_sha256=hashlib.sha256(json.dumps(trace, separators=(',', ':')).encode()).hexdigest(),
                final_tick=battle.tick, winner=battle.winner)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('suite', choices=('recorded', 'random'))
    ap.add_argument('mode', choices=('record', 'check'))
    ap.add_argument('baseline', type=Path)
    ap.add_argument('--count', type=int)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    # Serialize resumptions of one receipt; a waiting process does no replay work.
    lock = args.output.with_suffix(args.output.suffix + '.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX)
    count = args.count or (8 if args.suite == 'recorded' else 24)
    prov = provenance()
    baseline = json.loads(args.baseline.read_text()) if args.mode == 'check' else None
    if baseline:
        assert baseline['provenance']['data_sha256'] == prov['data_sha256'], 'non-meta gamedata differs from admitted baseline'
        assert baseline['count'] == count and baseline['suite'] == args.suite
    out = dict(suite=args.suite, count=count, provenance=prov, results={}, mismatches=[])
    if args.output.exists():
        old = json.loads(args.output.read_text())
        if all(old[k] == out[k] for k in ('suite', 'count', 'provenance')):
            out = old
    if args.suite == 'recorded':
        sys.path.insert(0, str(OQ))
        import oq_lib
        ctx = oq_lib.Context()
        paths = recorded_specs(count) if not baseline else [ROOT / row['recording'] for row in baseline['results'].values()]
    for index in range(count):
        key = str(index)
        if key in out['results'] and key not in out['mismatches']:
            if baseline:
                assert out['results'][key] == baseline['results'][key], (key, 'cached result differs from baseline')
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            if args.suite == 'recorded':
                path = paths[index]
                rec = json.loads(path.read_text())
                result = oq_lib.play_game(ctx, rec['spec'])
                expected = {k: rec[k] for k in FIELDS}
                actual = {k: result[k] for k in FIELDS}
                row = dict(recording=str(path.relative_to(ROOT)), recording_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), spec=rec['spec'], expected=expected, actual=actual)
                ok = actual == expected
            else:
                row = random_episode(index)
                ok = True
        if baseline:
            ok = ok and row == baseline['results'][key]
        out['results'][key] = row
        if not ok and key not in out['mismatches']:
            out['mismatches'].append(key)
        args.output.write_text(json.dumps(out, indent=2)+'\n')
        print(json.dumps(dict(suite=args.suite, episode=index, ok=ok, detail=row if args.suite == 'recorded' else {k:v for k,v in row.items() if k != 'episode'})), flush=True)
        if not ok:
            raise SystemExit(1)
    assert len(out['results']) == count and not out['mismatches']
    if args.mode == 'record':
        assert not args.baseline.exists(), 'refusing to overwrite baseline'
        args.baseline.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps(dict(suite=args.suite, checked=count, mismatches=[])), flush=True)


if __name__ == '__main__':
    main()
