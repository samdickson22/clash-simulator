import json
from pathlib import Path
import numpy as np
import torch
from clasher.rl.model import PolicyInputs
from scripts.evaluate_hog26_simple_policy import load_model
from scripts.collect_hog26_direct_simple_behavior import file_sha256, _atomic_json

torch.set_num_threads(1)
root=Path.cwd()
path=root/'datasets/derived/hog26_seeded_opening_cpu_probe_seed1278951/corpus.npz'
checkpoint=root/'checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt'
with np.load(path,allow_pickle=False) as archive:
    names=['entity_ids','entity_features','entity_mask','hand_ids','global_features','action_masks','previous_actions','previous_rewards','episode_starts','actions','episode_offsets','initial_hidden','initial_cell']
    arrays={key:archive[key] for key in names}
models={device:load_model(checkpoint,torch.device(device))[0] for device in ['cpu','mps']}
report={'schema':'clasher.hog26.completed-public-policy-device-replay.v1','role':'training-only-device-diagnostic','corpus_sha256':file_sha256(path),'checkpoint_sha256':file_sha256(checkpoint),'input_route':'full retained public tensors, exact previous reward/action, recurrent episode reset; batch4 repeated actor inputs','limitation':'isolates learner policy numerics on CPU-recorded observations; not simulator or opponent parity','episodes':[]}
with torch.inference_mode():
 for ep,(begin,end) in enumerate(zip(arrays['episode_offsets'][:-1],arrays['episode_offsets'][1:])):
    results={}
    for device,model in models.items():
      state=tuple(torch.tensor(arrays[name][ep],device=device).expand(4,-1).clone() for name in ['initial_hidden','initial_cell'])
      predicted=[]
      for row in range(begin,end):
        def value(name):
          raw=torch.as_tensor(arrays[name][row:row+1],device=device)
          return raw.unsqueeze(0).expand(4,*raw.shape).clone()
        inputs=PolicyInputs(entity_ids=value('entity_ids'),entity_features=value('entity_features'),entity_mask=value('entity_mask'),hand_ids=value('hand_ids'),global_features=value('global_features'),action_mask=value('action_masks'),previous_actions=value('previous_actions'),previous_rewards=value('previous_rewards'),episode_starts=value('episode_starts'))
        if model.config.public_observation_confidence: inputs=inputs.with_exact_actor_confidence()
        actions,_,_,state,_=model.act(inputs,state,deterministic=True)
        predicted.append(int(actions[0,0].cpu()))
      results[device]=np.array(predicted)
    saved=arrays['actions'][begin:end]
    comparisons={}
    for name,a,b in [('cpu_vs_recorded',results['cpu'],saved),('mps_vs_recorded',results['mps'],saved),('cpu_vs_mps',results['cpu'],results['mps'])]:
      bad=np.flatnonzero(a!=b)
      comparisons[name]={'mismatches':len(bad),'first_mismatch':None if not len(bad) else int(bad[0]),'first_examples':[{'decision':int(i),'left':int(a[i]),'right':int(b[i])} for i in bad[:8]]}
    report['episodes'].append({'episode':ep,'decisions':int(end-begin),'comparisons':comparisons})
    print(json.dumps(report['episodes'][-1]),flush=True)
out=root/'reports/hog26_completed_cpu_policy_device_replay_20260908.json'
assert not out.exists()
_atomic_json(out,report)
