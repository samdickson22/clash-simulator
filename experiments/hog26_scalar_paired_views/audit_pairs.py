"""Prove paired public capture against preserved loss and draw trajectories."""

import json

import numpy as np
import run_controls as rc
from order_contract import scenarios
from paired_contract import BASELINE, ORDINALS, OUTPUT, PIN, validate
from paired_writer import PairedWriter
from value_contract import publish, sha


def main():
    rc.torch.set_num_threads(1)
    validate()
    pin = rc.validate()
    authority = rc.source_authority()
    model, builder = rc.load_model(pin['policy_checkpoint'], rc.torch.device('cpu'))
    vocabulary = rc.load_current_client_typed_vocabulary()
    setup = rc.compile_standard_simple_setup(builder.loader, authority['contract']['canonical_names'], device='cpu', canonical_lane_globals=True)
    lookup, _ = rc._typed_lookups(setup, builder.loader, vocabulary)
    provider = rc.SimplePublicMaskV2Provider(rc._compile_public_mask_v2_tables(builder, setup, lookup))
    from collect_expansion import EXTRA_TOKENS

    tokens = (*vocabulary.token_names, *EXTRA_TOKENS)
    layout, table, _ = rc.configuration()
    if OUTPUT.exists():
        raise ValueError('preserve previous paired-view proof')
    OUTPUT.mkdir()
    reports = {}
    for ordinal in ORDINALS:
        case = scenarios()[ordinal]
        name = f'order{ordinal:02}'
        metadata = [{'schema': 'clasher.scalar-excluded-control.v1', 'role': 'excluded-paired-view-parity',
                     'case': name, 'opening_scenario_id': case.scenario_id, 'opening_cluster_id': case.cluster_id,
                     'physical_game_id': case.scenario_id, 'policy_selfplay': True, 'control_noop': False,
                     'learner_seat': seat, 'policy_token_names': list(vocabulary.token_names), 'outcome_token_names': list(tokens),
                     'pin_sha256': sha(PIN)} for seat in (0, 1)]
        paths = [OUTPUT / f'{name}-seat{seat}.npz' for seat in (0, 1)]
        before = rc.global_rng_digest()
        with PairedWriter(paths, metadata) as writer:
            result = rc.run(model, builder, vocabulary, provider, None, seat=0, seed=1281201,
                            opening_scenario=case, expanded_receipts=True, policy_selfplay=True, episode_writer=writer)
        writer.finish(result)
        if before != rc.global_rng_digest():
            raise ValueError('paired capture changed global RNG')
        baseline = json.loads((BASELINE / f'{name}.json').read_text())
        result = json.loads(json.dumps(result))
        if {k: v for k, v in result.items() if k != 'elapsed_seconds'} != {k: v for k, v in baseline.items() if k != 'elapsed_seconds'}:
            raise ValueError('paired recorder changed original physical trajectory')
        with np.load(BASELINE / f'{name}.npz', allow_pickle=False) as a, np.load(paths[0], allow_pickle=False) as b:
            if a.files != b.files or any(a[k].shape != b[k].shape or a[k].dtype != b[k].dtype or a[k].tobytes() != b[k].tobytes()
                                        for k in a.files if k != 'metadata_json'):
                raise ValueError('original seat0 arrays changed')
        audits = []
        for seat, path in enumerate(paths):
            audit = rc.validate_scalar_corpus(path, expected_metadata=metadata[seat])
            state = rc.PublicFeatureState(layout, table)
            with np.load(path, allow_pickle=False) as data:
                for row in range(len(data['tick'])):
                    state.step({key: data[key][row] for key in rc.PUBLIC_FIELDS})
                expected = np.asarray([record['actions'][seat] for record in result['trace']])
                success = np.asarray([record['action_success'][seat] for record in result['trace']])
                if not np.array_equal(data['action'], expected) or not np.array_equal(data['success'], success):
                    raise ValueError('paired view did not capture actual seat decisions')
            if state.seen != writer.completed_rows:
                raise ValueError('complete online feature stream required')
            audits.append(audit)
        if audits[0]['terminal_tower_margin'] != -audits[1]['terminal_tower_margin']:
            raise ValueError('opposite views must have opposite terminal margins')
        reports[name] = {'full_trajectory_exact': True, 'seat0_arrays_exact': True,
                         'paired_rows_each': writer.completed_rows, 'audits': audits, 'outcome_seat0': result['outcome']}
        publish(OUTPUT / f'{name}-result.json', result)
        print(json.dumps({'case': name, 'status': 'paired-view-parity-complete', 'rows_each': writer.completed_rows}), flush=True)
    validate()
    publish(OUTPUT / 'complete.json', {'status': 'complete-excluded-paired-view-proof', 'pin_sha256': sha(PIN),
            'cases': reports, 'acceptance': False, 'fitting': False,
            'artifacts': {p.name: sha(p) for p in OUTPUT.iterdir() if p.is_file()}})


if __name__ == '__main__':
    main()
