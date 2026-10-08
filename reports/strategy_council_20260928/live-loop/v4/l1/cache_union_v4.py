"""Exact train/validation cache union; no formal admission or heldout authority.

All shard metadata is checked before opening any payload or remote connection.
The caller supplies the entire admitted snapshot, never a convenient subset.
"""
from contextlib import ExitStack
import fcntl
import json
import math
from pathlib import Path

from formal_guard import SPLIT_SHA
from pixel_cache import sha


def partition(receipts, shards):
    rows=list(receipts);expected={r['episode']:r for r in rows}
    if not rows or len(rows)!=len(expected) or not shards:
        raise ValueError('Nonempty unique complete snapshot required')
    for ep,r in expected.items():
        if ('/' in ep or not ep.startswith('v4-phase-a-') or r['split'] not in ('train','validation')
                or type(r['frames']) is not int or r['frames']<1):
            raise ValueError('Only admitted train/validation frames allowed')
    seen=set();groups=[]
    for shard in shards:
        inv,m=shard['inventory'],shard['manifest']
        episodes=inv['episodes'];pins=inv['receipt_sha256'];eps=set(episodes)
        if (len(episodes)!=len(eps) or not eps or eps!=set(pins) or inv['matches']!=len(eps)
                or inv.get('heldout_payloads_opened') is not False
                or eps&seen or not eps<=set(expected)):
            raise ValueError('Shard is empty, overlapping, outside snapshot or invalid')
        if any(pins[e]!=expected[e]['receipt_sha256'] for e in eps):
            raise ValueError('Shard receipt changed')
        group=[expected[e] for e in sorted(eps)]
        counts={s:sum(r['split']==s for r in group) for s in ('train','validation')}
        if (m.get('complete_for_snapshot') is not True or m.get('heldout_payloads_opened') is not False
                or m.get('split_sha256')!=SPLIT_SHA or m.get('source_snapshot_sha256')!=shard['inventory_sha256']
                or set(m.get('index_sha256',{}))!=eps or m.get('matches')!=len(eps)
                or m.get('files_verified')!=2*len(eps) or m.get('equality_mismatches')!=0
                or m.get('equality_checked',0)<sum(math.ceil(.01*r['frames']) for r in group)
                or m.get('frames')!=sum(r['frames'] for r in group) or m.get('splits')!=counts):
            raise ValueError('Shard verification evidence does not match snapshot')
        if any(not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v)
               for v in m['index_sha256'].values()):raise ValueError('Invalid index SHA256')
        groups.append(group);seen.update(eps)
    if seen!=set(expected):raise ValueError('Incomplete cache union')
    return groups


class UnionPixelCache:
    def __init__(self, receipts, shards):
        """shards: inventory/manifest paths plus local cache or remote ready/token/endpoint.

        The union remains tied to these exact files and source receipt hashes.
        Use as a context manager, or close explicitly, to release local read locks.
        """
        from cache_budget import validate_root
        from cache_transport_v4 import RangeStore,RemotePixelCache
        self._resources=ExitStack();self.index={};self.readers={};self.provenance=[]
        evidence=[]
        # Decode and validate the entire metadata plan before any payload read.
        for shard in shards:
            inv=Path(shard['inventory']);manifest=Path(shard['manifest'])
            evidence.append(dict(inventory=json.loads(inv.read_text()),manifest=json.loads(manifest.read_text()),
                inventory_sha256=sha(inv),manifest_sha256=sha(manifest)))
            if shard['kind'] not in ('local','remote'):raise ValueError('Unknown shard kind')
        groups=partition(receipts,evidence)
        try:
            for shard,e,rows in zip(shards,evidence,groups):
                pins=e['manifest']['index_sha256']
                if shard['kind']=='local':
                    root=Path(shard['cache']);validate_root(root)
                    lock=self._resources.enter_context((root/'.writer.lock').open('a'))
                    fcntl.flock(lock,fcntl.LOCK_SH|fcntl.LOCK_NB)
                    reader=RangeStore(root,rows,pins).cache
                else:
                    ready=json.loads(Path(shard['ready']).read_text())
                    if (ready.get('payloads_verified') is not True or ready.get('heldout_payloads_opened') is not False
                            or ready.get('manifest_sha256')!=e['manifest_sha256']
                            or ready.get('inventory_sha256')!=e['inventory_sha256']
                            or ready.get('index_sha256')!=pins):raise ValueError('Unpinned remote service')
                    token=Path(shard['token_file'])
                    if token.stat().st_mode&0o077:raise ValueError('Private token required')
                    reader=RemotePixelCache(shard['endpoint'],token.read_text().strip(),rows,pins)
                self.index.update(reader.index)
                self.readers.update({r['episode']:reader for r in rows})
                # Stable provenance excludes private tokens and transient tunnel ports.
                self.provenance.append(dict(manifest_sha256=e['manifest_sha256'],
                    inventory_sha256=e['inventory_sha256'],index_sha256=pins))
        except BaseException:
            self.close();raise

    def get(self,episode,indices,raw=False):
        if episode not in self.readers:raise ValueError('Episode outside complete admitted union')
        return self.readers[episode].get(episode,indices,raw=raw)

    def close(self):self._resources.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
