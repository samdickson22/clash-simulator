"""Independently verify all retained paired controls and their declared roles."""

import collections
import json

import numpy as np
import run_controls as rc
from training_contract import COUNT, OUTPUT, PIN, ROLE, WORKERS, scenarios, validate
from value_contract import publish, sha


def main():
    rc.torch.set_num_threads(1)
    plan = validate()
    vocabulary = rc.load_current_client_typed_vocabulary()
    from collect_expansion import EXTRA_TOKENS

    completed = []
    for worker in range(WORKERS):
        record = json.loads((OUTPUT / f'worker{worker}-complete.json').read_text())
        expected = list(range(worker, COUNT, WORKERS))
        if record['worker'] != worker or record['ordinals'] != expected or record['pin_sha256'] != sha(PIN):
            raise ValueError('worker assignment or completion changed')
        completed.extend(record['ordinals'])
    if sorted(completed) != list(range(COUNT)):
        raise ValueError('every fixed control must be retained exactly once')
    counts, rows, audits, resources = collections.Counter(), 0, {}, {}
    for case in scenarios():
        directory = OUTPUT / f'game{case.ordinal:04}'
        record = json.loads((directory / 'complete.json').read_text())
        if (record['scenario_id'] != case.scenario_id or record['cluster_id'] != case.cluster_id
                or record['role'] != ROLE or record['pin_sha256'] != sha(PIN)):
            raise ValueError('physical game identity differs')
        for name, expected in record['artifacts'].items():
            if sha(directory / name) != expected:
                raise ValueError('collected artifact changed')
        result = json.loads((directory / 'result.json').read_text())
        if (not result['complete'] or result['initial_ordered_decks'] != [list(deck) for deck in case.relative_decks]
                or result['opening_scenario_id'] != case.scenario_id or not result['policy_selfplay'] or result['control_noop']):
            raise ValueError('unchanged complete frozen-policy physical run required')
        pair = []
        for seat in (0, 1):
            path = directory / f'seat{seat}.npz'
            metadata = {'schema': 'clasher.scalar-controlled-training.v1', 'role': ROLE, 'campaign_seed': 1281301,
                        'ordinal': case.ordinal, 'opening_scenario_id': case.scenario_id, 'opening_cluster_id': case.cluster_id,
                        'physical_game_id': case.scenario_id, 'policy_selfplay': True, 'control_noop': False,
                        'learner_seat': seat, 'policy_token_names': list(vocabulary.token_names),
                        'outcome_token_names': [*vocabulary.token_names, *EXTRA_TOKENS], 'pin_sha256': sha(PIN),
                        'natural_distribution': False}
            audit = rc.validate_scalar_corpus(path, expected_metadata=metadata)
            if audit != record['audits'][seat]:
                raise ValueError('independent corpus audit differs')
            with np.load(path, allow_pickle=False) as data:
                if (not np.array_equal(data['action'], [r['actions'][seat] for r in result['trace']])
                        or not np.array_equal(data['success'], [r['action_success'][seat] for r in result['trace']])
                        or not np.array_equal(data['tick'], [r['tick'] for r in result['trace']])
                        or not np.array_equal(data['terminal_tower_hp'], result['terminal_tower_hp_by_slot'])
                        or int(data['terminal_tick']) != result['ticks']):
                    raise ValueError('recorded actor view does not match actual run')
                pair.append((len(data['tick']), float(data['terminal_tower_margin']), int(np.argmax(data['outcome_wdl']))))
        if pair[0][0] != pair[1][0] or pair[0][0] != record['rows_each'] or pair[0][1] != -pair[1][1] or pair[0][2] != 2 - pair[1][2]:
            raise ValueError('paired view identity or opposite labels differ')
        counts[result['outcome']] += 1
        rows += sum(p[0] for p in pair)
        audits[str(case.ordinal)] = {'physical_game': case.scenario_id, 'cluster': case.cluster_id,
                                     'rows_each': pair[0][0], 'outcome_seat0': result['outcome']}
        resources[str((directory / 'complete.json').relative_to(OUTPUT))] = sha(directory / 'complete.json')
    validate()
    if len({case.cluster_id for case in scenarios()}) != COUNT or len(plan['cases']) != COUNT:
        raise ValueError('distinct fixed opening clusters required')
    publish(OUTPUT / 'complete.json', {'status': 'complete-audited-scalar-mirror-training-controls', 'pin_sha256': sha(PIN),
            'physical_games': COUNT, 'actor_views': COUNT * 2, 'rows': rows, 'physical_outcomes_seat0': dict(counts),
            'paired_actor_outcomes': {'draw': counts['draw'] * 2, 'win': counts['win'] + counts['loss'], 'loss': counts['win'] + counts['loss']},
            'games': audits, 'resources': resources, 'role': ROLE, 'fitting_performed': False,
            'natural_frequency_evidence': False, 'acceptance': False})
    print(json.dumps({'status': 'controls-reviewed', 'physical_outcomes': dict(counts), 'rows': rows}), flush=True)


if __name__ == '__main__':
    main()
