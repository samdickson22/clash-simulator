"""Read-only SHA/schema/root check before deciding optional G inclusion."""
import hashlib,json,subprocess,time,resource
from pathlib import Path
import numpy as np

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def main():
    start=time.monotonic();out=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1/G-verification.json');out.parent.mkdir(parents=True,exist_ok=True)
    result=dict(passed=False,shards=[])
    try:
        p=Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/pause-concat-manifest.json')
        assert sha(p)=='4e8faf7edc7164a6676f76e4f7a7d6ea237d4eba88d19252a0921c40cf409ef8'
        m=json.loads(p.read_text());assert m['complete'] and m['admission_paused'] and m['smoke_excluded']
        assert m['parent_r1_manifest_sha256']=='1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b'
        roots=0
        for item in m['shards']:
            root=Path(item['path']);assert sha(root/'manifest.json')==item['manifest_sha256']
            seal=json.loads((root/'manifest.json').read_text());assert seal['complete'] and seal['schema']=='clasher.exit-r1.teacher-v6.v1'
            for name,digest in seal['files'].items():assert sha(root/name)==digest,name
            arrays={k:np.load(root/'train'/f'{k}.npy',mmap_mode='r') for k in ('teacher_root','teacher_wait_kind','expert_action_supervision_valid','root_offsets','root_valid','root_actions','root_scores')}
            ix=np.flatnonzero(arrays['teacher_root'].astype(bool)&(arrays['teacher_wait_kind']==0)&arrays['expert_action_supervision_valid'].astype(bool))
            assert len(ix)==item['root_decisions']
            for i in ix:
                lo,hi=arrays['root_offsets'][i:i+2];assert hi>lo
                valid=arrays['root_valid'][lo:hi];actions=arrays['root_actions'][lo:hi]
                assert valid.any() and ((actions==2304)&valid).any()
                assert np.isfinite(arrays['root_scores'][lo:hi][valid]).all()
            roots+=len(ix);result['shards'].append(dict(**item,verified_files=len(seal['files']),eligible_roots=len(ix)))
        for item in m['host_manifests'].values():assert sha(item['path'])==item['sha256']
        assert roots==212542
        result.update(passed=True,eligible_roots=roots,pause_manifest_sha256=sha(p))
    except Exception as e:result['error']=repr(e)
    finally:
        u=resource.getrusage(resource.RUSAGE_SELF)
        result.update(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime)
        out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
