"""Register the independent true-Battle-Log validation after gate and selection."""
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess

ROOT = Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')
DEST = ROOT / 'fullpool'
REPO = Path('/mpac/sdicks02/repos/clasher-bot-deckopt2-fullpool')
OPPONENTS = ('R3a', 'v1', 'LIVE-K4CW-r16')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc():
    return subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], text=True).strip()


def exclusive(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)


def prepare():
    from bot.fullpool.cards import C56, engine_name
    from bot.levels.profile import clamp, RARE_OFFSET
    gate = json.loads((DEST / 'gate-approved.json').read_text())
    assert gate['approved'] is True
    config = json.loads((DEST / 'player-config.json').read_text())
    assert config['mode'] in ('no-wall', 'wall200')
    replay = json.loads((DEST / 'repeat-proof.json').read_text())
    assert replay['passed'] and replay['player_config_sha256'] == sha(DEST / 'player-config.json')
    assert replay['adapter_sha256'] == sha(ROOT / 'fullpool_eval.py')
    assert replay['worker_sha256'] == sha(ROOT / 'fullpool_worker.py')
    if config['mode'] == 'wall200':
        timing = json.loads((DEST / 'timing-policy.json').read_text())
        assert timing['wall200_allowed'] is True and timing['reserved_core_cutoff_rate'] < .10
    smoke = json.loads((DEST / 'smoke-result.json').read_text())
    assert smoke['result']['terminal'] and not smoke['unmapped']
    assert not smoke['native_failures'] and not any(smoke['live_errors'].values())
    assert not any(smoke['packet_issues'].values())
    strong_smoke = json.loads((DEST / 'strong-smoke-result.json').read_text())
    assert strong_smoke['result']['terminal'] and not strong_smoke['failures'] and not strong_smoke['unmapped']
    assert not any(strong_smoke['errors'].values())
    assert strong_smoke['diagnostics']['0']['start_config']['belief_class'] == 'FullPoolBelief'
    assert strong_smoke['diagnostics']['1']['start_config']['belief_class'] == 'LiveBelief'
    assert strong_smoke['diagnostics']['0']['start_config'].get('effective_deadline_seconds','missing') is None
    assert strong_smoke['diagnostics']['1']['start_config'].get('effective_deadline_seconds','missing') is None
    selection = json.loads((ROOT / 'selection.json').read_text())
    variant = json.loads((ROOT / 'variant-B-full-budget.json').read_text())
    assert sha(ROOT / 'variant-B-full-budget.json') == '190e15df6ecea88da441ef29f2c45da56316558a5174516054997191dc5de968'
    assert selection['variant_sha256'] == sha(ROOT / 'variant-B-full-budget.json')
    names = selection['selected']
    assert all(set(variant['candidates'][name]) <= set(C56) for name in names)
    population = [json.loads(line) for line in (ROOT / 'opponent-decks.jsonl').read_text().splitlines()]
    assert len(population) == 91
    original = json.loads((ROOT / 'manifest.json').read_text())
    rarity_rows = json.loads((ROOT / 'upgrade-source-gamedata.json').read_text())['items']['spells']
    rarities = {engine_name(row['name'], strict=False): str(row['rarity']).lower() for row in rarity_rows}
    true_cards = {engine_name(c) for row in population for c in row['opp_deck']}
    assert true_cards <= set(rarities), sorted(true_cards - set(rarities))
    assert all(rarities[c] in ('common','rare','epic','legendary','champion') for c in true_cards)
    model_pins = json.loads((DEST / 'model-pins.json').read_text())
    assert all(sha(DEST / path) == digest for path, digest in model_pins.items())
    helpers = ('fullpool_eval.py', 'fullpool_bank.py', 'fullpool_worker.py', 'fullpool_queue.py', 'fullpool_entry.py', 'run-fullpool-pool.sh')
    meta = dict(created_utc=utc(), scenario='true Battle Log full-pool', card_scope='owned C56 only',
                source_commit='1a65dcd1a00c5e3f891228df878d3bbebe4de187', runtime_pin='live16402b-r3',
                native_sha256='de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1',
                gamedata_sha256='a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb',
                simulator=original['simulator'], own_tower=6, opponent_tower=6,
                planner='unchanged deployed root/belief level handling; no ExactLevelRoot',
                candidates={name: variant['candidates'][name] for name in names},
                candidate_plans={name: variant['plans'][name] for name in names},
                player_config=config, players=config['players'], opponents=OPPONENTS,
                selection_sha256=sha(ROOT / 'selection.json'), variant_sha256=sha(ROOT / 'variant-B-full-budget.json'),
                collection_sha256=variant['collection_sha256'], population_sha256=sha(ROOT / 'opponent-decks.jsonl'),
                gate_sha256=sha(DEST / 'gate-approved.json'), repeat_proof_sha256=sha(DEST / 'repeat-proof.json'), models=model_pins,
                vocab_sha256=sha(DEST / 'vocab-combined.json'),
                helper_sha256={name: sha(ROOT / name) for name in helpers},
                source_sha256={str(path.relative_to(REPO)): sha(path) for directory in ('bot', 'reports/explore/x4s')
                               for path in sorted((REPO / directory).rglob('*.py'))},
                opponent_common_prior=original['opponent_common_prior'],
                strong='LiveBelief C56 + it5s2, threads1, extended R3a proposer; separate Runtime',
                pairing='all candidate/player arms of a case share host/worker; randomized arm order; atomic central case claims',
                rext_bc='n/a: C56-only policy')
    exclusive(DEST / 'manifest.json', meta)
    entropy = os.urandom(16).hex()
    rng = random.Random(int(entropy, 16))
    levels, weights = zip(*meta['opponent_common_prior'])
    cases = []
    for oi, opponent in enumerate(OPPONENTS):
        for i in range(150):
            seed = rng.randrange(1 << 48)
            crng = random.Random(seed)
            source_index = crng.randrange(91)
            deck = [engine_name(c) for c in population[source_index]['opp_deck']]
            assert len(set(deck)) == len(deck) == 8
            crng.shuffle(deck)
            order = list(range(8)); crng.shuffle(order)
            lrng = random.Random(seed ^ 0x1E7E1)
            opp_levels = {c: clamp(rarities[c], lrng.choices(levels, weights=weights)[0] -
                                   RARE_OFFSET.get(rarities[c], 1)) for c in deck}
            cases.append(dict(id=f'{oi}-{i:04d}', opponent=opponent, index=i, seed=seed, seat=i % 2,
                              source_index=source_index, opponent_deck=deck, opponent_levels=opp_levels,
                              own_permutation=order))
    dispatch = list(range(len(cases))); rng.shuffle(dispatch)
    used = set()
    for relative in ('screen', 'new-cards/screen', 'final-validation/validation'):
        prior = json.loads((ROOT / relative / 'bank.json').read_text())
        used.update(case['seed'] for case in prior['cases'])
    assert not used & {case['seed'] for case in cases}
    data = dict(stage='validation', scenario='true Battle Log full-pool', created_utc=utc(), entropy_hex=entropy,
                cases=cases, cases_per_policy=150, candidates=names, players=config['players'],
                dispatch_order=dispatch, own_tower=6, opponent_tower=6,
                candidate_levels={name: meta['candidate_plans'][name]['levels'] for name in names},
                own_levels=meta['candidate_plans']['baseline']['levels'], collection_sha256=meta['collection_sha256'],
                manifest_sha256=sha(DEST / 'manifest.json'))
    exclusive(DEST / 'validation/bank.json', data)
    (DEST / 'validation/rows').mkdir()
    print('TRUE_DECK_BANK', data['created_utc'], sha(DEST / 'validation/bank.json'),
          len(cases), 'cases', len(cases)*len(names)*len(config['players']), 'games', flush=True)


if __name__ == '__main__':
    prepare()
