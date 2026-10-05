import collections,gzip,json,time
from study import OUT,run_one
rows=[json.loads(l) for l in gzip.open(OUT/'sample50.jsonl.gz','rt')]
# Paired three-minute and overtime reconstructions; all action/outcome limits apply.
chosen=[rows[0],rows[19]]
with (OUT/'benchmark.jsonl').open('w') as f:
 for session in [True,False]:
  for rich in [False,True]:
   for cadence in [20,5]:
    for row in chosen:
     label=f'bench-{int(session)}-{int(rich)}-{cadence}'
     r=run_one(row,cadence=cadence,rich=rich,session=session,prefix=label,save_frames=True)
     path=OUT/f'{label}-{row["index"]}-frames.jsonl.gz';r['gzip_bytes']=path.stat().st_size if path.exists() else None
     # Retain timing/outcomes/actions but avoid repeating large initial packets.
     for k in ['initial_rich_towers','initial_rich_players','initial_observe']:r.pop(k,None)
     f.write(json.dumps(r)+'\n');f.flush()
     print(label,row['index'],r.get('failure'),r.get('total_s'),r.get('observations'),r.get('gzip_bytes'),flush=True)
