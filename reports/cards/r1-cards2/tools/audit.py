"""Audit complete gate coverage and exact outputs; no simulation or engine changes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

NATIVE = '5f07238c3c3c1eafa7ada7b87aae00f9c40f69f78680aca206a4733c7b729252'
BASE_NATIVE = '681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b'
TREE = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(TREE))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rows(files):
    return [json.loads(s) for p in sorted(files) for s in p.read_text().splitlines()]


def headline(path, games, candidate):
    rr = rows(path.glob('games-*.jsonl'))
    found = {(r['opponent'], r['index']): r for r in rr if r['candidate'] == candidate}
    expected = {(o, i) for o in ('R3a', 'v1') for i in range(games)}
    assert set(found) == expected and len(rr) == len(expected), (path, len(rr), len(found))
    assert all('error' not in r and r['terminal'] for r in rr), path
    return found


def roots(d):
    arms = {}
    headers = {}
    for arm, native in [('live', BASE_NATIVE), ('full', NATIVE)]:
        rr = []
        for p in sorted(d.glob(f'roots-{arm}-*.jsonl')):
            lines = [json.loads(s) for s in p.read_text().splitlines()]
            assert lines[0]['native_sha256'] == native, p
            headers[arm] = lines[0]
            rr += lines[1:]
        keyed = {(r['k'], r['variant']): r for r in rr}
        assert len(rr) == len(keyed) == 600, (arm, len(rr), len(keyed))
        full = {k for k, v in keyed if v == 'full'}
        cut = {k for k, v in keyed if v == 'cut'}
        assert full == cut and len(full) == 300
        arms[arm] = keyed
    assert arms['live'].keys() == arms['full'].keys()
    strip = lambda r: {k: v for k, v in r.items() if k != 'config_sha'}
    differences = [k for k in arms['live'] if strip(arms['live'][k]) != strip(arms['full'][k])]
    result = dict(records=600, sampled_roots=300, differing_ids=differences,
                  identical_by_variant={v: sum(k[1] == v and k not in differences for k in arms['live']) for v in ('full', 'cut')},
                  headers=headers)
    assert not differences, result
    return result


def k4l(d):
    cand = 'K4L-R-gs-rw-fc-p2'
    a, b = [headline(d / f'hl-k4l-{s}', 6, cand) for s in ('c56', 'full')]
    fields = ('command_sha256', 'winner', 'ticks', 'towers', 'score')
    diff = [k for k in a if any(a[k][f] != b[k][f] for f in fields)]
    assert not diff, diff
    return dict(games_per_arm=12, identical=12, errors=0,
                by_opponent={o: dict(cases=6, identical=6) for o in ('R3a', 'v1')})


def matches(path, expected):
    rr = rows([path])
    assert len(rr) == expected, (path, len(rr), expected)
    keys = [(r['deck'], r['opponent'], r['game']) for r in rr]
    assert len(set(keys)) == len(keys)
    assert all(r.get('terminal') and not r.get('crash') for r in rr), path
    counts = Counter()
    entities = Counter()
    per_deck = {}
    for r in rr:
        counts['games'] += 1
        for key in ('panics', 'fast_errors'):
            counts[key] += r.get(key) or 0
        for key in ('errors', 'native_failures', 'search_failures', 'root_errors'):
            counts[key] += sum((r.get(key) or {}).values())
        counts['roots'] += r['roots']
        counts['opp_noncore_roots'] += r['opp_noncore_roots']
        entities.update(r['noncore_entities_in_roots'])
        per_deck.setdefault(r['deck'], []).append(r)
        if r['deck'] != 'X1':
            # Fast tier does not call Resources.root; search streams must exercise new bodies.
            if not r['player'].startswith('LIVE-fast'):
                assert r['opp_noncore_roots'] and r['noncore_entities_in_roots'], r['deck']
    assert all(counts[k] == 0 for k in ('panics', 'fast_errors', 'errors', 'native_failures', 'search_failures', 'root_errors')), dict(counts)
    return dict(counts, crashes=0, terminal=len(rr), new_entity_names=sorted(entities),
                by_deck={d:dict(games=len(rs), roots=sum(r['roots'] for r in rs),
                                  opp_noncore_roots=sum(r['opp_noncore_roots'] for r in rs)) for d,rs in per_deck.items()})


def totality(d):
    result = {}
    for cfg in ('root', 'runtime'):
        for mode in ('plain', 'scrub'):
            p = d / f'totality-{cfg}-{mode}.json'
            data = json.loads(p.read_text())
            failures = [v for r in data['scenarios'].values() for cut in r['failures'].values() for v in cut.values()]
            counts = Counter(failures)
            assert all(x.startswith('ValueError: unsupported card absent') for x in failures), counts
            if mode == 'scrub':
                assert not failures, counts
            probes = sum(r['probes'] for r in data['scenarios'].values())
            assert probes == 6707, probes
            result[f'{cfg}-{mode}'] = dict(probes=probes, panics=0,
                failing_cuts=sum(r['failing_cuts'] for r in data['scenarios'].values()), failures=dict(counts))
    return result


def evaluate(d, current):
    from bot.eval.summarize import ci
    from reports.cards.live16402.tools.eval_compare import paired
    a = headline(d / 'hl-live16402b', 200, 'K4L-R-gs-rw-fc')
    currows = rows(current.glob('games-*.jsonl')) if current.is_dir() else rows([current])
    b = {(r['opponent'], r['index']):r for r in currows if r['candidate'] == 'K4L-R-gs' and r['index'] < 200 and r['opponent'] in ('R3a','v1')}
    assert b.keys() == a.keys() and all('error' not in r and r['terminal'] for r in b.values())
    result = {}
    for o in ('R3a','v1','pooled'):
        keys = sorted(k for k in a if o == 'pooled' or k[0] == o)
        group = {}
        for label, arm in [('live16402b', a), ('current', b)]:
            scores = [arm[k]['score'] for k in keys]
            group[label] = dict(games=len(scores), mean=sum(scores)/len(scores), ci95=list(ci(scores)),
                wins=scores.count(1), draws=scores.count(.5), losses=scores.count(0))
        diff = [a[k]['score']-b[k]['score'] for k in keys]
        group['paired_diff'] = dict(zip(('mean','lo','hi'), paired(diff)))
        group['identical_command_streams'] = sum(a[k]['command_sha256'] == b[k]['command_sha256'] for k in keys)
        result[o] = group
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['roots','k4l','cards-noncore','totality','live-matches','eval'])
    ap.add_argument('--gate', type=Path, required=True)
    ap.add_argument('--current', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    if a.stage == 'roots': result = roots(a.gate)
    elif a.stage == 'k4l': result = k4l(a.gate)
    elif a.stage == 'cards-noncore': result = matches(a.gate/'noncore-cards.jsonl',6)
    elif a.stage == 'totality': result = totality(a.gate)
    elif a.stage == 'live-matches': result = dict(live=matches(a.gate/'noncore-live.jsonl',33),fast=matches(a.gate/'fast-live.jsonl',36))
    else: result = evaluate(a.gate,a.current)
    patterns = {
        'roots': ['roots-*.jsonl'], 'k4l': ['hl-k4l-*/games-*.jsonl'],
        'cards-noncore': ['noncore-cards.jsonl'], 'totality': ['totality-*.json'],
        'live-matches': ['noncore-live.jsonl','fast-live.jsonl'],
        'eval': ['hl-live16402b/games-*.jsonl'],
    }
    files = [p for pattern in patterns[a.stage] for p in sorted(a.gate.glob(pattern))]
    receipt = dict(stage=a.stage,status='PASS',result=result,
        input_sha256={str(p.relative_to(a.gate)):sha(p) for p in files if p.suffix in ('.json','.jsonl')},
        audit_sha256=sha(Path(__file__)))
    if a.current: receipt['current_arm_sha256'] = sha(a.current) if a.current.is_file() else {p.name:sha(p) for p in a.current.glob('games-*.jsonl')}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(result,indent=1))
