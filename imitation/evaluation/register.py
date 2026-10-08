"""Prepare prospective schedules and freeze only with a complete fleet audit.

No games are started here. The external audit must enumerate all schedule seeds,
all five authorized host inventories, source hashes and zero errors/overlaps.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
from .paths import setup, ROOT, COUNCIL, SNAPSHOT_ROOT
from .snapshot import provenance
setup()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def b_schedule():
    from decks import catalogs, family
    cats=catalogs()
    supported={tuple(sorted(d['cards'])) for d in cats['train']['decks']}
    held=[(role,d) for role in ('eval','eval_ood') for d in cats[role]['decks']
          if tuple(sorted(d['cards'])) in supported]
    families=['Hog 2.6','Hog EQ/Firecracker/MM','Royal Hogs/Furnace','X-Bow','bait','Goblinstein','AQ']
    rng=random.Random(2817590001)
    out=[]
    for mode, counts in [('head-to-head',[46,46,46,46,46,45,45]),('scripts',[19,19,18,18,18,18,18])]:
        for fam,count in zip(families,counts):
            pool=[(role,d) for role,d in held if family(d['cards'])==fam]
            if not pool: raise ValueError(f'empty family {fam}')
            for _ in range(count):
                role, own=rng.choices(pool,weights=[d['frequency'] for _,d in pool])[0]
                other=rng.choices(cats['train']['decks'],weights=[d['frequency'] for d in cats['train']['decks']])[0]
                decks=[list(own['cards']),list(other['cards'])]
                for deck in decks: rng.shuffle(deck)
                i=len(out)
                out.append(dict(pair=i, mode=mode, seed=2817600001+1009*i, role=role,
                                family=fam, decks=decks, style=('balanced','pressure','defense')[i%3]))
    return out


def c_schedule():
    from decks import catalogs
    cats=catalogs(); rng=random.Random(3217590001); out=[]
    for i in range(192):
        decks=[]
        for role in ('eval','train'):
            pool=cats[role]['decks']
            deck=list(rng.choices(pool,weights=[d['frequency'] for d in pool])[0]['cards'])
            rng.shuffle(deck); decks.append(deck)
        out.append(dict(pair=i,mode='scripts',seed=3217600001+1009*i,role='eval',
                        decks=decks,style=('balanced','pressure','defense')[i//64]))
    return out


def proposed_seeds(gate, schedule):
    seeds=set()
    if gate=='b':
        seeds.update((2817590001,2817590002))
        for row in schedule:
            s=row['seed']; seeds.update((s,s+100000,s+100001,s+100002))
    else:
        seeds.update((3217590001,3217590002))
        worlds=[row['seed'] for row in schedule]
        worlds += [base+1000003*(r*6+t+12)+1009*i for base in (2917600001,3017600001)
                   for r in range(2) for t in range(3) for i in range(16)]
        worlds += [3117600001+1009*i for i in range(128)]
        for s in worlds: seeds.update((s,s+7919,s+271828,s+271829,s+91117))
    return sorted(seeds)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--gate',choices=['b','c'],required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--checkpoint',type=Path)
    ap.add_argument('--checkpoint-sha256')
    ap.add_argument('--audit',type=Path)
    args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    schedule_path=args.output/'schedule.json'
    if schedule_path.exists():
        schedule=json.loads(schedule_path.read_text())['pairs']
    else:
        schedule=b_schedule() if args.gate=='b' else c_schedule()
        with open(schedule_path,'x') as f: json.dump({'gate':args.gate,'pairs':schedule},f,indent=2)
    seeds=proposed_seeds(args.gate,schedule)
    proposal=args.output/'proposed-seeds.json'
    if not proposal.exists():
        with open(proposal,'x') as f: json.dump(seeds,f,indent=2)
    if not args.audit:
        print('Schedule prepared; freeze requires --audit, --checkpoint and --checkpoint-sha256.'); return
    if not args.checkpoint or not args.checkpoint_sha256 or sha(args.checkpoint)!=args.checkpoint_sha256:
        raise ValueError('selected checkpoint hash mismatch or missing')
    audit=json.loads(args.audit.read_text())
    if not (audit.get('passed') and audit.get('complete_inventory') and not audit.get('errors')
            and not audit.get('overlap') and set(audit.get('hosts',[]))=={'127x01','127x03','127x04','127x05','127x08'}
            and set(seeds)<=set(audit.get('proposed',[])) and audit.get('files')):
        raise ValueError('fleet seed audit incomplete or failed')
    import torch
    ck=torch.load(args.checkpoint,map_location='cpu',weights_only=True)
    if ck.get('plumbing_only'):
        raise ValueError('synthetic checkpoint cannot freeze a gate')
    source_pin=provenance()
    if not source_pin['snapshot_tree_sha256']: raise ValueError('freeze requires isolated pinned snapshot')
    prereg=SNAPSHOT_ROOT/f'imitation/gate-{args.gate}/PREREG.md'
    text=prereg.read_text()
    frozen=args.output/'PREREG.frozen.md'
    if frozen.exists(): raise FileExistsError(frozen)
    text=text.replace('Checkpoint SHA256: **TBD**', 'Checkpoint SHA256: '+args.checkpoint_sha256)
    if args.checkpoint_sha256 not in text: raise ValueError('PREREG checkpoint hash differs')
    text += '\nConfirmation snapshot SHA256: '+source_pin['snapshot_tree_sha256']+'\n'
    frozen.write_text(text.replace('— DRAFT', '— FROZEN'))
    files=[*SNAPSHOT_ROOT.joinpath('imitation/evaluation').glob('*.py'), *SNAPSHOT_ROOT.joinpath('imitation/model').glob('*.py'),
           *COUNCIL.joinpath('imitation').glob('*.py'), *ROOT.joinpath('src/clasher').rglob('*.py'),
           *ROOT.joinpath('engine-rs').glob('*.py'), *ROOT.joinpath('engine-rs').glob('*.so'),
           *COUNCIL.joinpath('engine-speed/stage5').glob('*.py'),
           COUNCIL/'engine-speed/stage5b-r3/deadline_player.py', ROOT/'gamedata.json',
           COUNCIL/'c56/engine/root-v3/human_deck_catalog.json',
           COUNCIL/'c56/data/roles/c56_roles_v1.json',COUNCIL/'c56/data/index/perspectives.jsonl.gz',
           *COUNCIL.joinpath('m0/data/roles_v2').glob('*.json'), COUNCIL/'pilot/hog26-deployment.json',
           SNAPSHOT_ROOT/'snapshot-manifest.json',prereg,frozen,args.audit,proposal,schedule_path,args.checkpoint]
    if args.gate=='c':
        from .run_p16 import S2902,NATURAL
        files += [S2902,NATURAL,COUNCIL/'human-prior-p16/scripts/run_eval.py']
    manifest=dict(**source_pin,gate=args.gate,checkpoint=str(args.checkpoint.resolve()),checkpoint_sha256=args.checkpoint_sha256,
                  files={str(p.resolve()):sha(p) for p in sorted(set(files))},schedule=str(schedule_path.resolve()),
                  seed_audit_sha256=sha(args.audit),plumbing_only=False)
    with open(args.output/'manifest.json','x') as f: json.dump(manifest,f,indent=2)
    print('Frozen manifest:',args.output/'manifest.json')


if __name__=='__main__': main()
