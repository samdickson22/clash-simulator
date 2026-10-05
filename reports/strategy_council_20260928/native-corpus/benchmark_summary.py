import collections,json,statistics
from study import OUT,dump
rs=[json.loads(l) for l in open(OUT/'benchmark.jsonl')];groups=collections.defaultdict(list)
for r in rs:groups[(r['session'],r['rich'],r['cadence'])].append(r)
out=[]
for (session,rich,cadence),rows in sorted(groups.items()):
 total=sum(r['total_s'] for r in rows);ticks=sum(r['last_tick'] for r in rows);normalized=total*6000/ticks
 out.append({'session':session,'rich':rich,'cadence':cadence,'n':len(rows),'mean_s':total/len(rows),'matches_per_hour':3600*len(rows)/total,'six_thousand_tick_seconds':normalized,'six_thousand_tick_matches_per_hour':3600/normalized,'days_252k':{str(n):252000*normalized/86400/n for n in [1,2,4,8]},'mean_gzip_bytes':statistics.mean(r['gzip_bytes'] for r in rows),'gzip_252k_gib':statistics.mean(r['gzip_bytes'] for r in rows)*252000/2**30,'observe_ms':1000*sum(r['observe_s'] for r in rows)/sum(r['observations'] for r in rows),'step_ms':1000*sum(r['step_s'] for r in rows)/sum(r['observations'] for r in rows)})
byid=collections.defaultdict(list)
for r in rs:byid[r['index']].append(r['final'])
summary={'groups':out,'transport_cadence_final_identity':{str(k):all(v==vals[0] for v in vals) for k,vals in byid.items()},'note':'Two early-ending synthetic reconstructions, not valid full human replays. Normalization assumes linear cost in ticks and unchanged board/event density. Rich writes full cumulative telemetry gzip; public-field-only output has its own benchmark.'}
dump('benchmark-summary.json',summary);print(json.dumps(summary,indent=2))
