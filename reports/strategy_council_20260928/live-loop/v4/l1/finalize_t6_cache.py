"""Move a completed owned T6 corpus under the cache budget, retaining its alias.

No deletion, conversion, training or heldout payload access. Invoke on15 through
the lease wrapper after the converter's authenticated zero-exit receipt exists.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket

from cache_budget import require_growth, used_bytes, validate_root


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    for name in ('dataset','exit-receipt','destination','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    lease=Path('/mpac/sdicks02/repos/clasher-lease')
    if socket.gethostname().split('.')[0]!='127x15' or os.environ.get('CLASHER_LEASE_ROOT')!=str(lease):
        raise ValueError('15 lease wrapper required')
    root=validate_root(lease/'data/v4-cache')
    if (a.dataset.parent!=lease/'data' or a.dataset.is_symlink()
            or not a.dataset.name.startswith('v4-final-preparation-')
            or a.destination.parent!=root or a.destination.exists() or a.destination.is_symlink()
            or a.output.parent!=lease/'jobs' or a.output.exists()
            or a.exit_receipt.parent!=lease/'jobs'):
        raise ValueError('Fresh explicit owned corpus/cache/receipt paths required')
    receipt=read(a.exit_receipt)
    if (receipt.get('host')!='127x15' or receipt.get('exit_code')!=0
            or receipt.get('status')!='pass' or str(a.dataset) not in receipt.get('command',[])
            or not any(str(p).endswith('/prepare_t6.py') for p in receipt.get('command',[]))):
        raise ValueError('Successful converter exit receipt required')
    for key in ('pid','supervisor_pid'):
        pid=receipt[key]
        if type(pid) is not int or Path(f'/proc/{pid}').exists():
            raise ValueError('Converter or supervisor still present; retry after verified exit')
    inventory=read(a.dataset/'inventory.json')
    complete=read(a.dataset/'complete.json')
    counts={s:sum(r['split']==s for r in inventory) for s in ('train','validation')}
    if (not all(counts.values()) or sum(counts.values())!=len(inventory)
            or complete!=dict(matches=len(inventory),splits=counts,heldout_opened=False)
            or len({r['episode'] for r in inventory})!=len(inventory)):
        raise ValueError('Complete unique train/validation corpus required')
    for row in inventory:
        if sha(Path(row['path'])/'receipt.json')!=row['receipt_sha256']:
            raise ValueError('Source receipt changed')
        if read(a.dataset/'per-match'/row['episode']/'roundtrip.json').get('passed') is not True:
            raise ValueError('Per-match conversion verification failed')
    links=[p for p in a.dataset.rglob('*') if p.is_symlink()]
    if any(not p.resolve(strict=True).is_relative_to(a.dataset) for p in links):
        raise ValueError('Unexpected alias outside completed corpus')
    source_bytes=used_bytes(a.dataset)
    pins={name:sha(a.dataset/name) for name in ('inventory.json','manifest.json','complete.json')}
    with (root/'.writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Reserve future formal JPEG cache and its working-space allowance now.
        require_growth(root,source_bytes+4096*2**20+2_000_000_000)
        os.rename(a.dataset,a.destination)
        try:
            a.dataset.symlink_to(a.destination,target_is_directory=True)
        except BaseException:
            os.rename(a.destination,a.dataset)
            raise
        # Absolute converter aliases resolve through the retained original path.
        moved_links=[a.destination/p.relative_to(a.dataset) for p in links]
        if any(not p.resolve(strict=True).is_relative_to(a.destination) for p in moved_links):
            raise ValueError('Moved alias failed validation; preserve corpus and investigate')
        if any(sha(a.destination/name)!=digest for name,digest in pins.items()):
            raise ValueError('Corpus metadata changed during relocation')
        result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_alias=str(a.dataset),destination=str(a.destination),matches=len(inventory),splits=counts,
            metadata_sha256=pins,converter_exit_sha256=sha(a.exit_receipt),
            conservative_corpus_bytes=source_bytes,cache_root_bytes=used_bytes(root),
            reserved_future_growth_bytes=4096*2**20+2_000_000_000,
            checked_internal_aliases=len(links),deleted=False,heldout_payloads_opened=False)
        with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
