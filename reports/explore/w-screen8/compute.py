"""Compact task-only process, scheduling and completion receipt."""
import json
from pathlib import Path
import sys

job=Path(sys.argv[1]);samples=[]
for phase in ('smoke','reporting'):
    samples += [json.loads(line) for line in (job/phase/'census.jsonl').read_text().splitlines()]
# First smoke attempt caught a transient launcher shell before any game and
# stopped. Preserve its raw census separately; only actual own workers are
# included in scheduling assertions.
rows=[r for s in samples for r in s['rows'] if r['own'] and not r['command'].startswith('bash -c ')]
assert max(s['combined'] for s in samples)<=60
assert all(r['nice']>=10 and r['scheduler']==5 for r in rows)
exits={p:json.loads((job/p/'exit.json').read_text()) for p in ('smoke','reporting')}
assert all(e['returncode']==0 and not e['stopping'] for e in exits.values())
result=dict(host='127x03',peak_combined=max(s['combined'] for s in samples),
    peak_own=max(sum(r['own'] and not r['command'].startswith('bash -c ') for r in s['rows']) for s in samples),
    census_samples=len(samples),all_sampled_own_workers_nice10_sched_idle=True,
    exits=exits,reporting_receipt=json.loads((job/'reporting/receipt.json').read_text()),
    smoke_receipt=json.loads((job/'smoke/receipt.json').read_text()),
    raw_root=str(job),cache_root=str(job/'cache'),setsid=True,no_leased_hosts=True,
    no_heavy_05=True,first_smoke_attempt=dict(games=0,reason='launcher shell classified as a worker; corrected'),
    limitations=['15-second process census; transient setup/read helpers can occur between samples',
                 'completed-game CPU excludes startup, builds, qualification and technical attempts'])
(job/'compute.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('peak_combined','peak_own','census_samples')}),flush=True)
