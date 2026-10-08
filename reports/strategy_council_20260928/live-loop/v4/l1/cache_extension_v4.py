"""Plan receipt-pinned new shards beyond an already verified cache snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
from formal_guard import SPLIT_SHA


def extension(current, base, previous, previous_sha):
    def inventory(value):
        eps=value['episodes'];receipts=value['receipt_sha256']
        if (value.get('heldout_payloads_opened') is not False or len(eps)!=len(set(eps))
                or set(eps)!=set(receipts) or value['matches']!=len(eps)
                or any(not ep.startswith('v4-phase-a-') or '/' in ep for ep in eps)):
            raise ValueError('Invalid train/validation stage inventory')
        return receipts
    now,old=inventory(current),inventory(previous)
    if (base.get('complete_for_snapshot') is not True or base.get('formal_population_seal') is not False
            or base.get('heldout_payloads_opened') is not False or base.get('split_sha256')!=SPLIT_SHA
            or base.get('source_snapshot_sha256')!=previous_sha or base.get('matches')!=len(old)
            or set(base.get('index_sha256',{}))!=set(old) or base.get('files_verified')!=2*len(old)
            or base.get('equality_mismatches')!=0 or base.get('equality_checked',0)<1):
        raise ValueError('Verified base snapshot evidence required')
    if any(now.get(ep)!=digest for ep,digest in old.items()):
        raise ValueError('Base receipts missing or changed in current population')
    added={ep:digest for ep,digest in now.items() if ep not in old}
    return dict(matches=len(added),episodes=sorted(added),receipt_sha256=added,
                heldout_payloads_opened=False,complete_population=False,
                base_matches=len(old),current_matches=len(now),
                scope='new shards only; full training reader/union verification required')


def disjoint_extension(current, bases):
    seen=set();pins={}
    for manifest,inventory,digest in bases:
        extension(current,manifest,inventory,digest)
        if seen.intersection(inventory['episodes']):raise ValueError('Overlapping verified base shards')
        seen.update(inventory['episodes']);pins.update(inventory['receipt_sha256'])
    if not bases:raise ValueError('Verified base required')
    added={e:d for e,d in current['receipt_sha256'].items() if e not in seen}
    return dict(matches=len(added),episodes=sorted(added),receipt_sha256=added,
                heldout_payloads_opened=False,complete_population=False,
                base_matches=len(seen),current_matches=current['matches'],
                scope='new shards only; full training reader/union verification required')


def main():
    p=argparse.ArgumentParser()
    for name in ('current','base-manifest','base-inventory','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--extra-base',nargs=2,type=Path,action='append',default=[],metavar=('MANIFEST','INVENTORY'))
    a=p.parse_args()
    data=[p.read_bytes() for p in (a.current,a.base_manifest,a.base_inventory)]
    current,base,previous=[json.loads(v) for v in data]
    bases=[(base,previous,hashlib.sha256(data[2]).hexdigest())]
    for manifest,inventory in a.extra_base:
        bases.append((json.loads(manifest.read_text()),json.loads(inventory.read_text()),hashlib.sha256(inventory.read_bytes()).hexdigest()))
    result=disjoint_extension(current,bases)
    result['input_sha256']={str(p):hashlib.sha256(v).hexdigest() for p,v in zip((a.current,a.base_manifest,a.base_inventory),data)}
    result['input_sha256'].update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for pair in a.extra_base for p in pair})
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('episodes','receipt_sha256','input_sha256')}),flush=True)


if __name__=='__main__':main()
