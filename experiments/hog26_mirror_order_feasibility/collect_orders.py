"""Keep every fixed mirror-order game and verify an exact observational replay."""

import json

import numpy as np
import run_controls as rc
from order_contract import OUTPUT, PIN, scenarios, validate
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
    if OUTPUT.exists():
        raise ValueError('preserve prior mirror-order collection')
    OUTPUT.mkdir()
    results = {}
    cases = [(f'order{case.ordinal:02}', case) for case in scenarios()]
    cases.append(('order00-replay', scenarios()[0]))
    for name, case in cases:
        validate()
        metadata = {'schema': 'clasher.scalar-excluded-control.v1', 'role': 'excluded-mirror-order-feasibility',
                    'case': name, 'opening_scenario_id': case.scenario_id, 'opening_cluster_id': case.cluster_id,
                    'policy_selfplay': True, 'control_noop': False, 'learner_seat': 0,
                    'policy_token_names': list(vocabulary.token_names), 'outcome_token_names': list(tokens),
                    'pin_sha256': sha(PIN), 'retention': 'Every outcome, complete predecision stream to first actual terminal'}
        path = OUTPUT / f'{name}.npz'
        writer = rc.ScalarGameCorpusWriter(path, metadata)
        before = rc.global_rng_digest()
        result = rc.run(model, builder, vocabulary, provider, None, seat=0, seed=1281201,
                        opening_scenario=case, expanded_receipts=True, policy_selfplay=True, episode_writer=writer)
        if before != rc.global_rng_digest():
            raise ValueError('process-global RNG changed')
        writer.finish(terminal_tick=result['ticks'], winner=result['winner'], learner_seat=0,
                      terminal_tower_hp=result['terminal_tower_hp_by_slot'], initial_tower_hp=result['initial_tower_hp_by_slot'],
                      actual_terminal=result['complete'])
        if (result['initial_ordered_decks'] != [list(deck) for deck in case.relative_decks]
                or result['initial_public_hand_ids'][0] != result['initial_public_hand_ids'][1]):
            raise ValueError('mirror opening differs')
        audit = rc.validate_scalar_corpus(path, expected_metadata=metadata)
        if audit['terminal_tower_margin'] != result['terminal_tower_margin']:
            raise ValueError('independent terminal label differs')
        publish(OUTPUT / f'{name}.json', result)
        publish(OUTPUT / f'{name}-audit.json', audit)
        results[name] = {key: result[key] for key in ('outcome', 'winner', 'ticks', 'terminal_tower_margin')}
        print(json.dumps({'case': name, **results[name]}), flush=True)
    original = json.loads((OUTPUT / 'order00.json').read_text())
    replay = json.loads((OUTPUT / 'order00-replay.json').read_text())
    if {k: v for k, v in original.items() if k != 'elapsed_seconds'} != {k: v for k, v in replay.items() if k != 'elapsed_seconds'}:
        raise ValueError('mirror replay result differs')
    with np.load(OUTPUT / 'order00.npz', allow_pickle=False) as a, np.load(OUTPUT / 'order00-replay.npz', allow_pickle=False) as b:
        if a.files != b.files or any(a[k].dtype != b[k].dtype or a[k].shape != b[k].shape or a[k].tobytes() != b[k].tobytes()
                                    for k in a.files if k != 'metadata_json'):
            raise ValueError('mirror replay arrays differ')
    validate()
    publish(OUTPUT / 'complete.json', {'status': 'complete-excluded-mirror-order-feasibility', 'pin_sha256': sha(PIN),
            'cases': results, 'exact_replay': True, 'fitting': False, 'acceptance': False,
            'artifacts': {p.name: sha(p) for p in OUTPUT.iterdir() if p.is_file()}})


if __name__ == '__main__':
    main()
