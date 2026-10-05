"""Load only completed final checkpoints and record finite, nonzero updates."""
from pathlib import Path
import hashlib
import json
import sys
import torch
from clasher.rl.eval import load_policy_checkpoint

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
INITIAL=REPO/'reports/strategy_council_20260928/human-prior-p16/checkpoints/human-bc-natural-seed2903.pt'
DECKS=REPO/'reports/strategy_council_20260928/m0/data/roles_v2/training.json'
torch.set_num_threads(1)
initial=load_policy_checkpoint(INITIAL,device=torch.device('cpu'),decks_path=DECKS).model.state_dict()
target=ROOT/'results/final-checkpoints.json'
results=json.loads(target.read_text()) if target.exists() else {}

def finite(value):
    if isinstance(value,torch.Tensor): return bool(torch.isfinite(value).all())
    if isinstance(value,dict): return all(finite(x) for x in value.values())
    if isinstance(value,(list,tuple)): return all(finite(x) for x in value)
    return True

for label in sys.argv[1:]:
    run=ROOT/'runs'/label
    receipt=json.loads((run/'completion.json').read_text())
    assert receipt['completed'] and receipt['decisions']==150000
    path=run/'final.pt'
    loaded=load_policy_checkpoint(path,device=torch.device('cpu'),decks_path=DECKS)
    checkpoint=torch.load(path,map_location='cpu',weights_only=False)
    state=loaded.model.state_dict()
    assert state.keys()==initial.keys()
    changed={'actor':0,'critic':0}
    for name,value in state.items():
        assert value.shape==initial[name].shape
        group='critic' if name.startswith(('critic_encoder.','value_head.')) else 'actor'
        changed[group]+=int(not torch.equal(value,initial[name]))
    result=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),decisions=checkpoint['total_transitions'],
                model_finite=finite(state),optimizer_finite=finite(checkpoint['optimizer_state_dict']),changed_tensors=changed)
    assert result['model_finite'] and result['optimizer_finite'] and all(changed.values())
    results[label]=result
    print(label,json.dumps(result))
target.write_text(json.dumps(results,indent=2)+'\n')
