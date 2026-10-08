"""V2 dev calibration and embargo-guarded, once-only sufficient statistics.

Imports qualified network, metric and calibration functions plus the exact
T5 bounded loader/baseline. No eval path exists without a sealed two-run
release and the unchanged published v1 report.
"""
import argparse
from contextlib import nullcontext
from datetime import datetime,timezone
import json
from pathlib import Path
import time
import numpy as np
import torch
from imitation.model.network import ModelConfig,SetPolicy
from imitation.model.store import PackedStore
from imitation.model.batching import batch_loader
from imitation.model import runner
from imitation.model.evaluate import metric_rows,fit_temperature
from imitation.t5.guards import sha,write_once,canonical_hash,role_guard
from imitation.t5.resources import install
from .frequency import frequency_rows
from .train import frozen
from .select import RUNS


class HeldoutStore(PackedStore):
    def __init__(self,directory,role,assets,manifest):
        role_guard(directory,role,manifest,heldout=True)
        self.root=Path(directory).resolve();self.manifest_path=self.root/'manifest.json'
        self.manifest=json.loads(self.manifest_path.read_text())
        assert self.manifest['role']==role and 'perspectives' in self.manifest
        self.t3=True;self._load_t3(role,assets)


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('calibrate','score'))
    for name in ('freeze','checkpoint','store','assets','output','selection','run'):p.add_argument('--'+name,required=True)
    p.add_argument('--release');p.add_argument('--frequency-counts');p.add_argument('--roles');p.add_argument('--technical-resume')
    p.add_argument('--device',default='cuda');a=p.parse_args();start=time.monotonic()
    root=Path(__file__).resolve().parents[2];m,pins=frozen(root,a.freeze)
    selection=json.loads(Path(a.selection).read_text())
    assert set(selection['runs'])==set(RUNS) and selection['manifest_sha256']==pins['T11_manifest']
    chosen=selection['runs'][a.run];checkpoint_hash=sha(a.checkpoint)
    assert chosen['checkpoint_sha256']==checkpoint_hash and sha(a.assets)==m['assets_sha256']
    role=Path(a.store).name;out=Path(a.output)
    if a.mode=='score':
        assert role in ('eval','eval_ood') and a.release and a.roles and a.frequency_counts
        release=json.loads(Path(a.release).read_text())
        assert set(release['runs'])==set(RUNS) and release['selection_sha256']==sha(a.selection)
        assert release['manifest_sha256']==pins['T11_manifest']
        assert sha(release['v1_report'])==release['v1_report_sha256'],'v1 report absent or changed'
        item=release['runs'][a.run]
        assert item['checkpoint_sha256']==checkpoint_hash and item['calibration']['checkpoint_sha256']==checkpoint_hash
        assert item['temperature_content_sha256']==canonical_hash(item['calibration'])
        temperatures=item['calibration']['temperatures']
        assert sha(a.frequency_counts)==m['frequency_counts_sha256'] and sha(a.roles)==m['role_file_sha256']
        role_guard(a.store,role,m,heldout=True)
    else:
        assert role=='dev' and not out.exists(), 'calibration requires a fresh output'
        role_guard(a.store,role,m)
    # No checkpoint/model or heldout rows are loaded before release checks.
    install();torch.set_num_threads(1);torch.set_num_interop_threads(1);device=torch.device(a.device)
    ckpt=torch.load(a.checkpoint,map_location='cpu',weights_only=True)
    assert ckpt['args']['seed']==RUNS[a.run] and all(ckpt['hashes'].get(k)==v for k,v in pins.items())
    state=ckpt['ema'];model=SetPolicy(ModelConfig(**ckpt['config']),state['descriptors'],state['tile_features'],state['costs'])
    model.load_state_dict(state);model=model.to(device).eval()
    if a.mode=='calibrate':
        store=PackedStore(a.store,'dev',a.assets)
        data=runner.calibration_data(model,store,device,1024,cap=100000,seed=1,workers=1)
        temps=[fit_temperature(*data[k],role='dev') for k in ('gate','card','tile')]
        write_once(out,dict(run=a.run,role='dev',checkpoint_sha256=checkpoint_hash,selection_sha256=sha(a.selection),
                           manifest_sha256=pins['T11_manifest'],temperatures=temps,sample_seed=1,sample_cap=100000,
                           head_rows={k:len(v[2]) for k,v in data.items()},wall_seconds=time.monotonic()-start))
        return
    claim=Path(a.checkpoint).parent/f'v2-heldout-{role}.claim.json'
    contract=dict(run=a.run,role=role,output=str(out.resolve()),checkpoint_sha256=checkpoint_hash,
                  release_sha256=sha(a.release),**pins)
    if claim.exists():
        assert json.loads(claim.read_text())==contract and a.technical_resume
        assert not (out/'complete.json').exists(),'already scored; use saved statistics'
        with (out/'technical-resumes.jsonl').open('a') as f:f.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'reason':a.technical_resume})+'\n')
    else:
        assert not out.exists();write_once(claim,contract);out.mkdir(parents=True)
    store=HeldoutStore(a.store,role,a.assets,m);roles=json.loads(Path(a.roles).read_text())
    names=store.assets['names'].tolist();metadata={'perspectives':{}}
    for item in store.perspectives:
        summary=item['summary'];begin=item['target_start'];pid=str(int(store.arrays['perspective_ids'][begin]))
        assert pid not in metadata['perspectives']
        metadata['perspectives'][pid]=dict(identity=item['identity'],start=begin,rows=item['rows'],corpus=item['corpus'],
            flags=item['flags'],p16=item['p16'],family=roles['family'][item['identity']],mode=summary['info'].get('battle_type','other'),
            end_tick=summary['playable_end_tick'],ability_attributable=bool(summary['ability_attributable']),
            forms={str(names.index(n)):f for n,f in zip(summary['own_deck'],summary['own_forms'])})
    if not (out/'slice-metadata.json').exists():write_once(out/'slice-metadata.json',metadata)
    else:assert json.loads((out/'slice-metadata.json').read_text())==metadata
    with np.load(a.frequency_counts,allow_pickle=False) as z:counts={k:z[k] for k in ('gate','cards','tiles')}
    cursor=0
    for path in sorted(out.glob('batch-*.npz')):
        with np.load(path,allow_pickle=False) as z:
            ix=z['index'];assert np.array_equal(ix,np.arange(cursor,cursor+len(ix)))
            np.testing.assert_array_equal(z['row_id'],store.arrays['row_ids'][ix])
            np.testing.assert_array_equal(z['perspective'],store.arrays['perspective_ids'][ix])
            cursor+=len(ix)
    with torch.inference_mode():
        for b,y in batch_loader(store,1024,np.arange(cursor,len(store)),workers=1,pin_memory=device.type=='cuda'):
            b,y=runner.transfer(b,device),runner.transfer(y,device)
            with torch.autocast('cuda',dtype=torch.bfloat16) if device.type=='cuda' else nullcontext():
                o=model(b,torch.empty(0,dtype=torch.long,device=device))
            values={}
            for stage,temps in [('before',(1.,1.,1.)),('after',temperatures)]:
                values.update({stage+'__'+k:v for k,v in metric_rows(o,y,b['ids'][:,:4],temps).items()})
            ix=y['index'].cpu().numpy();baseline=frequency_rows(store,ix,counts)
            values.update({'frequency__'+k:v for k,v in baseline.items()})
            values.update(index=ix,row_id=y['row_id'].cpu().numpy(),perspective=y['perspective'].cpu().numpy(),
                          p16=np.array(store.arrays['p16'][ix]),corpus_s122=np.array(store.arrays['corpus_s122'][ix]),
                          submitted_ticks=np.array(store.arrays['submitted_ticks'][ix]),source_unit=np.array(store.arrays['source_unit'][ix]))
            final=out/f'batch-{cursor:09d}.npz';tmp=final.with_suffix('.partial')
            if tmp.exists():tmp.rename(out/(tmp.name+'.failed-'+str(time.time_ns())))
            with tmp.open('xb') as f:np.savez(f,**values)
            tmp.replace(final);cursor+=len(ix)
            if cursor%65536==0:print(json.dumps({'role':role,'rows':cursor,'seconds':time.monotonic()-start}),flush=True)
    write_once(out/'complete.json',dict(**contract,rows=cursor,wall_seconds=time.monotonic()-start,
        slice_metadata_sha256=sha(out/'slice-metadata.json'),batches={p.name:sha(p) for p in sorted(out.glob('batch-*.npz'))}))


if __name__=='__main__':main()
