"""Prove frozen no-live-import gates have identical inputs after adapter repair."""
import hashlib,json,sys,types
from pathlib import Path
from c56_gate import ROOT,FOLDER,PLAN,CARDS,battle,config,resources,fingerprint
from differential import snapshot
import live_snapshot

folder=FOLDER
card=json.loads((folder/'card_kernel_r64_manifest.json').read_text())
current=Path('engine-rs/live_snapshot.py').read_text()
added='''    if (
        type(e).__name__ == "AreaEffect"
        and out["scope"] is None
        and s is not None
        and str(s.card_type).lower() != "spell"
    ):
        # Character death payload labels (e.g. FreezeIceGolemite) identify
        # their source, not a card in the playable-spell configuration.
        out["spell_name"] = ""
'''
assert current.count(added)==1
prior=current.replace(added,'',1)
assert hashlib.sha256(prior.encode()).hexdigest()==card['hashes']['engine-rs/live_snapshot.py']
paths=[*[p for p in ROOT.joinpath('src/clasher').rglob('*.py') if p.relative_to(ROOT/'src/clasher').parts[0]!='vision'],*ROOT.joinpath('engine-rs/src').glob('*.rs'),*ROOT.joinpath('engine-rs').glob('*.py'),ROOT/'engine-rs/clasher_core.abi3.so']
previous_bytes=[]
for p in sorted(paths):
 name=str(p.relative_to(ROOT))
 if name=='engine-rs/test_stage4_imports.py':continue
 previous_bytes.extend([name.encode(),prior.encode() if name=='engine-rs/live_snapshot.py' else p.read_bytes()])
old_fp=hashlib.sha256((ROOT/'gamedata.json').read_bytes()+b''.join(previous_bytes)).hexdigest()
receipts={name:folder/(name+'_r65.json') for name in ('controller_roots','c56_games','c56_placements')}
for name,path in receipts.items():
 data=json.loads(path.read_text());assert data['fingerprint']==old_fp,name
 assert all(r['ok'] for r in data['results'].values())
assert len(json.loads(receipts['c56_games'].read_text())['results'])==64
assert len(json.loads(receipts['c56_placements'].read_text())['results'])==14
old_module=types.ModuleType('live_snapshot')
exec(compile(prior,'<frozen-live-snapshot-before-area-repair>','exec'),old_module.__dict__)
new_module=live_snapshot
builder,_,_,_=resources();cfg=config(CARDS)
roots=[]
for index,ep in enumerate(json.loads(PLAN.read_text())['episodes']):roots.append((f'game-{index}',battle(ep,builder.loader)))
for index in range(14):
 deck=list(CARDS[index*4:index*4+4])+list(CARDS[((index+1)%14)*4:((index+1)%14)*4+4])
 b=battle(dict(seed=630056+index,decks=[deck,deck]),builder.loader)
 for p in b.players:p.elixir=10
 roots.append((f'fresh-{index}',b))
hashes={}
try:
 for name,b in roots:
  assert all(type(e).__name__!='AreaEffect' for e in b.entities.values())
  sys.modules['live_snapshot']=old_module;old=snapshot(b,cfg)
  sys.modules['live_snapshot']=new_module;new=snapshot(b,cfg)
  assert old==new,name
  hashes[name]=hashlib.sha256(new.encode()).hexdigest()
finally:sys.modules['live_snapshot']=new_module
assert (folder/'character_area_r65b.exit').read_text().strip()=='0'
out=dict(status='adapter-only requalification; frozen simulation/controller/fresh-placement inputs proven byte-identical',old_fingerprint=old_fp,new_fingerprint=fingerprint(),changed_code=['engine-rs/live_snapshot.py'],added_test='engine-rs/test_stage4_imports.py',old_exporter_sha256=hashlib.sha256(prior.encode()).hexdigest(),new_exporter_sha256=hashlib.sha256(current.encode()).hexdigest(),proof_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),native_binary_sha256=hashlib.sha256((ROOT/'engine-rs/clasher_core.abi3.so').read_bytes()).hexdigest(),frozen_receipts={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in receipts.values()},identical_initial_states=hashes)
(folder/'area_adapter_requalification.json').write_text(json.dumps(out,indent=2)+'\n')
print({k:v for k,v in out.items() if k not in ('frozen_receipts','identical_initial_states')})
print('PASS',len(hashes),'byte-identical initial native states; full old fingerprint reconstructed exactly')
