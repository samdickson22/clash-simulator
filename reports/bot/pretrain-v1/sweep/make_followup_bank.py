"""Generate the registered fresh S/M banks; no games, weights or outcomes are loaded."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import sys

R1 = Path('/mpac/sdicks02/scratch/rl-search-prior-20261020')
R2 = Path('/mpac/sdicks02/scratch/rl-search-prior-20261020-r2')


def build(base, reference, other_seeds, rd, lp, table, classify):
    old = reference['cases']
    own_levels = next(c['own_levels'] for c in old if c['row'] == 'HOG26-acct')
    cases = []
    for oi, opponent in enumerate(['LIVE-K4CW-r16-fp', 'R3a']):
        for i in range(800):
            g = oi*801+i
            seed = base+g
            rng = random.Random(seed)
            other, source = rd.opp_deck(g, base, frozenset(reference['exclude']))
            own = list(own_levels)
            levels = lp.dist_levels(table, other, own=own_levels)
            rng.shuffle(own)
            rng.shuffle(other)
            cases.append(dict(index=len(cases), id=f'pv1-{base}-{oi}-{i:04}', row='HOG26-acct', seed=seed,
                              seat=i % 2, opponent=opponent, own_deck=own, own_levels=own_levels, own_king=9,
                              opponent_deck=other, opponent_levels=levels, opponent_king=int(table['king']),
                              opp_source=source, opp_archetype=classify(other)))
    seeds = {c['seed'] for c in cases}
    assert len(seeds) == 1600 and not seeds.intersection(other_seeds)
    assert not {c['id'] for c in cases}.intersection(c['id'] for c in old)
    return dict(base=base, cases=cases, cases_per_opponent=800, mix=rd.OPP_MIX_SPEC,
                exclude=reference['exclude'], corpus_sha256=reference['corpus_sha256'],
                level_table_sha256=reference['level_table_sha256'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    reference = json.loads((R2/'evaluation/bank.json').read_text())
    # Reuse the exact distribution and level functions that produced the r2 source bank, in this generator only.
    sys.path.insert(0, str(R2))
    import eval_setup
    import bot
    bot.__path__.append(str(R1/'rl-source/bot'))
    os.environ['BOT_RL_CORPUS_DECKS'] = str(R1/'evidence/corpus-decks-v1.jsonl')
    import bot.rl
    bot.rl.__path__.append(str(R1/'rl-source/bot/rl'))
    from bot.rl import decks as rd
    import bot.fullpool
    bot.fullpool.__path__.append(str(R1/'rl-source/bot/fullpool'))
    from bot.fullpool.archetype import classify
    spec = importlib.util.spec_from_file_location('bank_levelplan', R1/'rl-source/bot/search/levelplan.py')
    lp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lp)
    for name, key in [('corpus-decks-v1.jsonl', 'corpus_sha256'), ('opp-levels-dist.json', 'level_table_sha256')]:
        assert hashlib.sha256((R1/'evidence'/name).read_bytes()).hexdigest() == reference[key]
    table = json.loads((R1/'evidence/opp-levels-dist.json').read_text())
    seen = {c['seed'] for c in reference['cases']}
    a.out.mkdir(parents=True, exist_ok=True)
    for name, base in [('power-v3', 2026102201000000), ('next-snapshot', 2026102202000000)]:
        d = build(base, reference, seen, rd, lp, table, classify)
        raw = (json.dumps(d, sort_keys=True, indent=1)+'\n').encode()
        p = a.out/f'{name}-bank.json'
        if p.exists():
            assert p.read_bytes() == raw, 'refusing to change frozen bank'
        else:
            with p.open('xb') as f:
                f.write(raw)
        seen.update(c['seed'] for c in d['cases'])
        print(name, len(d['cases']), hashlib.sha256(raw).hexdigest(), flush=True)


if __name__ == '__main__':
    main()
