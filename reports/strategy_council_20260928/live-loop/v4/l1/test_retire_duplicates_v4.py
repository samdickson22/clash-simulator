"""Synthetic retirement preflight tests. Never invokes queue, worker or unlink."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from retire_duplicates_v4 import sha,target_plan


def main(root):
    root.mkdir();folder=root/'v4-phase-a-1';folder.mkdir()
    for name in ('raw.zst','pixels.zst'):(folder/name).write_bytes(name.encode())
    idx=dict(split='train',sha256={n:sha(folder/n) for n in ('raw.zst','pixels.zst')},
             equality={'pass':True,'checked':1,'mismatches':0})
    index=folder/'index.json';index.write_text(json.dumps(idx))
    pins={folder.name:sha(index)}
    evidence={folder.name:dict(index_sha256=sha(index),sha256=idx['sha256'],equality=idx['equality'],
                              sizes={n:(folder/n).stat().st_size for n in idx['sha256']})}
    checks=0
    def reject(fn):
        nonlocal checks
        try:fn()
        except (ValueError,FileNotFoundError):checks+=1
        else:raise AssertionError('Unsafe retirement preflight accepted')
    plan=target_plan(root,pins,evidence)
    assert len(plan)==2 and {r[1] for r in plan}=={'raw.zst','pixels.zst'};checks+=1
    (folder/'unique-extra.bin').write_bytes(b'keep')
    assert target_plan(root,pins,evidence)==plan;checks+=1
    reject(lambda:target_plan(root,{'../escape':next(iter(pins.values()))},evidence))
    bad=deepcopy(evidence);bad[folder.name]['sizes']['raw.zst']+=1
    reject(lambda:target_plan(root,pins,bad))
    bad=deepcopy(evidence);bad[folder.name]['equality']['checked']=2
    reject(lambda:target_plan(root,pins,bad))
    original=index.read_bytes();index.write_bytes(original+b' ')
    reject(lambda:target_plan(root,pins,evidence));index.write_bytes(original)
    payload=folder/'raw.zst';retained=folder/'saved-raw';payload.rename(retained);payload.symlink_to(retained)
    reject(lambda:target_plan(root,pins,evidence))
    assert retained.exists() and (folder/'pixels.zst').exists() and (folder/'unique-extra.bin').exists();checks+=1
    print(json.dumps(dict(checks=checks,passed=True,deleted=False,scope='synthetic planning only')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
