"""Compact resumable status; no outcome peeking."""
import json,subprocess,sys
from pathlib import Path
job=Path(sys.argv[1]);p=json.loads((job/'progress.json').read_text())
counts={stage:len(list((job/'reporting'/stage/'games').glob('*.json'))) for stage in ('single','threaded')}
print(json.dumps(dict(at_utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),host=p['host'],terminal_reporting=sum(counts.values()),stage_counts=counts,active_arms=p['arms'],stage_target=p['target'],mem_GiB=round(p['memavailable_GiB'],1),paused=p['paused'],pid=p['pid'],pgid=p['pgid'],done=(job/'REPORTING-DONE').exists(),stage_exits={f.parent.name:json.loads(f.read_text())['returncode'] for f in (job/'reporting').glob('*/supervisor-exit.json')})))
