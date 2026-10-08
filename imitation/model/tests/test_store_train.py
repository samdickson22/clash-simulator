from argparse import Namespace
from dataclasses import asdict
import random
import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader
from imitation.model.synthetic_store import create
from imitation.model.store import PackedStore, collate, epoch_indices
from imitation.model.synthetic import model, batch
from imitation.model.train import optimizer_step, save_checkpoint, update_ema
from imitation.model.inference import load_policy
from imitation.model.network import ModelConfig
from imitation.model.runner import evaluate_checkpoint


def test_store_sampling_and_protected_roles(tmp_path):
    root=create(tmp_path/"train","train",128)
    store=PackedStore(root,"train")
    i=epoch_indices(store,0,1); j=epoch_indices(store,1,1)
    np.testing.assert_array_equal(i,epoch_indices(store,0,1))
    assert set(np.where(store.column("expert_actions")!=2304)[0]) <= set(i)
    assert not np.array_equal(i,j)
    with pytest.raises(ValueError): PackedStore(root,"eval")
    b,y=next(iter(DataLoader(store,batch_size=4,collate_fn=collate)))
    assert b["ids"].shape[0]==4
    assert y["action"].tolist()==[0,2304,2305,0]


def test_checkpoint_resume_optimizer_and_dev_pipeline(tmp_path):
    torch.manual_seed(7)
    c=ModelConfig(dropout=0.)
    m=model(c); b,y=batch(3,2)
    optimizer=torch.optim.AdamW(m.parameters(),lr=3e-4,weight_decay=.05)
    scheduler=torch.optim.lr_scheduler.LambdaLR(optimizer,lambda _:1.)
    ema={k:v.detach().clone() for k,v in m.state_dict().items()}
    first=optimizer_step(m,optimizer,b,y,2,torch.device("cpu"))["loss"]
    update_ema(ema,m)
    path=tmp_path/"checkpoint.pt"
    save_checkpoint(path,m,ema,optimizer,scheduler,c,{"epoch":0,"cursor":3,"step":1},{},Namespace(seed=7))
    payload=torch.load(path,weights_only=True)
    m2=model(c); m2.load_state_dict(payload["model"])
    opt2=torch.optim.AdamW(m2.parameters(),lr=3e-4,weight_decay=.05); opt2.load_state_dict(payload["optimizer"])
    next1=optimizer_step(m,optimizer,b,y,2,torch.device("cpu"))["loss"]
    next2=optimizer_step(m2,opt2,b,y,2,torch.device("cpu"))["loss"]
    assert next1 < first
    assert next1==pytest.approx(next2,abs=1e-7)
    for a,z in zip(m.parameters(),m2.parameters()): torch.testing.assert_close(a,z,atol=0,rtol=0)
    assert load_policy(path).model.training is False
    dev=create(tmp_path/"dev","dev",8)
    evaluate_checkpoint(Namespace(store=str(dev),checkpoint=str(path),output=str(tmp_path/"evaluation"),
                                 device="cpu",calibrate=True,calibration_rows=8,batch_size=4,bootstrap=20))
    assert (tmp_path/"evaluation"/"report.json").exists()
    assert (tmp_path/"evaluation"/"policy.ts").exists()


def test_actual_t3_adapter_mask_time_history_and_intent(tmp_path):
    import json
    import hashlib
    from imitation.model.store import sha256
    from imitation.model.features import build_row
    from imitation.model.losses import HAZARD_EDGES
    root=create(tmp_path/"actual"/"train","train",8)
    old=json.loads((root/"manifest.json").read_text())
    arrays={k:np.load(root/v) for k,v in old["arrays"].items()}
    for side in ("opp","own"):
        history=arrays.pop(side+"_history")
        arrays[side+"_recent_play_ids"]=history[:,:,0].astype(np.int16)
        arrays[side+"_recent_play_features"]=history[:,:,1:]
        arrays[side+"_refill_remaining"]=np.full(8,500,np.int16)
    ability=arrays.pop("opp_abilities")
    arrays["opp_ability_ids"]=ability[:,:,0].astype(np.int16)
    arrays["opp_ability_ages"]=ability[:,:,1:]
    masks=arrays.pop("action_mask")
    arrays["mask_index"]=np.arange(8,dtype=np.int32)
    arrays["episode_ids"]=arrays["perspective_ids"]
    arrays["source_unit"]=np.zeros(8,np.int16); arrays["source_row"]=np.arange(8,dtype=np.int32)
    arrays["intent_deck_index"]=arrays.pop("intent_card")
    arrays["intent_card"]=np.ones(8,np.int16)
    arrays["intent_censored"]=~arrays.pop("intent_observed")
    arrays["intent_censored"][0]=True
    arrays["intent_delay_ticks"]=np.ones(8,np.int32) # exactly 0.05 seconds
    arrays.pop("intent_valid")
    for k,v in arrays.items(): np.save(root/f"{k}.npy",v)
    np.save(root.parent/"mask_table.npy",np.packbits(masks,axis=-1))
    manifest={"role":"train","rows":8,"arrays":{k:{"shape":list(v.shape),"dtype":str(v.dtype)} for k,v in arrays.items()},"perspectives":[]}
    (root/"manifest.json").write_text(json.dumps(manifest))
    parent={"schema":"clasher.imitation.packed.v1","passed":True,
            "role_manifests":{"train":sha256(root/"manifest.json")},
            "role_file_sha256":"0"*64,"eval_spec_sha256":"1"*64,"sidecar_manifest_sha256":"2"*64}
    (root.parent/"manifest.json").write_text(json.dumps(parent))
    asset=root/"assets.npz"
    (root/"assets.npz.json").write_text(json.dumps({"asset_sha256":sha256(asset),"token_sha256":"3"*64}))
    store=PackedStore(root,"train",asset)
    row,y=store[0]
    np.testing.assert_array_equal(row["action_mask"],masks[0])
    glob=row["numeric"][row["types"]==18][0]
    assert glob[16]==pytest.approx(.5) and glob[17]==pytest.approx(.5)
    assert y["intent_observed"] is False and y["intent_bin"]==1 # completed first interval
    assert store[1][1]["intent_bin"]==0 # event on boundary belongs to first interval
    receipt={"passed":True,"store_manifest_sha256":store.hashes["store_manifest"],
             "role_file_sha256":store.hashes["roles"],"roles":{"train":{"rows":8,"perspectives":0}}}
    store.verify_qualification(receipt)
    for key in ("store_manifest_sha256", "role_file_sha256"):
        with pytest.raises(ValueError, match="mismatch"):
            store.verify_qualification({**receipt,key:"f"*64})
    with pytest.raises(ValueError, match="counts mismatch"):
        store.verify_qualification({**receipt,"roles":{"train":{"rows":7,"perspectives":0}}})
    with pytest.raises(ValueError, match="passed T3"):
        store.verify_qualification({**receipt,"passed":False})

    from imitation.model.batching import build_batch
    b,y=build_batch(store,np.arange(8))
    old,oy=collate([store[i] for i in range(8)])
    for key in b: torch.testing.assert_close(b[key],old[key],atol=0,rtol=0)
    for key in y: torch.testing.assert_close(y[key],oy[key],atol=0,rtol=0,check_dtype=False)


def test_batched_adapter_and_joint_match_scalar(tmp_path):
    from imitation.model.batching import build_batch, batch_loader
    from imitation.model.runner import joint_nll_rows
    from imitation.model.evaluate import metric_rows
    store=PackedStore(create(tmp_path/"dev", "dev", 17), "dev")
    ix=np.array([16,0,3,7,2,1])
    b,y=build_batch(store,ix)
    old,oy=collate([store[int(i)] for i in ix])
    for key in b: torch.testing.assert_close(b[key],old[key],atol=0,rtol=0)
    for key in y: torch.testing.assert_close(y[key],oy[key],atol=0,rtol=0,check_dtype=False)
    loaded=list(batch_loader(store,4,ix,workers=1))
    assert torch.cat([v[1]["index"] for v in loaded]).tolist()==ix.tolist()
    m=model(ModelConfig(dropout=0.)).eval()
    with torch.inference_mode():
        o=m(b,torch.empty(0,dtype=torch.long))
        teacher=m(b,(y["action"].long()//576).clamp(0,3))
        reference=metric_rows(o,y,b["ids"][:,:4])["joint_nll"]
        np.testing.assert_allclose(joint_nll_rows(teacher,y).numpy(),reference,atol=1e-6,rtol=1e-6)
