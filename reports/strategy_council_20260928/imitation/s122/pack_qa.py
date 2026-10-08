"""Publish the preselected QA inputs independently of production packing."""
import gzip,json,subprocess
from fetch_source import DATA,ROOT,sha,write
from pack_jobs import write_job,key
sample=json.loads((DATA/'qa/s122-sample.json').read_text());wanted={}
for r in sample['sample']:wanted.setdefault(r['shard'],{}).setdefault(r['match_index'],[]).append(r)
units=[]
for shard,indices in sorted(wanted.items()):
    for index,line in enumerate(gzip.open(DATA/f'payloads/shard-{shard:03d}.jsonl.gz')):
        if index not in indices:continue
        record=json.loads(line)
        for r in indices[index]:
            assert record['tag']==r['tag'];name=f"qa-{r['episode_id']}"
            units.append(write_job(DATA/f'inputs/qa-fast/{name}.json.gz',[{'item':r,'record':record}])|{'unit':name})
assert len(units)==400
write(DATA/'inputs/qa-fast-plan.json',{'units':units,'determinism_keys':sample['determinism_keys'],'qa_sample_sha256':sha(DATA/'qa/s122-sample.json')})
files=[u['file'] for u in units]+['inputs/qa-fast-plan.json','receipts/T9-PASS.json','receipts/T9-payloads.json','qa/s122-sample.json']
p=DATA/'receipts/qa-fast-files.txt';p.write_text('\n'.join(files)+'\n')
subprocess.run(['rsync','-c','--files-from='+str(p),str(DATA)+'/','127x01:'+str(DATA)+'/'],check=True)
print(json.dumps({'qa_inputs':400,'copied_to':'127x01'}),flush=True)
