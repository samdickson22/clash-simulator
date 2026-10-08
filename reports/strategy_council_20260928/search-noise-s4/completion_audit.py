"""Independent post-barrier receipt and environment verification."""
from pathlib import Path
import hashlib,json,socket
from collections import Counter
HERE=Path(__file__).resolve().parent
assert socket.gethostname().split('.')[0]=='127x01'
result=json.loads((HERE/'result.json').read_text());manifest=hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest();assert result['manifest']==manifest
aggregate=hashlib.sha256();counts=Counter();scores=Counter();cpu=Counter();bounds=[]
for i,p in enumerate(sorted((HERE/'confirmation').glob('*.json'))):
 r=json.loads(p.read_text());assert r['job']==i and r['terminal'] and r['manifest']==manifest
 assert r['host']['nice']>=10 and r['host']['native_threads']==1
 assert r['host']['hostname'].split('.')[0] in ('127x04','127x08')
 counts[r['variant']]+=1;scores[r['variant']]+=r['score'];cpu[r['host']['hostname']]+=r['cpu_seconds'];bounds.append((r['started'],r['started']+r['elapsed']))
 aggregate.update(p.name.encode()+hashlib.sha256(p.read_bytes()).digest())
assert sum(counts.values())==1280 and set(counts.values())=={256}
assert aggregate.hexdigest()==result['receipt_aggregate']
for c,n in counts.items():assert scores[c]/n==result['scores'][c]['point']
audit=dict(games=sum(counts.values()),counts=counts,manifest=manifest,receipt_aggregate=aggregate.hexdigest(),all_nice_at_least_10=True,all_native_threads_one=True,game_cpu_hours_by_host={h:v/3600 for h,v in cpu.items()},wall_span_minutes=(max(b for a,b in bounds)-min(a for a,b in bounds))/60,outcome_barrier='All receipts, 152 partition successes, both supervisor successes checked by frozen analyzer before scores.')
(HERE/'completion-audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit))
