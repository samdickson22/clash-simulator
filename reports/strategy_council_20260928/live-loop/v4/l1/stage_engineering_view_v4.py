"""Home01-only immutable-input hardlink view for an explicit engineering pilot.

No new media copies, no heldout payloads, no formal population admission.
Interrupted views are retained; every new run uses a fresh destination.
"""
import argparse
import json
import os
from pathlib import Path
import socket
from stage_training import FILES,HUB,sha
from formal_guard import SPLIT_SHA


def stage_view(hub,destination,expected,members):
    if not isinstance(expected,dict) or not expected:raise ValueError('Pinned engineering population required')
    destination.mkdir(exist_ok=False);frames=0
    for ep,digest in sorted(expected.items()):
        if not isinstance(ep,str) or not ep.startswith('v4-phase-a-') or '/' in ep:raise ValueError('Invalid episode')
        source=hub/ep
        if source.is_symlink():raise ValueError('Source episode must not be a symlink')
        if (source/'receipt.json').is_symlink() or sha(source/'receipt.json')!=digest:raise ValueError('Receipt changed or linked')
        r=json.loads((source/'receipt.json').read_text());m=members[r['seed']]
        if (r['episode']!=ep or ep!='v4-phase-a-'+str(r['seed']) or r['split'] not in ('train','validation')
                or (r['split'],r['decks'])!=(m['split'],m['decks'])):raise ValueError('Engineering train/validation admission failed')
        target=destination/ep;target.mkdir()
        for name in FILES:
            path=source/name
            if path.is_symlink() or sha(path)!=(digest if name=='receipt.json' else r['files'][name]):
                raise ValueError('Source checksum failed')
            os.link(path,target/name)  # Consumer only reads these immutable inputs.
        frames+=r['frames']
    result=dict(matches=len(expected),frames=frames,episodes=sorted(expected),receipt_sha256=expected,
        complete_population=False,engineering_only=True,heldout_payloads_opened=False,
        storage='hardlinks to receipt-pinned immutable hub train/validation files')
    with (destination/'stage-inventory.json').open('x') as f:json.dump(result,f,indent=2)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('destination','expected','split'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if socket.gethostname().split('.')[0]!='127x01':raise ValueError('Home01 only')
    if sha(a.split)!=SPLIT_SHA:raise ValueError('Frozen split changed')
    members={r['seed']:r for r in json.loads(a.split.read_text())['matches']}
    result=stage_view(Path(HUB),a.destination,json.loads(a.expected.read_text()),members)
    print(json.dumps({k:v for k,v in result.items() if k not in ('episodes','receipt_sha256')}),flush=True)
