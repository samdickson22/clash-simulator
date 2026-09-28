"""Collect assigned prospective controls; no outcome filtering or policy updates."""

import argparse
import json

import run_controls as rc
from paired_writer import PairedWriter
from training_contract import OUTPUT, PIN, ROLE, WORKERS, scenarios, validate
from value_contract import publish, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', type=int, choices=range(WORKERS), required=True)
    worker = parser.parse_args().worker
    rc.torch.set_num_threads(1)
    plan = validate()
    pin = rc.validate()
    authority = rc.source_authority()
    model, builder = rc.load_model(pin['policy_checkpoint'], rc.torch.device('cpu'))
    vocabulary = rc.load_current_client_typed_vocabulary()
    setup = rc.compile_standard_simple_setup(builder.loader, authority['contract']['canonical_names'], device='cpu', canonical_lane_globals=True)
    lookup, _ = rc._typed_lookups(setup, builder.loader, vocabulary)
    provider = rc.SimplePublicMaskV2Provider(rc._compile_public_mask_v2_tables(builder, setup, lookup))
    from collect_expansion import EXTRA_TOKENS

    tokens = (*vocabulary.token_names, *EXTRA_TOKENS)
    completed = []
    for case in scenarios()[worker::WORKERS]:
        validate()
        expected = plan['cases'][case.ordinal]
        if expected['scenario_id'] != case.scenario_id or expected['deck_order'] != list(case.relative_decks[0]):
            raise ValueError('prospective deal differs')
        directory = OUTPUT / f'game{case.ordinal:04}'
        directory.mkdir()
        metadata = [{'schema': 'clasher.scalar-controlled-training.v1', 'role': ROLE, 'campaign_seed': 1281301,
                     'ordinal': case.ordinal, 'opening_scenario_id': case.scenario_id, 'opening_cluster_id': case.cluster_id,
                     'physical_game_id': case.scenario_id, 'policy_selfplay': True, 'control_noop': False,
                     'learner_seat': seat, 'policy_token_names': list(vocabulary.token_names), 'outcome_token_names': list(tokens),
                     'pin_sha256': sha(PIN), 'natural_distribution': False} for seat in (0, 1)]
        paths = [directory / f'seat{seat}.npz' for seat in (0, 1)]
        before = rc.global_rng_digest()
        with PairedWriter(paths, metadata) as writer:
            result = rc.run(model, builder, vocabulary, provider, None, seat=0, seed=1281301,
                            opening_scenario=case, expanded_receipts=True, policy_selfplay=True, episode_writer=writer)
        writer.finish(result)
        if before != rc.global_rng_digest():
            raise ValueError('process-global RNG changed')
        if (result['initial_ordered_decks'] != [list(deck) for deck in case.relative_decks]
                or result['initial_public_hand_ids'][0] != result['initial_public_hand_ids'][1]):
            raise ValueError('frozen mirror opening changed')
        audits = [rc.validate_scalar_corpus(path, expected_metadata=metadata[seat]) for seat, path in enumerate(paths)]
        if audits[0]['terminal_tower_margin'] != -audits[1]['terminal_tower_margin']:
            raise ValueError('paired terminal margin differs')
        publish(directory / 'result.json', result)
        publish(directory / 'complete.json', {'ordinal': case.ordinal, 'pin_sha256': sha(PIN),
                'scenario_id': case.scenario_id, 'cluster_id': case.cluster_id, 'role': ROLE,
                'rows_each': writer.completed_rows, 'outcome_seat0': result['outcome'], 'audits': audits,
                'artifacts': {p.name: sha(p) for p in directory.iterdir() if p.is_file()}, 'acceptance': False})
        completed.append(case.ordinal)
        print(json.dumps({'worker': worker, 'completed': len(completed), 'ordinal': case.ordinal,
                          'outcome_seat0': result['outcome'], 'rows_each': writer.completed_rows}), flush=True)
    validate()
    publish(OUTPUT / f'worker{worker}-complete.json', {'worker': worker, 'ordinals': completed, 'pin_sha256': sha(PIN)})


if __name__ == '__main__':
    main()
