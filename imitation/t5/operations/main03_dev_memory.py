"""Main03 resource-only allocator cap and unused-cache release around dev."""
import argparse,json,hashlib,socket,sys
from pathlib import Path
from datetime import datetime,timezone


def configure():
    import torch
    from imitation.model import runner
    torch.cuda.set_per_process_memory_fraction(0.75)
    original = runner.dev_joint_nll
    def snapshot(phase):
        free,total = torch.cuda.mem_get_info()
        print(json.dumps({'event':'dev_memory_boundary','phase':phase,
                          'allocated_bytes':torch.cuda.memory_allocated(),
                          'reserved_bytes':torch.cuda.memory_reserved(),
                          'free_bytes':free,'total_bytes':total}),flush=True)
    def cache_bounded_dev(*args, **kwargs):
        torch.cuda.empty_cache()
        snapshot('before_dev')
        try:
            return original(*args, **kwargs)
        finally:
            torch.cuda.empty_cache()
            snapshot('after_dev')
    runner.dev_joint_nll = cache_bounded_dev


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(add_help=False,allow_abbrev=False)
    p.add_argument('--operational-freeze',required=True)
    p.add_argument('--operational-freeze-sha256',required=True)
    p.add_argument('--resume-sha256',required=True)
    a,rest=p.parse_known_args();specfile=Path(a.operational_freeze)
    assert sha(specfile)==a.operational_freeze_sha256
    spec=json.loads(specfile.read_text())
    for name,digest in spec['files'].items():assert sha(specfile.parent/name)==digest,name
    assert sha(__file__)==spec['files'][Path(__file__).name]
    host=socket.gethostname().split('.')[0];run=spec['hosts'][host]
    options=dict(zip(rest[::2],rest[1::2]))
    assert options['--variant']==run['variant'] and options['--seed']==str(run['seed'])
    assert Path(options['--output']).resolve()==Path(run['output'])
    assert Path(options['--resume']).resolve().parent==Path(run['output'])
    assert sha(options['--resume'])==a.resume_sha256
    assert sha(options['--freeze'])==spec['parent_manifest_sha256']
    assert host=='127x13' and options['--stop-at']=='2026-10-09T04:20:00Z'
    from imitation.t5.guards import frozen
    from imitation.t5 import train
    root=Path(run['source']);assert Path(train.__file__).resolve()==root/'imitation/t5/train.py'
    frozen(root,options['--freeze']);configure()
    record={'at':datetime.now(timezone.utc).isoformat(),'operational_freeze_sha256':sha(specfile),
            'cuda_allocator_fraction':0.75,'empty_cache_before_after_dev':True,'resume':options['--resume'],'resume_sha256':a.resume_sha256,
            'scientific_source_changed':False,'training_recipe_changed':False}
    with (Path(run['output'])/'allocator-operations.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
    print(json.dumps({'event':'allocator_headroom_override',**record}),flush=True)
    sys.argv=[sys.argv[0],*rest];train.main()

if __name__=='__main__':main()
