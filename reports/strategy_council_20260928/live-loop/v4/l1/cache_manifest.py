"""Verify the complete train/validation cache for an explicit staged snapshot."""
import argparse
import datetime
import json
from pathlib import Path
from cache_budget import validate_root, require_growth, used_bytes
from pixel_cache import PixelCache, sha


def main():
    p=argparse.ArgumentParser()
    for name in ('source','cache','inventory','split','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();validate_root(a.cache);require_growth(a.cache,0)
    if sha(a.split)!='3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258':raise ValueError('Frozen split changed')
    members={r['seed']:r for r in json.loads(a.split.read_text())['matches']}
    inventory=json.loads(a.inventory.read_text());rows=[]
    if set(inventory['episodes'])!=set(inventory['receipt_sha256']):raise ValueError('Incomplete snapshot inventory')
    for ep,digest in inventory['receipt_sha256'].items():
        if '/' in ep or not ep.startswith('v4-phase-a-'):raise ValueError('Invalid episode')
        path=a.source/ep/'receipt.json'
        if sha(path)!=digest:raise ValueError('Snapshot receipt changed')
        r=json.loads(path.read_text());m=members[r['seed']]
        if r['split'] not in ('train','validation') or (r['split'],r['decks'])!=(m['split'],m['decks']):raise ValueError('Train/validation admission failed')
        rows.append(dict(r,receipt_sha256=digest))
    cache=PixelCache(a.cache,rows)  # Full SHA256 verification, no source media decode.
    result=dict(complete_for_snapshot=True,formal_population_seal=False,
        source_snapshot_sha256=sha(a.inventory),split_sha256=sha(a.split),
        matches=len(rows),splits={s:sum(r['split']==s for r in rows) for s in ('train','validation')},
        frames=sum(r['frames'] for r in rows),cache=str(a.cache),
        payload_bytes=sum(i['bytes'] for i in cache.index.values()),bytes_on_host=used_bytes(a.cache),
        equality_checked=sum(i['equality']['checked'] for i in cache.index.values()),
        equality_mismatches=sum(i['equality']['mismatches'] for i in cache.index.values()),
        files_verified=2*len(rows),index_sha256={ep:sha(a.cache/ep/'index.json') for ep in cache.index},
        heldout_payloads_opened=False,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='index_sha256'}),flush=True)


if __name__=='__main__':main()
