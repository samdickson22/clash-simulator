import json
from pathlib import Path
import numpy as np
import torch
from scripts.evaluate_hog26_simple_policy import load_model
from scripts.collect_hog26_complete_outcomes import install_seeded_deals
from clasher.rl.simple_pytorch_backend import SimplePytorchTrainingCollector,DEFAULT_SIMPLE_TOKEN_VOCABULARY

torch.set_num_threads(1)
root=Path.cwd();result={}
for device_name in ['cpu','mps']:
 device=torch.device(device_name);torch.manual_seed(1278951);np.random.seed(1278951)
 model,builder=load_model(root/'checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt',device)
 collector=SimplePytorchTrainingCollector(model=model,builder=builder,batch_size=2,device=device,decision_interval=8,gamma=.995,supported_decks_path=root/'training_decks/hog26_procedural_supported_seed1278401.json',typed_vocabulary_path=DEFAULT_SIMPLE_TOKEN_VOCABULARY,mirror_match=False,opponent_mode='strategy',opponent_strategy='balanced',learner_deck_name='Hog 2.6 Cycle',opponent_deck_name_schedule=('Procedural train 000-0',)*2)
 collector.policy.deterministic=True
 install_seeded_deals(collector,['balanced']*2,seed=1278951,episodes=4)
 runtime=collector.collector.bridge.runtime
 traces=[];combat_step=runtime.combat.step_tick;native_step=runtime.step_tick
 def capture_combat(**kwargs):
  combat=combat_step(**kwargs)
  row={name:getattr(runtime.state,name).detach().cpu().numpy().copy() for name in ['active','card_id','hp','x_units','y_units','target_id','cooldown_ticks']}
  row['contact']=combat.target_in_contact_range.detach().cpu().numpy().copy()
  row['attack_range']=combat.target_in_attack_range.detach().cpu().numpy().copy()
  for name in ['entity_kamikaze_ticks','entity_kamikaze_windup_ticks']:
   row['before_'+name]=getattr(runtime,name).detach().cpu().numpy().copy()
  traces.append(row)
  return combat
 def capture_tick(actions):
  joint=actions.detach().cpu().numpy().copy()
  step=native_step(actions)
  row=traces[-1];row['joint_actions']=joint
  row['after_hp']=runtime.state.hp.detach().cpu().numpy().copy()
  for name in ['entity_kamikaze_ticks','entity_kamikaze_windup_ticks']:
   row['after_'+name]=getattr(runtime,name).detach().cpu().numpy().copy()
  return step
 runtime.combat.step_tick=capture_combat;runtime.step_tick=capture_tick
 arrays,*_=collector.collect(16,model.initial_state(2,device=device),include_outcome_labels=False)
 stacked={key:np.stack([r[key] for r in traces]) for key in traces[0]}
 out=root/f'reports/hog26_ice_spirit_{device_name}_native_trace_20260908.npz';assert not out.exists();np.savez_compressed(out,**stacked);result[device_name]=stacked
 print(json.dumps({'device':device_name,'native_ticks':len(traces)}),flush=True)
report={}
for key,a in result['cpu'].items():
 b=result['mps'][key];bad=np.flatnonzero((a!=b).reshape(len(a),-1).any(1))
 if len(bad):
  tick=int(bad[0]);idx=np.argwhere(a[tick]!=b[tick])
  report[key]={'first_native_index':tick,'examples':[{'index':i.tolist(),'cpu':a[tick][tuple(i)].item(),'mps':b[tick][tuple(i)].item()} for i in idx[:4]]}
print(json.dumps(report,indent=2),flush=True)
p=root/'reports/hog26_ice_spirit_native_trace_difference_20260908.json';assert not p.exists();p.write_text(json.dumps(report,indent=2)+'\n')
