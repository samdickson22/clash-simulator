"""Materialize fixed, small replay inputs to avoid re-reading an entire shard per unit."""
import gzip,json,os
from fetch_source import DATA,sha,write

def key(r):return r['tag']+'|'+r['side']
def write_job(path,items):
    content=json.dumps(items,sort_keys=True,separators=(',',':')).encode()
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        try: existing=gzip.decompress(path.read_bytes())
        except (EOFError, OSError):
            preserved=path.with_suffix(path.suffix+'.interrupted-r1')
            assert not preserved.exists()
            path.rename(preserved)
        else:
            assert existing==content
    if not path.exists():
        data=gzip.compress(content,compresslevel=1,mtime=0)
        tmp=path.with_suffix(path.suffix+'.writing')
        tmp.write_bytes(data);tmp.replace(path)
    return {'file':str(path.relative_to(DATA)),'sha256':sha(path),'perspectives':len(items),'keys':[key(i['item']) for i in items]}

def main():
    assert json.loads((DATA/'receipts/T9-PASS.json').read_text())['status']=='PASS'
    sample=json.loads((DATA/'qa/s122-sample.json').read_text()); qa={key(r):r for r in sample['sample']}
    qa_jobs=[];units=[]
    for shard in range(52):
        rows=[json.loads(l) for l in gzip.open(DATA/f'index/shards/shard-{shard:03d}.jsonl.gz')]
        bymatch={}
        for row in rows:bymatch.setdefault(row['match_index'],[]).append(row)
        items=[];part=0
        for index,line in enumerate(gzip.open(DATA/f'payloads/shard-{shard:03d}.jsonl.gz')):
            record=json.loads(line)
            for item in bymatch[index]:
                assert item['tag']==record['tag']
                pair={'item':item,'record':record}
                if key(item) in qa:
                    name=f"qa-{item['episode_id']}"
                    qa_jobs.append(write_job(DATA/f'inputs/qa/{name}.json.gz',[pair])|{'unit':name})
                items.append(pair)
                if len(items)==48:
                    name=f'shard-{shard:03d}-part-{part:03d}'
                    units.append(write_job(DATA/f'inputs/production/{name}.json.gz',items)|{'unit':name})
                    part+=1;items=[]
        if items:
            name=f'shard-{shard:03d}-part-{part:03d}'
            units.append(write_job(DATA/f'inputs/production/{name}.json.gz',items)|{'unit':name})
        print(json.dumps({'packed_shard':shard,'units':len(units)}),flush=True)
    assert len(qa_jobs)==400 and sum(u['perspectives'] for u in units)==json.loads((DATA/'receipts/T9-PASS.json').read_text())['perspectives']
    write(DATA/'inputs/qa-plan.json',{'units':qa_jobs,'determinism_keys':sample['determinism_keys'],'qa_sample_sha256':sha(DATA/'qa/s122-sample.json')})
    write(DATA/'inputs/production-plan.json',{'units':units,'partition_rule':'unit ordinal modulo 2; 0=127x03, 1=127x01','roles_sha256':sha(DATA/'roles/s122_roles_v2.json')})
if __name__=='__main__':main()
