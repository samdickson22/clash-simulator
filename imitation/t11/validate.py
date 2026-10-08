"""Small train/synthetic-only checks of the v2 adapter, on a compute host."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import socket
import tempfile
import numpy as np
import torch
from imitation.model.store import PackedStore,epoch_indices as original,hash64
from imitation.model.batching import build_batch
from imitation.model.synthetic_store import create
from imitation.t5.resources import install,release_pages
from imitation.t5.guards import sha
from imitation.t5 import resources
from . import sampling
from .sampling import epoch_indices,train_loader


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--smoke-store',type=Path);p.add_argument('--assets')
    a=p.parse_args();assert socket.gethostname()=='127x01';torch.set_num_threads(1)
    checks={}
    with nullcontext(tempfile.mkdtemp(prefix='t11-validation-',dir='/mpac/sdicks02/tmp')) as tmp:
        # Preserve even synthetic validation fixtures under the no-delete rule.
        root=create(Path(tmp)/'train','train',128);s=PackedStore(root,'train')
        s.arrays['corpus_s122']=np.zeros(len(s),bool)
        for seed in (2026100821,2026100822):
            for epoch in range(6): np.testing.assert_array_equal(original(s,epoch,seed),epoch_indices(s,epoch,seed))
        checks['c56_sampling_identical_all_seeds_epochs']=True
        s.arrays['corpus_s122'][64:]=True
        s.arrays['weights']=s.arrays['weights'].copy()
        waits=s.arrays['expert_actions']==2304
        s.arrays['weights'][waits & s.arrays['corpus_s122']]*=2
        seed=2026100821;epoch=2;ids=s.arrays['row_ids'].astype(np.uint64)
        h=hash64(ids^np.uint64(seed)^np.uint64((epoch+1)*0x9e3779b9))>>np.uint64(32)
        expected=np.flatnonzero(~waits | (h<np.where(s.arrays['corpus_s122'],2**31,2**30)))
        np.random.default_rng(np.random.SeedSequence([seed,epoch])).shuffle(expected)
        np.testing.assert_array_equal(epoch_indices(s,epoch,seed),expected)
        checks['mixed_hash_membership_and_shuffle_exact']=True
        install()
        for workers in (0,1):
            seen=[]
            for b,y in train_loader(s,16,np.arange(len(s)),workers=workers,seed=17):
                final=y['weight']*torch.where(y['action']==2304,4.,1.)
                torch.testing.assert_close(final,torch.where(y['action']==2304,4.,1.),atol=0,rtol=0)
                seen.extend(y['index'].tolist())
            assert seen==list(range(len(s)))
        checks['both_corpora_total_wait_ipw4_workers0_1']=True
        for cursor in (0,7,31,len(expected)):
            np.testing.assert_array_equal(epoch_indices(s,epoch,seed)[cursor:],expected[cursor:])
        checks['resume_cursor_reconstruction_exact']=True
    if a.smoke_store:
        for role in ('train','dev'):
            s=PackedStore(a.smoke_store/role,role,a.assets)
            ix=np.unique(np.linspace(0,len(s)-1,64,dtype=np.int64))
            b,y=build_batch(s,ix);release_pages(s);bb,yy=build_batch(s,ix)
            for k in b:torch.testing.assert_close(b[k],bb[k],atol=0,rtol=0)
            for k in y:torch.testing.assert_close(y[k],yy[k],atol=0,rtol=0)
            if role=='train':
                epoch=epoch_indices(s,0,2026100821)
                assert set(np.flatnonzero(s.column('expert_action_supervision_valid') & (s.column('expert_actions')!=2304)))<=set(epoch)
        checks['real_train_dev_batch_and_mmap_release_exact']=True
        checks['all_supervised_plays_and_abilities_retained']=True
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps({'passed':True,'real_fitting':False,'heldout_scored':False,'checks':checks,
        'sampling_sha256':sha(sampling.__file__),'loader_sha256':sha(resources.__file__),'validator_sha256':sha(__file__),
        'smoke_manifest_sha256':sha(a.smoke_store/'manifest.json') if a.smoke_store else None,
        'assets_sha256':sha(a.assets) if a.assets else None},indent=2)+'\n')
    print(a.output.read_text())


if __name__=='__main__':main()
