"""Retain every excluded prefix/continuation game and prove zero-prefix parity."""

import json

import numpy as np
import run_controls as rc
from late_continuation_contract import (
    EARLY_BASELINE,
    OUTPUT,
    PIN,
    cases,
    old_scenarios,
    validate,
)
from paired_writer import PairedWriter
from prefix_policy import FrozenContinuation
from value_contract import publish, sha


def exact_arrays(first, second):
    with np.load(first, allow_pickle=False) as a, np.load(second, allow_pickle=False) as b:
        return a.files == b.files and all(a[k].shape == b[k].shape and a[k].dtype == b[k].dtype
                                        and a[k].tobytes() == b[k].tobytes() for k in a.files if k != 'metadata_json')


def same_result(first, second):
    ignored = {'elapsed_seconds', 'prefix_control'}
    return {k: v for k, v in first.items() if k not in ignored} == {k: v for k, v in second.items() if k not in ignored}


def main():
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

    if OUTPUT.exists():
        raise ValueError('preserve previous late continuation evidence')
    OUTPUT.mkdir()
    fixed = cases()
    scheduled = (('zero-prefix-anchor', 0, old_scenarios()[0]), *fixed,
                 ('first-late-replay', fixed[0][1], fixed[0][2]))
    results = {}
    layout, table, _ = rc.configuration()
    for name, release, case in scheduled:
        validate()
        metadata = [{'schema': 'clasher.scalar-excluded-control.v1', 'role': 'excluded-late-frozen-continuation',
                    'case': name, 'learner_seat': seat, 'physical_game_id': case.scenario_id, 'opening_cluster_id': case.cluster_id,
                    'policy_token_names': list(vocabulary.token_names), 'outcome_token_names': [*vocabulary.token_names, *EXTRA_TOKENS],
                    'prefix_forced_pass_until_tick': release, 'frozen_policy_continuation_from_tick': release,
                    'prefix_future_policy_is_modified': bool(release),
                    'all_rows_excluded_from_fitting_and_calibration': True, 'pin_sha256': sha(PIN)} for seat in (0, 1)]
        paths = [OUTPUT / f'{name}-seat{seat}.npz' for seat in (0, 1)]
        policy = FrozenContinuation(model, release)
        before = rc.global_rng_digest()
        with PairedWriter(paths, metadata) as writer:
            result = rc.run(policy, builder, vocabulary, provider, None, seat=0, seed=1281501,
                            opening_scenario=case, expanded_receipts=True, policy_selfplay=True, episode_writer=writer)
        writer.finish(result)
        if before != rc.global_rng_digest() or policy.prefix_calls != release // 8 or policy.calls != writer.completed_rows:
            raise ValueError('prefix length, real stream or global RNG changed')
        if any(row['actions'] != [2304, 2304] for row in result['trace'] if row['tick'] < release):
            raise ValueError('prefix was not implemented as actual pass actions')
        post = [row for row in result['trace'] if row['tick'] >= release]
        if not post or post[0]['tick'] != release:
            raise ValueError('complete unmodified-policy continuation required')
        audits = []
        for seat, path in enumerate(paths):
            audit = rc.validate_scalar_corpus(path, expected_metadata=metadata[seat])
            state = rc.PublicFeatureState(layout, table)
            with np.load(path, allow_pickle=False) as data:
                for row in range(len(data['tick'])):
                    state.step({key: data[key][row] for key in rc.PUBLIC_FIELDS})
                if not np.array_equal(data['action'], [r['actions'][seat] for r in result['trace']]):
                    raise ValueError('paired actions differ from physical trace')
            if state.seen != writer.completed_rows:
                raise ValueError('complete public feature stream required')
            audits.append(audit)
        result['prefix_control'] = {'release_tick': release, 'suppressed_teacher_actions': policy.changed_actions,
                'prefix_decisions': policy.prefix_calls, 'post_release_decisions': len(post),
                'post_release_nonnoop_actions': sum(action != 2304 for r in post for action in r['actions']),
                'fitting': False, 'calibration': False}
        result = json.loads(json.dumps(result))
        if release == 0:
            baseline = json.loads((EARLY_BASELINE / 'order00.json').read_text())
            if not same_result(result, baseline) or not exact_arrays(paths[0], EARLY_BASELINE / 'order00.npz'):
                raise ValueError('zero-prefix wrapper changed original full trajectory')
        publish(OUTPUT / f'{name}.json', result)
        publish(OUTPUT / f'{name}-audit.json', {'views': audits, 'prefix_control': result['prefix_control']})
        results[name] = {key: result[key] for key in ('outcome', 'winner', 'ticks', 'terminal_tower_margin', 'prefix_control')}
        print(json.dumps({'case': name, **results[name]}), flush=True)
    first = json.loads((OUTPUT / f'{fixed[0][0]}.json').read_text())
    replay = json.loads((OUTPUT / 'first-late-replay.json').read_text())
    if not same_result(first, replay) or first['prefix_control'] != replay['prefix_control']:
        raise ValueError('late continuation replay differs')
    for seat in (0, 1):
        if not exact_arrays(OUTPUT / f'{fixed[0][0]}-seat{seat}.npz', OUTPUT / f'first-late-replay-seat{seat}.npz'):
            raise ValueError('late continuation replay arrays differ')
    validate()
    publish(OUTPUT / 'complete.json', {'status': 'complete-excluded-late-continuation', 'pin_sha256': sha(PIN),
            'cases': results, 'zero_prefix_original_exact': True, 'first_late_replay_exact': True, 'scope': plan['scope'],
            'fitting': False, 'acceptance': False, 'artifacts': {p.name: sha(p) for p in OUTPUT.iterdir() if p.is_file()}})


if __name__ == '__main__':
    main()
