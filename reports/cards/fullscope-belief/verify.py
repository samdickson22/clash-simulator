"""Compare the complete C56 gate, then validate the separate full-pool smoke receipt."""
import json
from pathlib import Path
import sys


def read(root):
    rows = {}
    for suite in ('k4l', 'k4cw'):
        for path in (Path(root) / suite).glob('games-*.jsonl'):
            for line in path.read_text().splitlines():
                row = json.loads(line)
                key = (row['candidate'], row['opponent'], row['index'])
                assert key not in rows, key
                assert 'error' not in row and row['terminal'], row
                rows[key] = row
    expected = {('K4L-R-gs-rw-fc', opp, i) for opp in ('R3a', 'v1') for i in range(6)}
    expected.add(('K4CW-r16', 'R3a', 0))
    assert set(rows) == expected, (root, set(rows) ^ expected)
    return rows


def main(before, after, smoke, out):
    a, b = read(before), read(after)
    comparisons = []
    for key in sorted(a):
        same = a[key]['command_sha256'] == b[key]['command_sha256']
        comparisons.append(dict(candidate=key[0], opponent=key[1], case=key[2],
                                before=a[key]['command_sha256'], after=b[key]['command_sha256'], identical=same))
        assert same, comparisons[-1]
    positive = json.loads(Path(smoke).read_text())
    assert positive['result']['terminal'] and not positive['errors'] and not positive['fast_errors']
    assert not positive['panics'] and not positive['search_disabled']
    assert set(positive['required']) == set(positive['belief_contains']) <= set(positive['revealed'])
    assert positive['belief_class'] == 'FullPoolBelief'
    receipt = dict(pass_all=True, identical=len(comparisons), comparisons=comparisons,
                   smoke={k: positive[k] for k in ('required', 'revealed', 'belief_contains', 'belief_class',
                          'belief_rebuilds', 'fast', 'fast_errors', 'panics', 'search_disabled', 'errors')},
                   smoke_game={k: positive['result'][k] for k in ('command_sha256', 'terminal', 'ticks', 'winner',
                                                                 'cpu_seconds', 'decks', 'accepted')},
                   configurations=positive['configurations'])
    Path(out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(f'PASS: {len(comparisons)}/{len(comparisons)} identical C56 hashes; full-pool smoke passed')


if __name__ == '__main__':
    main(*sys.argv[1:])
