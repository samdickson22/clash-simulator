"""ExIt pipeline self-test (one process, ~3-4 min CPU):

    CLASHER_BOT_RUNTIME=... python -m bot.exit.test_exit --assets ASSETS.npz --tmp DIR

1. 'student:R3a.pt@thr' reproduces PolicyPlayer('R3a') vs v1 (identical command hash).
2. Labelling does not perturb play: LabelingPlayer(R3a, K4S-b64) vs v1 has the same command hash.
3. Sealed shards pack (exit_r1.pack) and load with exit_r3 RootTeacherStore; every root row is
   trainable; the trainer's features equal the serving features (single_features) bit for bit;
   the label of every uncut row is the first argmax of its complete scores.
4. The first label equals the K4S-b64 player's own first decision on the same seed (same state).
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import torch

TICKS = 1200
INDEX = 3
BASE = 4096   # throwaway smoke bank (not HEADLINE, not training)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--assets', required=True)
    ap.add_argument('--tmp', required=True, type=Path)
    ap.add_argument('--ticks', type=int, default=TICKS)
    a = ap.parse_args()
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime, PINS
    from bot.players.ours import play_match, x4s_setup
    from bot.players.policy import PolicyPlayer
    from bot.players.search import SearchPlayer
    from bot.exit.student import StudentPlayer
    from bot.exit.label import LabelingPlayer, seal_rows
    rt = Runtime()
    case = x4s_setup(rt, INDEX, BASE)
    seat = case['seat']
    out = {}

    def run(p, ticks=a.ticks):
        players = {seat: p, 1 - seat: PolicyPlayer(rt, 'v1')}
        return play_match(rt, players, seed=case['seed'], decks=case['decks'], max_ticks=ticks)

    ref = run(PolicyPlayer(rt, 'R3a'))
    spec = f'student:{rt.student_path}@{PINS["r3a_threshold"]!r}'
    stu = run(StudentPlayer.from_spec(rt, spec))
    assert stu['command_sha256'] == ref['command_sha256'], 'student spec != R3a'
    out['1_student_spec_equals_R3a'] = ref['command_sha256'][:16]

    lab = LabelingPlayer(rt, PolicyPlayer(rt, 'R3a'), SearchPlayer(rt, mode='budget', budget=64, default='R3a'),
                         keep_features=True)
    res = run(lab)
    assert res['command_sha256'] == ref['command_sha256'], 'labelling perturbed the game'
    assert lab.rows, 'no labels'
    out['2_labelling_unperturbed'] = dict(rows=len(lab.rows), counts=lab.counts)

    if a.tmp.exists():
        shutil.rmtree(a.tmp)
    (a.tmp / 'games').mkdir(parents=True)
    seal_rows(a.tmp / 'games' / 'game-0000003-s1', lab.rows, lab.scores,
              dict(seed=case['seed'], outcome=0.0, rows=len(lab.rows)))
    from imitation.exit_r1.pack import pack
    pack([a.tmp / 'games'], a.tmp / 'packed', memory_guard=lambda: None)
    from exit_r3.student import RootTeacherStore, teacher_targets
    store = RootTeacherStore(a.tmp / 'packed', a.assets)
    assert len(store) == len(lab.rows), (len(store), len(lab.rows))
    mism = 0
    for i in range(len(lab.rows)):
        b, y = store.batch(np.array([i]))
        f = lab.features[i]
        n = int(f['valid'].shape[1])
        for k in ('ids', 'types', 'numeric', 'valid'):
            if not torch.equal(b[k][0, :n], f[k][0]) or b['valid'][0, n:].any():
                mism += 1
                print('feature mismatch', i, k)
                break
        assert torch.equal(b['action_mask'][0], f['action_mask'][0])
        hit = bool(lab.rows[i]['teacher_hit'])
        sc = lab.scores[i]
        if not hit:
            valid = [j for j, v in enumerate(sc['scores']) if v is not None]
            best = max(valid, key=lambda j: (sc['scores'][j], -j))
            first = min(j for j in valid if sc['scores'][j] >= sc['scores'][best] - 1e-9)
            assert sc['candidates'][first] == int(lab.rows[i]['teacher_search_action']), (i, sc)
            q = teacher_targets(y, .003)
            assert int(y['root_actions'][0, int(q[0].argmax())]) == sc['candidates'][first] or \
                sc['candidates'][first] >= 2400
    assert mism == 0, f'{mism} feature mismatches'
    out['3_pack_store_features_labels'] = dict(rows=len(store), hits=int(sum(bool(r['teacher_hit']) for r in lab.rows)))

    k = SearchPlayer(rt, mode='budget', budget=64, default='R3a')
    run(k, ticks=120)
    first = k.decisions[0]
    assert first['action'] == int(lab.rows[0]['teacher_search_action']), (first, lab.rows[0]['teacher_search_action'])
    out['4_first_label_equals_K4S_b64'] = first['action']
    print(json.dumps(dict(passed=True, **out), default=str))


if __name__ == '__main__':
    main()
