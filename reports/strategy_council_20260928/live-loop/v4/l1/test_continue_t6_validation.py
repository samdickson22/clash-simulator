"""Synthetic completed-fit guard; no inference, optimizer or native data."""
import argparse
import json
from pathlib import Path
from continue_t6_validation import validate_completed_fit
from validation_admission_v4 import sha


def main(root):
    root.mkdir();run=root/'run';model=run/'run/model';model.mkdir(parents=True)
    dataset=root/'dataset';dataset.mkdir();receipts={};inventory=[]
    def put(p,value):p.write_text(json.dumps(value))
    for ep,split in [('a','train'),('b','validation')]:
        folder=root/ep;folder.mkdir();put(folder/'receipt.json',dict(episode=ep,split=split))
        digest=sha(folder/'receipt.json');receipts[str(folder/'receipt.json')]=digest
        inventory.append(dict(episode=ep,split=split,receipt_sha256=digest))
    admission=dict(receipts=receipts);put(run/'admission.json',admission)
    put(dataset/'manifest.json',{});put(dataset/'inventory.json',inventory)
    (model/'last.pt').write_bytes(b'synthetic checkpoint')
    complete=dict(epochs=24,sha256=sha(model/'last.pt'));put(model/'complete.json',complete)
    meta=dict(seed=6107,device='cuda',heldout_pixels_or_labels_opened=False,
              dataset_manifest_sha256=sha(dataset/'manifest.json'),training_episodes=['a'])
    put(model/'manifest.json',meta)
    log=''.join(json.dumps(dict(epoch=i,loss=.1))+'\n' for i in range(1,25))
    (model/'training.jsonl').write_text(log)
    checks=0
    def reject():
        nonlocal checks
        try:validate_completed_fit(run,dataset,admission)
        except ValueError:checks+=1
        else:raise AssertionError('Incomplete or changed fit accepted')
    assert validate_completed_fit(run,dataset,admission)==complete['sha256'];checks+=1
    for key,value in [('epochs',23),('sha256','bad')]:
        put(model/'complete.json',dict(complete,**{key:value}));reject()
    put(model/'complete.json',complete)
    for key,value in [('seed',42),('device','cpu'),('heldout_pixels_or_labels_opened',True),('training_episodes',[])]:
        put(model/'manifest.json',dict(meta,**{key:value}));reject()
    put(model/'manifest.json',meta)
    (model/'training.jsonl').write_text(log+json.dumps(dict(epoch=24,loss=.1)));reject()
    (model/'training.jsonl').write_text(log)
    put(dataset/'inventory.json',inventory+[inventory[-1]]);reject()
    put(dataset/'inventory.json',inventory)
    (model/'last.pt').write_bytes(b'changed');reject()
    print(json.dumps(dict(checks=checks,passed=True,scope='synthetic completed-fit guard')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
