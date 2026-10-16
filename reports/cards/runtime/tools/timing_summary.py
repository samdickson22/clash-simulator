"""Summarize decision_timing.py outputs: python timing_summary.py OUT1.jsonl [OUT2.jsonl ...] (medians/means per phase;
paired by tick when two runs share the same command path)."""
import json
import statistics
import sys

runs = {}
for path in sys.argv[1:]:
    lines = open(path).read().splitlines()
    head, rows = json.loads(lines[0]), [json.loads(x) for x in lines[1:]]
    runs[path] = (head, rows)
keys = ['total_ms', 'poll', 'belief_update', 'propose', 'candidates', 'sample', 'root', 'json_ms', 'snapshot_ms',
        'begin_ms', 'ph:ship', 'ph:native', 'ph:learned', 'ph:parse', 'ph:chunk', 'rollouts', 'candidates_n',
        'payload_bytes', 'snapshot_bytes', 'config_bytes']


def get(r, k):
    if k.startswith('ph:'):
        return (r.get('phase_ms') or {}).get(k[3:])
    if k == 'candidates_n':
        return r.get('candidates')
    return r.get(k)


print('| run | scope | deck | decisions | ' + ' | '.join(keys) + ' |')
print('|' + '---|' * (4 + len(keys)))
for path, (h, rows) in runs.items():
    cells = []
    for k in keys:
        v = [get(r, k) for r in rows if get(r, k) is not None]
        cells.append(f'{statistics.median(v):.1f} / {statistics.mean(v):.1f}' if v else '—')
    print(f"| {path.split('/')[-1]} | {h['scope']} | {h['deck']} | {len(rows)} | " + ' | '.join(cells) + ' |')
paths = list(runs)
for i in range(len(paths)):
    for j in range(i + 1, len(paths)):
        A = {r['tick']: r for r in runs[paths[i]][1]}
        B = {r['tick']: r for r in runs[paths[j]][1]}
        common = sorted(set(A) & set(B))
        if not common:
            continue
        same_action = sum(A[t]['action'] == B[t]['action'] for t in common)
        ratio = [B[t]['total_ms'] / A[t]['total_ms'] for t in common if A[t]['total_ms'] > 0]
        print(f"pair {paths[i].split('/')[-1]} vs {paths[j].split('/')[-1]}: {len(common)} common ticks, "
              f"same action {same_action}, total_ms ratio median {statistics.median(ratio):.3f}, "
              f"command {runs[paths[i]][0]['command_sha256']} / {runs[paths[j]][0]['command_sha256']}")
