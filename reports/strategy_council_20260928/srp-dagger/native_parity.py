"""Compare one full Python/native game on canonical data, outside training."""
import json
import numpy as np
import torch
from kit import (HERE, INITIAL, TRAINING, DEVICE, ev, config, collect_game,
                 sha, write_json, check_data_pins, sources_match)
from run import note


def main():
    torch.set_num_threads(1)
    pins = json.loads((HERE/'preflight.json').read_text())
    check_data_pins(pins)
    assert sources_match(pins['sources']) and sha(INITIAL) == pins['initial_sha256']
    folder = HERE/'native-parity'
    folder.mkdir(exist_ok=True)
    original = folder/'python/game-000.npz'
    replay = folder/'native/game-000.npz'
    loaded = ev.load_policy_checkpoint(INITIAL, device=DEVICE, decks_path=TRAINING)
    if not original.exists():
        collect_game(0, loaded, config(), backend='python', output_dir=original.parent)
    before = json.loads(original.with_suffix('.json').read_text())
    assert before['backend'] == 'python' and sha(original) == before['npz_sha256']
    canonical = json.loads((HERE/'canonical-data.json').read_text())
    assert before['gamedata_sha256'] == canonical['gamedata_sha256']
    if replay.exists():
        result = json.loads(replay.with_suffix('.json').read_text())
        assert result['backend'] == 'native' and sha(replay) == result['npz_sha256']
    else:
        result = collect_game(0, loaded, config(), backend='native', output_dir=replay.parent)
    assert result['gamedata_sha256'] == canonical['gamedata_sha256']
    checked = []
    with np.load(original, allow_pickle=False) as old, np.load(replay, allow_pickle=False) as new:
        assert set(old.files) == set(new.files)
        for key in old.files:
            # Metadata contains timestamps and the newly recorded backend name.
            if key == 'metadata_json':
                continue
            if key == 'root_candidate_values':
                different = np.flatnonzero(old[key] != new[key])
                score_differences = [dict(index=int(i), row=int(old['root_candidate_rows'][i]),
                    action=int(old['root_candidate_ids'][i]), python=float(old[key][i]),
                    native=float(new[key][i])) for i in different]
                continue
            assert np.array_equal(old[key], new[key]), key
            checked.append(key)
    for key in ('labels', 'decisions', 'end_tick', 'outcome', 'teacher_waits',
                'teacher_executions', 'playable_teacher_executions', 'rejected_executions'):
        assert before[key] == result[key], key
    receipt = dict(passed=True, game=0, gamedata_sha256=canonical['gamedata_sha256'],
        labels=result['labels'], decisions=result['decisions'],
        exact_arrays=checked, python_sha256=sha(original), native_sha256=sha(replay),
        root_score_differences=score_differences,
        python_planner_cpu_s=before['planner_cpu_s'], native_planner_cpu_s=result['planner_cpu_s'],
        python_game_cpu_s=before['total_cpu_s'], native_game_cpu_s=result['total_cpu_s'])
    write_json(HERE/'native-parity.json', receipt)
    note(f'Native parity passed: complete game 000, {result["decisions"]} decisions, '
         f'{result["labels"]} teacher labels; all public observations, masks, sampled student actions, '
         'mixed executed actions, labels and candidate IDs exactly equal. '
         f'{len(score_differences)} root scores differ; retained as diagnostics, not training targets. '
         'QA replay excluded from the 40-game training corpus. See native-parity.json.')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
