"""Retained synthetic file fixtures; no real model, media, or completion claim."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch
import torch

import validation_admission_v4 as gate
from formal_guard import SPLIT_SHA


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    root=a.output;run=root/'run';source=root/'matches';model=run/'model'
    state=root/'state.json';ex=root/'exit.json'
    write(state,dict(stage='phase-a',time=2));write(ex,dict(code=0,time=1))
    # Real producer guard rejects before any run artifact/checkpoint can be opened.
    with patch.object(gate, 'read', side_effect=AssertionError('Premature artifact read')):
        try:gate.validate_run(run,source,root/'unused-split.json',state,ex)
        except ValueError as err:assert 'not completed' in str(err)
        else:raise AssertionError('Running producer admitted')
    checks=1
    receipts={}
    for ep,split in [('train-a','train'),('val-a','validation'),('heldout-a','heldout')]:
        path=source/ep/'receipt.json';write(path,dict(episode=ep,split=split));receipts[str(path)]=gate.sha(path)
    # Heldout payload is deliberately absent; only its receipt may be consulted.
    proof=dict(receipts=receipts,synthetic_admission=True)
    write(run/'admission.json',proof)
    code=root/'synthetic-source.py';code.write_text('# Synthetic fixture, not production source.\n')
    (model/'source').mkdir(parents=True);(model/'source'/code.name).write_bytes(code.read_bytes())
    cache=root/'cache';write(cache/'train-a/index.json',dict(synthetic=True))
    sha='a'*64
    manifest=dict(seed=6108,device='cuda',precision='bf16',compile=False,epochs=24,steps=400,
        max_matches=0,windows_per_match=32,loader_workers=6,heldout_opened=False,pixel_cache=str(cache),
        source_hashes={str(code):gate.sha(code)},split_sha256=SPLIT_SHA,training_matches=1,
        cache_index_sha256={'train-a':gate.sha(cache/'train-a/index.json')},cards=['Knight'],bodies=['Knight'])
    write(model/'manifest.json',manifest)
    write(model/'data/inventory.json',dict(split='train',split_sha256=SPLIT_SHA,cards=['Knight'],
        matches=[dict(episode='train-a',split='train',receipt_sha256=receipts[str(source/'train-a/receipt.json')])]))
    for epoch in range(1,25):
        torch.save(dict(step=epoch*400,cards=['Knight'],bodies=['Knight'],model={'weight':torch.zeros(1)}),model/f'epoch-{epoch}.pt')
    torch.save({'synthetic':True},model/'last.pt')
    write(model/'complete.json',dict(manifest=manifest,steps_completed=9600,heldout_opened=False,checkpoint_sha256=gate.sha(model/'last.pt')))
    (model/'training.jsonl').write_text(''.join(json.dumps(dict(step=i,loss=1.))+'\n' for i in range(1,9601)))
    def invoke():return gate.validate_run(run,source,root/'unused-split.json',state,ex)
    with patch.object(gate,'admit',return_value=proof), patch.object(gate,'expected_sources',return_value=[code]):
        result=invoke();assert result['validated'] and result['validation_matches']==1 and not result['heldout_opening_authorized'];checks+=1
        def rejection(action, restore):
            nonlocal checks
            action()
            try:invoke()
            except ValueError:checks+=1
            else:raise AssertionError('Changed file evidence admitted')
            finally:restore()
        original=code.read_bytes()
        rejection(lambda:code.write_text('changed'),lambda:code.write_bytes(original))
        index=cache/'train-a/index.json';original_index=index.read_bytes()
        rejection(lambda:index.write_text('{}'),lambda:index.write_bytes(original_index))
        ckpt=model/'last.pt';original_checkpoint=ckpt.read_bytes()
        rejection(lambda:ckpt.write_bytes(b'changed'),lambda:ckpt.write_bytes(original_checkpoint))
        adm=run/'admission.json';original_admission=adm.read_bytes()
        rejection(lambda:write(adm,{}),lambda:adm.write_bytes(original_admission))
        receipt=source/'val-a/receipt.json';original_receipt=receipt.read_bytes()
        rejection(lambda:write(receipt,{}),lambda:receipt.write_bytes(original_receipt))
    result=dict(pass_=True,checks=checks,synthetic_only=True,fixtures=str(root),heldout_payloads_opened=False)
    write(root/'complete.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
