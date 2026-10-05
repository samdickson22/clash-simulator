"""Corpus invariants and an asymmetric KL regression for this pilot."""
import json
import numpy as np
import torch
from kit import HERE, INITIAL, TRAINING, DEVICE, ev, load_corpus, sha, write_json, log
from fit import student_kl
from clasher.rl.imitation import _sequence_batch_inputs


def verify_game(path):
    metadata, arrays = load_corpus(path)
    for level, confidence in (('hand_levels','hand_level_confidence'), ('entity_levels','entity_level_confidence')):
        assert np.all(arrays[level][arrays[confidence] > 0] == 11)
    with np.load(path, allow_pickle=False) as data:
        executed = data['submitted_actions']
        labels = arrays['expert_actions'][:-1]
        supervised = arrays['expert_action_supervision_valid'][:-1]
        mixed = data['teacher_executed']
        assert np.array_equal(arrays['previous_actions'][1:], executed)
        assert np.all(arrays['previous_rewards'] == 0)
        assert np.array_equal(executed[mixed], labels[mixed])
        assert np.array_equal(executed[~mixed], data['student_actions'][~mixed])
        assert arrays['terminal_status'][-1] == 1 and not arrays['expert_action_supervision_valid'][-1]
        assert arrays['episode_starts'].sum() == 1 and arrays['episode_starts'][0]
        assert metadata.decisions == len(executed)
        assert arrays['action_masks'][np.arange(len(executed)), executed].all()
        assert arrays['action_masks'][np.arange(len(executed)), data['student_actions']].all()
        ids, values, rows = data['root_candidate_ids'], data['root_candidate_values'], data['root_candidate_rows']
        assert np.array_equal(np.unique(rows), np.flatnonzero(supervised))
        assert np.isfinite(values).all()
        for row in np.flatnonzero(supervised):
            actions, scores = ids[rows == row], values[rows == row]
            assert len(set(actions)) == len(actions)
            assert arrays['action_masks'][row, actions].all()
            best, value = actions[0], -1e9
            for action, score in zip(actions, scores):
                if score > value + 1e-9: best, value = action, score
            assert labels[row] == best
    receipt = json.loads(path.with_suffix('.json').read_text())
    assert receipt['npz_sha256'] == sha(path)
    assert receipt['labels'] == int(supervised.sum())
    return dict(game=receipt['game'], labels=int(supervised.sum()), rows=metadata.samples,
        root_values=len(values), passed=True)


@torch.no_grad()
def replay_actions(loaded, game):
    path = HERE/'games'/f'game-{game:03d}.npz'
    metadata, arrays = load_corpus(path)
    with np.load(path, allow_pickle=False) as payload:
        expected = payload['student_actions'].copy()
    torch.manual_seed(metadata.seed + 271828)
    state = loaded.model.initial_state(1, device=DEVICE)
    for row, expected_action in enumerate(expected):
        inputs = _sequence_batch_inputs(arrays, np.asarray([[row]]), DEVICE,
            trim_entity_padding=False, reset_memory=False)
        action, _, _, state, _ = loaded.model.act(inputs, state, deterministic=False)
        if int(action[0,0]) != int(expected_action):
            raise AssertionError(f'saved actor replay differs: game {game}, row {row}')
    return dict(game=game, decisions=len(expected), exact_actions=True)


def main():
    torch.set_num_threads(1)
    p = torch.tensor([[.8,.2]], dtype=torch.float64, requires_grad=True)
    q = torch.tensor([[.4,.6]], dtype=torch.float64)
    got = student_kl(p.log(), q.log())
    expected = (p * (p.log() - q.log())).sum(-1)
    reverse = (q * (q.log() - p.log())).sum(-1)
    assert torch.allclose(got, expected) and not torch.allclose(got, reverse)
    got.sum().backward()
    assert torch.isfinite(p.grad).all()
    assert student_kl(q.log(), q.log()).abs().max() < 1e-12
    games = [verify_game(p) for p in sorted((HERE/'games').glob('game-[0-9][0-9][0-9].npz'))]
    replays = []
    if len(games) == 40:
        loaded = ev.load_policy_checkpoint(INITIAL, device=DEVICE, decks_path=TRAINING)
        replays = [replay_actions(loaded, game) for game in (0, 21)]
    result = dict(kl_direction_and_gradient=True, games=games, saved_actor_replays=replays)
    write_json(HERE/'verification.json', result)
    log(result)

if __name__ == '__main__': main()
