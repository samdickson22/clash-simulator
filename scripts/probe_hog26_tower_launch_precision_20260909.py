"""Reproduce tower-launch rounding on CPU and MPS without changing physics."""

import argparse
import json
from pathlib import Path

import torch

from clasher.data import CardDataLoader
from clasher.rl.simple_pytorch_backend import (
 DEFAULT_SIMPLE_TOKEN_VOCABULARY,
 _typed_lookups,
 load_current_client_typed_vocabulary,
 load_simple_supported_decks,
)
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_standard import compile_standard_simple_setup

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    raise SystemExit('refusing to overwrite launch precision report')
torch.set_num_threads(1)
p=json.loads(Path('reports/hog26_procedural_outcome_protocol_reassessed_20260908.json').read_text())
a=load_simple_supported_decks(Path(p['procedural_decks']['path']))
base=['HogRider','IceGolem','Musketeer','Cannon','Skeletons','IceSpirit','Fireball','Log']
records=[]
for device in ['cpu','mps:0']:
 l=CardDataLoader(); s=compile_standard_simple_setup(l,a.public_cards,device=device,canonical_lane_globals=True)
 v=load_current_client_typed_vocabulary(DEFAULT_SIMPLE_TOKEN_VOCABULARY);e,h=_typed_lookups(s,l,v)
 r=s.create_runtime([[['Musketeer']+[x for x in base if x!='Musketeer'],base]],entity_token_lookup=e,hand_token_lookup=h,canonical_lane_globals=True,max_entities=64,max_effects=64,starting_elixir=10)
 for tick in range(120):
  act=torch.full((1,2),NO_OP_ACTION,dtype=torch.int64,device=device)
  if tick==0:act[0,0]=14*18+3
  result=r.step_tick(act)
  slots=torch.nonzero(r.effects.active[0]&(r.effects.source_card_id[0]==0)).flatten()
  if len(slots):
   k=int(slots[0]);f=r.effects
   rec={'device':device,'tick':tick+1,**{n:int(getattr(f,n)[0,k].cpu()) for n in ['source_x_units','source_y_units','target_x_units','target_y_units','x_units','y_units','speed_units_per_tick']}}
   dx=(f.target_x_units[0,k]-f.source_x_units[0,k]).float();dy=(f.target_y_units[0,k]-f.source_y_units[0,k]).float();dist=torch.sqrt(dx.square()+dy.square());offset=dy*300/dist.clamp_min(1)
   rec.update(distance=float(dist.cpu()),muzzle_y_offset_before_trunc=float(offset.cpu()),muzzle_y_offset_after_trunc=int(torch.trunc(offset).cpu()))
   records.append(rec);print(json.dumps(rec),flush=True);break
 else:raise RuntimeError('no tower shot')
args.output.write_text(json.dumps({'scope':'Diagnostic native launch geometry; source/target values are audit-only and never actor inputs.','records':records},indent=2)+'\n')
