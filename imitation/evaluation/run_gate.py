"""Resume immutable, frozen gate schedules; each process handles owned jobs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from .paths import ROOT


def verify(manifest):
    from .register import sha
    for path, digest in manifest['files'].items():
        if sha(path)!=digest:
            raise ValueError(f'pinned file changed: {path}')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--worker',type=int,default=0)
    ap.add_argument('--workers',type=int,default=1)
    ap.add_argument('--section',choices=['all','search','p16','h2h','c56'],default='all')
    args=ap.parse_args()
    if not 0<=args.worker<args.workers: raise ValueError('invalid worker')
    manifest=json.loads(args.manifest.read_text()); verify(manifest)
    manifest_hash=hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    output=args.manifest.parent/'games';output.mkdir(exist_ok=True)
    gate=manifest['gate'];checkpoint=manifest['checkpoint']
    if gate=='c' and args.section in ('all','p16','h2h'):
        from .run_p16 import S2902,NATURAL
        jobs=[]
        if args.section in ('all','p16'):
            for block,seed in enumerate((2917600001,3017600001)):
                for name,ck,legacy in [('v1',checkpoint,False),('s2902',S2902,True),('natural',NATURAL,True)]:
                    for cell in range(6):
                        jobs.append(['--checkpoint',str(ck),'--output',str(output/f'p16-{block}-{name}'),
                                     '--seed',str(seed),'--cell',str(cell),*(['--legacy'] if legacy else [])])
        if args.section in ('all','h2h'):
            for cell in (0,3):
                jobs.append(['--checkpoint',checkpoint,'--output',str(output/'h2h'),
                             '--seed','3117600001','--games','128','--cell',str(cell),'--head-to-head'])
        for i,job in enumerate(jobs):
            if i%args.workers != args.worker: continue
            verify(manifest)
            subprocess.run([sys.executable,'-m','imitation.evaluation.run_p16',*job],check=True,cwd=ROOT)
    if gate=='b' or args.section in ('all','c56'):
        import torch
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        from .smoke import play,write_new
        from .paths import COUNCIL
        from fair_player import Resources
        from imitation.model import load_policy
        r=Resources();policy=load_policy(checkpoint)
        prior=json.loads((COUNCIL/'c56/engine/root-v3/human_deck_catalog.json').read_text())
        schedule=json.loads(Path(manifest['schedule']).read_text())['pairs']
        for ep in schedule:
            if ep['pair']%args.workers!=args.worker: continue
            for arm in (('B','A') if gate=='b' and ep['mode']=='scripts' else ('B',)):
                for seat in (0,1):
                    path=output/f"pair-{ep['pair']:03d}-{arm}-{seat}.json"
                    if path.exists():
                        saved=json.loads(path.read_text())
                        if saved['manifest_sha256']!=manifest_hash or not saved['terminal']:
                            raise ValueError('resume receipt invalid')
                        continue
                    verify(manifest)
                    world=dict(ep)
                    if ep['mode']=='scripts' and seat: world['decks']=list(reversed(ep['decks']))
                    row=play(r,prior,policy,world,seat,search=gate=='b',arm=arm,
                             head_to_head=ep['mode']=='head-to-head',plumbing_only=False)
                    row.update(pair=ep['pair'],mode=ep['mode'],manifest_sha256=manifest_hash)
                    write_new(path,row)
                    print(json.dumps({'pair':ep['pair'],'arm':arm,'seat':seat,'terminal':row['terminal']}),flush=True)
    verify(manifest)
    done=output/f'worker-{args.section}-{args.worker}-done.json'
    if not done.exists():
        with open(done,'x') as f: json.dump({'complete':True,'manifest_sha256':manifest_hash},f)


if __name__=='__main__': main()
