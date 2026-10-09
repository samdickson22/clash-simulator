"""Select the controller's exact completed-game prefixes, without outcome selection."""
import hashlib
import json
from pathlib import Path
import sys

host = sys.argv[1]
job = Path('/mpac/sdicks02/jobs/clasher/exit-r1-20261009-r1')
out = Path(sys.argv[2])
expected = {'03': (13169, 10277816, 1594935),
            '04': (17980, 14072510, 2183723),
            '08': (18428, 14388208, 2231023)}[host]
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
records = [json.loads(line) for line in (job/'generation/completed.jsonl').open()]
selected = records[:expected[0]]
assert (len(selected), sum(r['rows'] for r in selected),
        sum(r['root_decisions'] for r in selected)) == expected
launch = json.loads((job/'generation/launch.json').read_text())
base = launch['options']['seed']
entries = []
for r in selected:
    index = r['seed'] - base
    game = job/'generation'/f'game-{index:09d}'
    seal = json.loads((game/'manifest.json').read_text())
    assert seal['complete'] and seal['rows'] == r['rows']
    entries.append({'directory': game.name, 'seed': r['seed'],
                    'manifest_sha256': sha(game/'manifest.json')})
exit_receipt = json.loads((job/'generation/exit.json').read_text())
assert exit_receipt['fully_vacated']
assert all(not c['alive'] and c['exitcode'] == 0 for c in exit_receipt['children'])
out.mkdir(parents=True, exist_ok=True)
(out/'files.txt').write_text(''.join(e['directory']+'\n' for e in entries))
(out/'selection.json').write_text(json.dumps(dict(host='127x'+host,
    games=expected[0], rows=expected[1], roots=expected[2],
    selection='completed.jsonl prefix at frozen controller progress counts',
    completed_log_sha256=sha(job/'generation/completed.jsonl'),
    generation_exit_sha256=sha(job/'generation/exit.json'),
    launch_sha256=sha(job/'generation/launch.json'),
    excluded_drain_games=len(records)-len(selected), games_index=entries), indent=2)+'\n')
print(json.dumps(dict(host=host,games=expected[0],rows=expected[1],roots=expected[2],
                     selection_sha256=sha(out/'selection.json'))))
