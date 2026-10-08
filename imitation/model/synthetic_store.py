"""Create a tiny complete mmap fixture for CPU integration tests (not real data)."""
import argparse
import json
from pathlib import Path
import numpy as np
from .store import D1_KEYS, PACKET_KEYS
from .synthetic import packet


def create(root, role, n=32, seed=1):
    root=Path(root); root.mkdir(parents=True, exist_ok=False)
    values={key:[] for key in (*PACKET_KEYS,*D1_KEYS)}
    values.update({key:[] for key in ("action_mask","expert_actions","expert_action_supervision_valid","weights",
                   "intent_card","intent_bin","intent_observed","intent_valid","perspective_ids","row_ids",
                   "submitted_ticks","match_part","archetype","mode","p16","engine_phase","forms","ability_attributable")})
    flat={key:[] for key in ("ids","levels","features")}; offsets=[0]
    for i in range(n):
        p,d=packet(2,seed+i)
        p["action_mask"][0]=True
        for key in PACKET_KEYS: values[key].append(p[key])
        for key in D1_KEYS: values[key].append(d[key])
        target={"action_mask":p["action_mask"], "expert_actions":0 if i%3 == 0 else 2304 if i%3 == 1 else 2305,
                "expert_action_supervision_valid":True,"weights":1.,"intent_card":0,"intent_bin":1,
                "intent_observed":True,"intent_valid":True,"perspective_ids":i//8,"row_ids":i,
                "submitted_ticks":i*5,"match_part":"early","archetype":"synthetic","mode":"friendly",
                "p16":True,"engine_phase":"s117","forms":"base","ability_attributable":True}
        for key,value in target.items(): values[key].append(value)
        for key in flat: flat[key].append(p["entity_"+key])
        offsets.append(offsets[-1]+2)
    values={k:np.asarray(v) for k,v in values.items()}
    values.update({"flat_entity_"+k:np.concatenate(v) for k,v in flat.items()})
    values["entity_offsets"]=np.asarray(offsets,np.int64)
    for key,value in values.items(): np.save(root/f"{key}.npy",value)
    np.savez(root/"assets.npz",descriptors=np.zeros((360,57),np.float32),tiles=np.zeros((576,12),np.float32),
             costs=np.full(360,3,np.float32), names=np.array([str(i) for i in range(360)]),
             arenas=np.array(["TrainingCamp"]*360))
    manifest={"schema":"clasher.imitation.model-store.v1","role":role,"rows":n,
              "arrays":{k:f"{k}.npy" for k in values},"assets":"assets.npz","hashes":{},"synthetic":True}
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return root


if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("root"); p.add_argument("--rows",type=int,default=32)
    a=p.parse_args()
    for role in ("train","dev"): create(Path(a.root)/role,role,a.rows)
