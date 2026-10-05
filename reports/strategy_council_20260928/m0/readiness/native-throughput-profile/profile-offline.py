from pathlib import Path
import gzip,hashlib,json,statistics,sys,time
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'scripts'))
import run_readiness_v2 as runner
base=ROOT/'reports/strategy_council_20260928/m0/readiness'
plan=json.loads((base/'paired-repetition-run-v6/execution-plan.json').read_text())
_,builder,adapter,maps=runner.components(Path(plan['captures'][0]['capture_path']),Path(plan['catalog_path']),plan['catalog_sha256'])
source=base/'paired-repetition-run-v6/job-00002/decisions.jsonl.gz'
fields=('ok','schema','truncated','tick','generation','stateEpoch','count','returned','objects')
results=[]
with gzip.open(source,'rt') as stream:
 for index,line in enumerate(stream):
  if index not in {0,300,600}:continue
  start=time.perf_counter();row=json.loads(line);parse_seconds=time.perf_counter()-start
  frame=row['native_frame'];rich=frame['rich']
  minimal_rich={key:rich[key] for key in fields}
  minimal_frame={**frame,'rich':minimal_rich}
  full_views=runner.public_views(frame,adapter,maps,[None,None])
  minimal_views=runner.public_views(minimal_frame,adapter,maps,[None,None])
  equal=[runner.packet_sha(a)==runner.packet_sha(b) for a,b in zip(full_views,minimal_views)]
  assert all(equal)
  timings=[]
  for name,variant in [('full',row),('projection_fields',{**row,'native_frame':minimal_frame})]:
   start=time.perf_counter();encoded=json.dumps(variant,separators=(',',':')).encode();encode_seconds=time.perf_counter()-start
   for level in [1,9]:
    start=time.perf_counter();compressed=gzip.compress(encoded,compresslevel=level);seconds=time.perf_counter()-start
    assert gzip.decompress(compressed)==encoded
    timings.append({'variant':name,'gzip_level':level,'json_bytes':len(encoded),'gzip_bytes':len(compressed),'encode_seconds':encode_seconds,'gzip_seconds':seconds})
  results.append({'frame':index,'tick':row['tick'],'parse_seconds':parse_seconds,'public_packets_equal_with_same_history':equal,'timings':timings})
  if index==600:break
out={'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'results':results,'scope':'Offline saved-frame diagnostics. No native calls or production runner changes. Projection equality uses the same empty own-history input for both variants, not a claim of equality to archived history-dependent packet hashes.'}
with (base/'native-throughput-profile/offline-cost.json').open('x') as stream:json.dump(out,stream,indent=2)
for result in results:print(result)
