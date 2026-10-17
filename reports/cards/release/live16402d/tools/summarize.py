"""Content checks for gates.py outputs -> JOB/SUMMARY.json (r1-cards3-phase1 summarize.py, adapted).

    python summarize.py JOB REPO ENGINE_COMMIT

Stricter than r1-cards3: mixed runs must have ZERO root errors (no handled PublicGraphError), and the graph class probe
must show zero candidate errors. HEADLINE baseline hashes come from r1-cards3's GATES.json (same evaluator/baseline).
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

J, REPO = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
commit = sys.argv[3]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
out = dict(engine_commit=commit, assembly=json.loads((J / 'ASSEMBLY.json').read_text()))
for pin in ('r1-cards4', 'live16402d'):
    r = json.loads((J / f'smoke-{pin}.log').read_text().splitlines()[-1])
    assert r['scope'] == 'full' and r['meta_cards'] == 121 and r['templates'] >= 355, r
    out['smoke-' + pin] = r
    r = json.loads((J / f'none-{pin}.json').read_text())
    assert r['result'] == 'PASS' and not r['failures'], pin
    out['none-' + pin] = dict(checks=r['checks'], exceptions=0, input_sha256=sha(J / f'none-{pin}.json'))
paths = [J / f'objects-{i}.json' for i in range(4)]
source = {}
for path, h in json.loads(paths[0].read_text())['source_sha256'].items():
    p = Path(path)
    assert sha(p) == h, path
    if str(p).startswith(str(REPO) + '/'):
        suffix = str(p.relative_to(REPO))
    elif '/engine-rs/' in str(p):
        suffix = 'engine-rs/' + str(p).split('/engine-rs/')[1]
    else:
        suffix = 'reports/' + str(p).split('/reports/')[1]
    source[suffix] = h
(J / 'FROZEN-SOURCE.json').write_text(json.dumps(dict(commit=commit, source_sha256=source), indent=2) + '\n')
sys.path.insert(0, str(REPO / 'reports/cards/runtime/tools'))
from summarize_object_templates import summarize  # noqa: E402
r = summarize(paths, J / 'FROZEN-SOURCE.json')
(J / 'objects-summary.json').write_text(json.dumps(r, indent=2) + '\n')
out['class'] = {k: r[k] for k in ('result', 'cards', 'scenarios', 'total_checks', 'config_objects', 'templates')}
out['class'].update(observed_objects=len(r['objects']), exceptions=0)
assert out['class']['result'] == 'PASS'
out['totality'] = {}
expected = 'ValueError: unsupported card absent from imported pilot configuration'
for cfg in ('root', 'runtime'):
    for mode in ('plain', 'scrub'):
        p = J / f'totality-{cfg}-{mode}.json'
        r = json.loads(p.read_text())
        fail = Counter(v for x in r['scenarios'].values() for cut in x['failures'].values() for v in cut.values())
        unexpected = {k: v for k, v in fail.items() if k != expected}
        assert not unexpected, unexpected
        if mode == 'scrub':
            assert not fail, fail
        out['totality'][f'{cfg}-{mode}'] = dict(
            probes=sum(x['probes'] for x in r['scenarios'].values()), panics=0, unexpected_errors=0,
            expected_rejections=fail.get(expected, 0),
            failing_cuts=sum(x['failing_cuts'] for x in r['scenarios'].values()), input_sha256=sha(p))
base = {(c['opponent'], c['index']): c['baseline_sha256']
        for c in json.loads((REPO / 'reports/cards/r1-cards3/receipts/GATES.json').read_text())['headline']['cases']}
rows = [json.loads(s) for p in (J / 'hl-candidate').glob('games-*.jsonl') for s in p.read_text().splitlines()]
assert len(rows) == 12 and all('command_sha256' in r and not r.get('error') for r in rows), rows
cand = {(r['opponent'], r['index']): r['command_sha256'] for r in rows}
assert set(cand) == set(base) == {(o, i) for o in ('R3a', 'v1') for i in range(6)}
cases = [dict(opponent=k[0], index=k[1], baseline_sha256=base[k], candidate_sha256=cand[k]) for k in sorted(base)]
out['headline'] = dict(identical=sum(c['baseline_sha256'] == c['candidate_sha256'] for c in cases), cases=cases,
                       baseline_source='reports/cards/r1-cards3/receipts/GATES.json')
assert out['headline']['identical'] == 12, cases
mixed = [json.loads(s) for s in (J / 'mixed.jsonl').read_text().splitlines()]
extra = [json.loads(s) for s in (J / 'mixed-3m.jsonl').read_text().splitlines()]
assert len(mixed) == 4 and len(extra) == 2
for r in mixed + extra:
    bad = {k: r.get(k) for k in ('crash', 'errors', 'panics', 'fast_errors', 'native_failures', 'search_failures',
                                 'root_errors') if r.get(k)}
    assert not bad, (r['player'], r['deck'], bad)
    assert r['roots'] > 0 if r['player'].startswith('LIVE-K4L') else True
for r in extra:
    assert r['opp_played'].get('ThreeMusketeers', 0) > 0, r
keep = ('player', 'deck', 'seed', 'ticks', 'command_sha256', 'sources', 'roots', 'opp_noncore_roots')
out['mixed'] = dict(runs=len(mixed) + len(extra), crashes=0, root_errors=0,
                    roots=sum(r['roots'] for r in mixed + extra), rows=[{k: r.get(k) for k in keep} for r in mixed + extra])
st = json.loads((J / 'stress.json').read_text())
m = st['metrics']
assert m.get('candidate_graph_errors', 0) == 0 and m.get('root_errors', 0) == 0 and m['roots'] > 0
out['graph_class'] = dict(helper_sha256=st['helper_sha256'], runtime=st['runtime'], games=len(st['games']),
                          **{k: m.get(k, 0) for k in ('roots', 'attached_rows', 'structural_boards',
                                                      'structural_partial_boards', 'native_structural_continuations',
                                                      'candidate_graph_errors', 'prefix_a156cf5b1_graph_errors',
                                                      'b1_244e385ca_graph_errors')})
inputs = [p for p in J.glob('*.json') if p.name not in ('SUMMARY.json', 'objects-summary.json')]
inputs += list(J.glob('hl-candidate/games-*.jsonl')) + [J / 'mixed.jsonl', J / 'mixed-3m.jsonl']
out['inputs'] = {str(p.relative_to(J)): sha(p) for p in sorted(inputs)}
out['result'] = 'PASS'
(J / 'SUMMARY.json').write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
print(json.dumps({k: v for k, v in out.items() if k not in ('inputs', 'mixed', 'headline', 'assembly')}, indent=1))
print('HEADLINE', out['headline']['identical'], 'MIXED', out['mixed']['runs'], 'SUMMARY', sha(J / 'SUMMARY.json'))
