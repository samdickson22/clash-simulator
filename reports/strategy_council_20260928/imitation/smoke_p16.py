"""Upgrade/forward plumbing check on one TRAIN perspective; no held-out scoring."""
import json
import time
import numpy as np
from replay_sidecars import HERE,DATA,sha,write


def main():
    import torch
    from clasher.rl.contract_v5 import ContractV5ObservationBuilder
    from p16_upgrade import upgrade_p16
    from clasher.rl.model import ClasherPolicy,PolicyConfig
    from clasher.rl.human_replay_v5 import load_human_replay_shard_v5
    from clasher.rl.human_replay_bc import _run_streams
    torch.set_num_threads(1);start=time.perf_counter()
    path=HERE.parent/'human-prior-p16/checkpoints/human-bc-natural-seed2903.pt'
    builder=ContractV5ObservationBuilder()
    payload,upgrade_receipt=upgrade_p16(torch.load(path,map_location='cpu',weights_only=False),builder)
    model=ClasherPolicy(PolicyConfig.from_dict(payload['model_config']),torch.as_tensor(builder.card_stat_features)).eval()
    model.load_state_dict(payload['model_state_dict'])
    plan=json.loads((HERE/'data/store-smoke-v2/plan.json').read_text())
    unit=plan['units'][0];selected=next(p for p in unit['perspectives'] if p['role']=='train' and p['p16'])
    shard=load_human_replay_shard_v5(DATA/'recon/engine-v3'/f"{unit['key']}.npz")
    begin=selected['source_start'];arrays=shard.arrays(slice(begin,begin+selected['rows']))
    calls=[0]
    def step(output,batch,labels,weights):
        logp=output.joint_logits.reshape(-1,2306)[weights>0]
        assert torch.isfinite(logp).all()
        assert torch.allclose(logp.exp().sum(1),torch.ones(len(logp)),atol=1e-5)
        calls[0]+=1
    with torch.no_grad():
        rows=_run_streams(model,iter([(selected['summary'],arrays)]),streams=1,sequences_per_step=1,sequence_length=64,
            device=torch.device('cpu'),step=step,select_play_rows=False,
            weights_for=lambda summary,a:a['expert_action_supervision_valid'].astype(np.float32))
    write(HERE/'data/receipts/t3-p16-smoke.json',dict(passed=True,role='train',identity=selected['identity'],rows=rows,
          chunks=calls[0],checkpoint_sha256=sha(path),upgrade=upgrade_receipt,wall_seconds=time.perf_counter()-start))


if __name__=='__main__':main()
