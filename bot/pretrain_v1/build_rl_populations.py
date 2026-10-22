"""Freeze joint historical profiles and explicit synthetic stress profiles.

No engine, inference, games or outcomes are generated. The output is a draft
registration input until independent review accepts its exact sources/rules.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bot.pretrain_v1 import rl_schedule as S
from bot.fullpool.cards import POOL, CHAMPIONS, engine_name


def ref(path):
    return dict(path=str(Path(path).resolve()), sha256=S.file_sha(path))


def build(table_path, log_directory, adjacent_path, banks, run_exclusions, *, evaluation=False):
    table = json.loads(Path(table_path).read_text())
    sources = [ref(table_path), ref(adjacent_path), *(ref(p) for p in banks), *(ref(p) for p in run_exclusions)]
    excluded_runs, excluded_decks = set(), set()
    for path in run_exclusions:
        excluded_runs.update(json.loads(Path(path).read_text())['runs'])
    for path in banks:
        bank = json.loads(Path(path).read_text())
        for case in bank['cases']:
            excluded_decks.add(tuple(sorted(engine_name(c) for c in case['opponent_deck'])))
            if case.get('source_run'):
                excluded_runs.add(case['source_run'])
    raw = {'empirical': [], 'adjacent': []}
    for name, sha in table['source']['sha256'].items():
        path = Path(log_directory)/name
        S.require(S.file_sha(path) == sha, f'original historical source changed: {name}')
        sources.append(ref(path))
        raw['empirical'].extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
    raw['adjacent'] = [json.loads(line) for line in Path(adjacent_path).read_text().splitlines() if line.strip()]
    retained, counts = {}, {}
    for family, rows in raw.items():
        out, excluded, seen = [], Counter(), set()
        for row in rows:
            reason = None
            try:
                deck = [engine_name(c) for c in row['opp_deck']]
                cards = dict(zip(deck, row['opp_levels']))
                profile = dict(deck=deck, cards=cards, tower=row['opp_king_level'], weight=1,
                               source_id=row['run'])
                S.profile(profile, set(POOL))
                S.require(len(row['opp_levels']) == 8 and sum(c in CHAMPIONS for c in deck) <= 1,
                          'incomplete levels or multiple champions')
                expected = 'royal-arena' if family == 'empirical' else 'pekkas-playhouse'
                S.require(row['arena'] == expected, 'wrong source arena')
                if row['run'] in excluded_runs:
                    reason = 'evaluation_source_run'
                elif tuple(sorted(deck)) in excluded_decks:
                    reason = 'evaluation_deck_identity'
                elif row['run'] in seen:
                    reason = 'duplicate_physical_run'
            except (KeyError, TypeError, ValueError) as ex:
                reason = 'incomplete_or_unqualified_identity_levels'
            if evaluation and reason in ('evaluation_source_run', 'evaluation_deck_identity'):
                reason = None
            elif evaluation and reason is None:
                reason = 'reserved_for_training'
            if reason:
                excluded[reason] += 1
            else:
                seen.add(row['run'])
                out.append(profile)
        S.require(out, f'no eligible historical profiles in {family}; do not substitute medians')
        retained[family] = out
        counts[family] = dict(source_rows=len(rows), retained_rows=len(out), excluded=dict(excluded),
                              excluded_fraction=(len(rows)-len(out))/len(rows))
    historical = retained['empirical']+retained['adjacent']
    realistic = [r for r in historical if 8 <= r['tower'] <= 11]
    S.require(realistic, 'no historical realistic meta profiles')
    stress = []
    for row in historical:
        for level in range(12, 17):
            stress.append(dict(deck=row['deck'], cards=dict.fromkeys(row['deck'], level), tower=level,
                weight=1, source_id=f"synthetic-stress-{level}-from-{row['source_id']}"))
    meta = [dict(r, weight=.8/len(realistic), level_kind='realistic') for r in realistic]
    meta += [dict(r, weight=.2/len(stress), level_kind='stress') for r in stress]
    return S.validate_populations(dict(schema='pv1-rl-populations-v1', vocabulary=list(POOL), champions=sorted(CHAMPIONS),
        opponents=dict(retained, stress=stress), meta=meta,
        random_card_levels={c: 11 if c in CHAMPIONS else 9 for c in POOL}, random_tower=9,
        excluded_mass=counts, sources=sources, registration_status='DRAFT-requires-source-bound-GO',
        role='evaluation-only' if evaluation else 'training-only',
        physical_source_ids=sorted({r['source_id'] for r in historical}),
        rules=dict(empirical='joint observed royal-arena deck/card/tower levels; one weight per retained battle',
                   adjacent='joint observed adjacent pekkas-playhouse profiles; one weight per retained battle',
                   meta='retained historical deck frequency; 80% historical King8..11 / 20% synthetic stress',
                   stress='retain historical deck frequency; each all-card/tower level12..16 gets equal mass',
                   random='121 qualified vanilla cards; at most one champion; level9 except champion floor11; King9',
                   exclusion='union frozen bank opponent-deck identities and explicit physical run inventories')))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--table', required=True, type=Path)
    p.add_argument('--logs', required=True, type=Path)
    p.add_argument('--adjacent', required=True, type=Path)
    p.add_argument('--bank', action='append', required=True, type=Path)
    p.add_argument('--run-exclusions', action='append', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--evaluation-only', action='store_true')
    a = p.parse_args()
    population = build(a.table, a.logs, a.adjacent, a.bank, a.run_exclusions, evaluation=a.evaluation_only)
    with a.out.open('xb') as out:
        out.write(S.encoded(population)+b'\n')
    print(json.dumps(dict(artifact=ref(a.out), excluded_mass=population['excluded_mass']), indent=2))


if __name__ == '__main__':
    main()
