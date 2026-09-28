"""Probe real scalar mirror outcomes and exact replay without changing physics."""

import json

import numpy as np
import torch
from control_contract import CASES, OUTPUT, PIN, source_authority, validate
from online_features import PUBLIC_FIELDS, PublicFeatureState
from stream_contract import configuration
from value_contract import publish, sha

from clasher.rl.simple_pytorch_backend import (
    _compile_public_mask_v2_tables,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.evaluate_hog26_simple_policy import load_model
from scripts.hog26_scalar_corpus import ScalarGameCorpusWriter, validate_scalar_corpus
from scripts.hog26_scalar_public_payload_mask import (
    ScalarPublicPayloadMaskProvider,
    ScalarPublicPayloadMaskRules,
)
from scripts.probe_hog26_scalar_complete_replay_20260909 import DECK, run
from scripts.probe_hog26_scalar_seeded_replay_20260909 import global_rng_digest


def main():
    torch.set_num_threads(1)
    pin = validate()
    authority = source_authority()
    if OUTPUT.exists():
        raise ValueError('preserve previous scalar draw feasibility')
    model, builder = load_model(pin['policy_checkpoint'], torch.device('cpu'))
    vocabulary = load_current_client_typed_vocabulary()
    if vocabulary.sha256 != authority['vocabulary_sha256']:
        raise ValueError('frozen policy vocabulary differs')
    setup = compile_standard_simple_setup(builder.loader, authority['contract']['canonical_names'], device='cpu', canonical_lane_globals=True)
    lookup, _ = _typed_lookups(setup, builder.loader, vocabulary)
    provider = SimplePublicMaskV2Provider(_compile_public_mask_v2_tables(builder, setup, lookup))
    from collect_expansion import EXTRA_TOKENS

    outcome_tokens = (*vocabulary.token_names, *EXTRA_TOKENS)
    mask_provider = ScalarPublicPayloadMaskProvider(provider, ScalarPublicPayloadMaskRules.compile(
        builder.loader, policy_token_names=vocabulary.token_names, outcome_token_names=outcome_tokens))
    layout, table, _ = configuration()
    OUTPUT.mkdir()
    publish(OUTPUT / 'manifest.json', {'pin_sha256': sha(PIN), 'fitting': False, 'acceptance': False})
    results = {}
    for name, seed, noop in CASES:
        validate()
        metadata = {'schema': 'clasher.scalar-excluded-control.v1', 'role': 'excluded-control-feasibility',
                    'case': name, 'seed': seed, 'policy_selfplay': True, 'control_noop': noop, 'learner_seat': 0,
                    'policy_token_names': list(vocabulary.token_names), 'outcome_token_names': list(outcome_tokens),
                    'mask_semantics_digest': mask_provider.semantics_digest, 'pin_sha256': sha(PIN),
                    'retention': 'all predecision rows through first actual terminal; no outcome filtering'}
        path = OUTPUT / f'{name}.npz'
        writer = ScalarGameCorpusWriter(path, metadata)
        before = global_rng_digest()
        result = run(model, builder, vocabulary, provider, None, seat=0, seed=seed, opponent_deck=DECK,
                     expanded_receipts=True, policy_selfplay=True, control_noop=noop, episode_writer=writer)
        if before != global_rng_digest():
            raise ValueError('scalar control consumed process-global RNG')
        writer.finish(terminal_tick=result['ticks'], winner=result['winner'], learner_seat=0,
                      terminal_tower_hp=result['terminal_tower_hp_by_slot'], initial_tower_hp=result['initial_tower_hp_by_slot'],
                      actual_terminal=result['complete'])
        if (result['initial_ordered_decks'][0] != result['initial_ordered_decks'][1]
                or result['initial_public_hand_ids'][0] != result['initial_public_hand_ids'][1]
                or result['extra_public_effect_tokens'] != list(EXTRA_TOKENS)
                or result['mask_semantics_digest'] != mask_provider.semantics_digest):
            raise ValueError('mirror opening or public-mask authority differs')
        audit = validate_scalar_corpus(path, expected_metadata=metadata)
        if audit['terminal_tower_margin'] != result['terminal_tower_margin']:
            raise ValueError('independent scalar label audit differs')
        with np.load(path, allow_pickle=False) as saved:
            public = {key: saved[key] for key in PUBLIC_FIELDS}
        state = PublicFeatureState(layout, table)
        for row in range(len(public['global_features'])):
            state.step({key: value[row] for key, value in public.items()})
        result['source_scope'] = metadata['role']
        result['encoder_rows'] = state.seen
        publish(OUTPUT / f'{name}.json', result)
        publish(OUTPUT / f'{name}-audit.json', audit)
        results[name] = {'winner': result['winner'], 'outcome': result['outcome'], 'ticks': result['ticks'],
                         'rows': state.seen, 'terminal_margin': result['terminal_tower_margin'], 'sha256': sha(path)}
        print(json.dumps({'case': name, 'status': 'excluded-control-complete', **results[name]}), flush=True)
    first = json.loads((OUTPUT / 'mirror_a.json').read_text())
    replay = json.loads((OUTPUT / 'mirror_a_replay.json').read_text())
    if {k: v for k, v in first.items() if k != 'elapsed_seconds'} != {k: v for k, v in replay.items() if k != 'elapsed_seconds'}:
        raise ValueError('frozen mirror replay result differs')
    with np.load(OUTPUT / 'mirror_a.npz', allow_pickle=False) as first, np.load(OUTPUT / 'mirror_a_replay.npz', allow_pickle=False) as replay:
        names = [name for name in first.files if name != 'metadata_json']
        if set(first.files) != set(replay.files) or not all(first[name].dtype == replay[name].dtype
                and first[name].shape == replay[name].shape and first[name].tobytes() == replay[name].tobytes() for name in names):
            raise ValueError('mirror replay arrays differ')
    validate()
    publish(OUTPUT / 'complete.json', {'status': 'complete-excluded-scalar-draw-feasibility', 'pin_sha256': sha(PIN),
            'cases': results, 'exact_mirror_replay': True, 'replay_metadata_difference': 'case provenance only',
            'frozen_mirror_draws': sum(results[name]['outcome'] == 'draw' for name in ('mirror_a', 'mirror_b')),
            'noop_draw': results['noop_terminal']['outcome'] == 'draw', 'fitting': False, 'acceptance': False,
            'artifacts': {path.name: sha(path) for path in OUTPUT.iterdir() if path.is_file()}})


if __name__ == '__main__':
    main()
