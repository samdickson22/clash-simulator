"""Read-only final-bank integrity audit; never constructs a simulator/player."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from fullpool_clean import problems

ROOT = Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')
D = ROOT / 'fullpool'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    bank_path = D / 'validation/bank.json'
    bank = json.loads(bank_path.read_text())
    variant = json.loads((ROOT / 'variant-B-full-budget.json').read_text())
    bank_sha = digest(bank_path)
    assert bank_sha == '8eaf2214600b5a0fa31297cf113e482ac9b02e81cdc8db9adaabf41b2b82a8a2'
    cases = {case['id']: case for case in bank['cases']}
    assert Counter(case['opponent'] for case in cases.values()) == {
        'R3a': 150, 'v1': 150, 'LIVE-K4CW-r16': 150}
    expected = {(case, candidate, player) for case in cases
                for candidate in bank['candidates'] for player in bank['players']}
    rows = [json.loads(p.read_text()) for p in (D / 'validation/rows').glob('*.json')]
    keys = [(r['id'], r['candidate'], r['player']) for r in rows]
    assert len(rows) == 4500 and len(keys) == len(set(keys)) and set(keys) == expected
    drops = Counter()
    host_counts = Counter()
    search_decisions = 0
    for row in rows:
        case = cases[row['id']]
        assert row['bank_sha256'] == bank_sha and not problems(row)
        for key in ('seed', 'seat', 'opponent', 'opponent_deck', 'opponent_levels',
                    'own_permutation', 'source_index'):
            assert row[key] == case[key], (row['index'], key)
        result = row['result']
        seat = row['seat']
        assert result['terminal']
        assert bool(row['win']) == (result['winner'] == seat)
        assert set(result['decks'][seat]) == set(variant['candidates'][row['candidate']])
        assert set(result['decks'][1 - seat]) == set(case['opponent_deck'])
        own = result['public_diagnostics'][str(seat)]
        config = own['start_config']
        assert config['belief_class'] == 'FullPoolBelief'
        assert config['name'] == row['player']
        assert config['fast_path'].endswith('/fits/f1a2/step-001200.pt')
        assert config['native_threads'] == 1 and config['pool_size'] == 0
        assert config['chunks'] == 4
        assert all(config[key] is None for key in (
            'deadline_seconds', 'effective_deadline_seconds', 'search_deadline_seconds'))
        assert own['cutoff_hits'] == 0
        search_decisions += own['search_decisions']
        assert all(reason == 'OK' or count == 0 for reason, count in
                   result['deploy_reasons'][str(seat)].items())
        if row['opponent'] == 'LIVE-K4CW-r16':
            strong = result['public_diagnostics'][str(1 - seat)]['start_config']
            assert strong['belief_class'] == 'LiveBelief' and strong['runtime_belief'] == 'c56'
            assert strong['fast_path'].endswith('/students/it5s2-step001200.pt')
            assert strong['fast_threshold'] == .5375
        drops.update(row['unmapped'])
        host_counts[row['host']] += 1
    assert set(drops) <= {'unmapped_unit:SpearGoblin_Dummy'}, drops
    recovery = json.loads((D / 'resume-manifest.json').read_text())['preserved_rows']
    interim = json.loads((D / 'interim-50/snapshot.json').read_text())['rows']
    for preserved in (recovery, interim):
        for name, value in preserved.items():
            assert digest(D / 'validation/rows' / name) == value, name
    assert digest(ROOT / 'fullpool_worker.py') == '3950dee71274bf9ecefa6c3cbe075bd756a82f8c96de79a93d4cca3f3ea47af1'
    assert digest(ROOT / 'fullpool_eval.py') == '0b8181c805a6e748c970e22936c8b1311f6fe8fb1c18d7d1c317532a5d28680a'
    assert digest(ROOT / 'variant-B-full-budget.json') == '190e15df6ecea88da441ef29f2c45da56316558a5174516054997191dc5de968'
    audit = dict(utc=subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip(),
                 bank_sha256=bank_sha, games=len(rows), complete_cases=len(cases),
                 per_policy_cases=dict(Counter(c['opponent'] for c in cases.values())),
                 genuine_failures=0, cutoff_hits=0, search_decisions=search_decisions,
                 raw_drop_counters=dict(drops), preserved_recovery_hashes=len(recovery),
                 preserved_interim_hashes=len(interim), host_games=dict(host_counts), passed=True)
    (D / 'final-integrity-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(audit))


if __name__ == '__main__':
    main()
