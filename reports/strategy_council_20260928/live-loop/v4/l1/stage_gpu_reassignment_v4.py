"""Pinned preformal staging on 09/15, inside their reclaim-aware wrappers.

09 receives the 71-match unique shard from16 (one nice sender, no source writes).
15 receives complete T6 conversion inputs; its 10GB reservation covers the
unchanged T6 bounded JPEG cache. No GPU fitting or heldout payload access.
"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys

from pixel_cache import sha
from cache_budget import validate_root


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--label',required=True);p.add_argument('--admitted',type=Path,required=True)
    p.add_argument('--source-only',action='store_true',help='Extend input staging without recopying the existing immutable cache shard')
    a=p.parse_args();host=socket.gethostname().split('.')[0]
    if host not in ('127x09','127x15'):raise ValueError('Reassigned GPU host required')
    if not a.label or not all(c.isalnum() or c in '-_.' for c in a.label):raise ValueError('Invalid label')
    code=Path(__file__).resolve().parent;root=Path('/mpac/sdicks02/repos/clasher-lease')
    source=root/'data/v4-matches';cache=validate_root(root/'data/v4-cache');jobs=root/'jobs'
    current=json.loads(a.admitted.read_text())
    if (current.get('heldout_payloads_opened') is not False or current.get('complete_population') is not False
            or set(current['episodes'])!=set(current['receipt_sha256']) or not current['episodes']):
        raise ValueError('Pinned preformal train/validation inventory required')
    def run(name,*args):subprocess.run([sys.executable,'-B',str(code/name),*map(str,args)],check=True)
    run('stage_training.py','--destination',source,'--split',code.parent/'split.json',
        *(['--all-training-payloads'] if host=='127x15' else []),'--episodes',*current['episodes'])
    actual=json.loads((source/'stage-inventory.json').read_text())
    if actual['receipt_sha256']!=current['receipt_sha256']:raise ValueError('Staged snapshot differs')
    with (jobs/(a.label+'-stage.json')).open('x') as f:json.dump(actual,f,indent=2)
    result=dict(host=host,matches=current['matches'],admitted_sha256=sha(a.admitted),
        staged_inventory_sha256=sha(source/'stage-inventory.json'),formal_population_seal=False,
        heldout_payloads_opened=False,training_started=False)
    if host=='127x09' and not a.source_only:
        evidence=code/'receipts/preformal-cache-20261008'
        inventory=evidence/'v4-cache-unique-20261008-16r4-plan.json'
        original=evidence/'v4-cache-unique-20261008-16r4-manifest.json'
        inv=json.loads(inventory.read_text());old=json.loads(original.read_text())
        if old['source_snapshot_sha256']!=sha(inventory):raise ValueError('Source cache manifest unpinned')
        if any(current['receipt_sha256'].get(ep)!=digest for ep,digest in inv['receipt_sha256'].items()):
            raise ValueError('Source shard differs from admitted population')
        run('sync_pixel_cache.py','--from-host','127x16','--remote-cache',root/'data/v4-cache',
            '--cache',cache,'--source',source,'--split',code.parent/'split.json',
            '--receipt',jobs/(a.label+'-copy.json'),'--episodes',*inv['episodes'])
        manifest=jobs/(a.label+'-manifest.json')
        run('cache_manifest.py','--source',source,'--cache',cache,'--split',code.parent/'split.json',
            '--inventory',inventory,'--output',manifest)
        new=json.loads(manifest.read_text())
        for key in ('index_sha256','payload_bytes','equality_checked','equality_mismatches','frames','matches'):
            if old[key]!=new[key]:raise ValueError('Destination cache differs: '+key)
        result.update(cache_manifest_sha256=sha(manifest),copied_cache_matches=new['matches'],
            copied_cache_bytes=new['payload_bytes'],source_cache_retained=True)
    with (jobs/(a.label+'-complete.json')).open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
