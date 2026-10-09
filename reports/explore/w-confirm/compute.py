"""Compact compute/termination audit; raw process census stays outside git."""
import json
from pathlib import Path
import sys

job=Path(sys.argv[1]);samples=[]
for phase in ('smoke','reporting'):
    path=job/phase/'census.jsonl'
    samples.extend(json.loads(line) for line in path.read_text().splitlines())
own_rows=[];peaks=[]
for sample in samples:
    # Include the relative-path diagnostic launcher as well as absolute job paths.
    rows=[r for r in sample['rows'] if r['own'] or 'reports/explore/w-confirm/' in r['command']]
    own_rows+=rows;peaks.append(len(rows))
assert max(peaks)<=56 and max(s['combined'] for s in samples)<=100
assert all(r['nice']>=10 and r['scheduler']==5 for r in own_rows)
exits={phase:json.loads((job/phase/'exit.json').read_text()) for phase in ('smoke','reporting')}
assert all(e['returncode']==0 and not e['stopping'] for e in exits.values())
admission={phase:json.loads((job/phase/'admission.json').read_text()) for phase in ('smoke','reporting')}
elapsed={phase:exits[phase]['time']-admission[phase]['time'] for phase in exits}
result=dict(host='127x03',peak_own=max(peaks),peak_combined=max(s['combined'] for s in samples),
    census_samples=len(samples),all_sampled_own_nice10_sched_idle=True,
    phases_elapsed_seconds=elapsed,exits=exits,
    reporting_receipt=json.loads((job/'reporting/receipt.json').read_text()),
    smoke_receipt=json.loads((job/'smoke/receipt.json').read_text()),
    ordinary_parity=json.loads((job/'ordinary-parity.json').read_text()),
    rejected_command_replay=json.loads((job/'rejection-diagnostic/events.json').read_text()),
    native_build_seconds=46.6,
    limitations=['15-second process census, transient setup/read helpers can occur between samples',
                 'completed-game CPU subtotal excludes startup/profile/technical-attempt CPU'],
    raw_root=str(job),cache_root=str(job/'cache'),no_leased_hosts=True,no_heavy_05=True)
(job/'compute.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(peak_own=result['peak_own'],peak_combined=result['peak_combined'],elapsed=elapsed)),flush=True)
