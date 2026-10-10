"""Stage own home runtime after explicit CPU admission; no fitting/simulations."""
import hashlib,json,resource,subprocess,time
from pathlib import Path
J=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1');B=Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for v in iter(lambda:f.read(1<<20),b''):h.update(v)
    return h.hexdigest()
def copy_tree(source,target):
    if source.exists():command=['rsync','-a',str(source)+'/',str(target)+'/']
    else:command=['rsync','-a','--bwlimit=153600','--rsync-path=nice -n 19 taskset -c 63 rsync','127x03:'+str(source)+'/',str(target)+'/']
    subprocess.run(command,check=True)
def main():
    start=time.monotonic();result=dict(passed=False)
    receipt=json.loads((J/'CPU-RELEASE-ADMITTED.json').read_text());assert receipt['explicit_release']
    from admission import allowed
    assert allowed(J),'explicit release, live drain and home resource admission required before staging'
    try:
        for name in ('source','k-native','heldout-corpus','inputs'):copy_tree(B/name,J/name)
        copy_tree(Path('/mpac/sdicks02/jobs/clasher/exit-r1-20261009-r1/source'),J/'scorer-source')
        copy_tree(Path('/mpac/sdicks02/jobs/clasher/exit-r1-20261009-r1/native'),J/'scorer-native')
        sources=json.loads((J/'heldout-corpus/sources.json').read_text())['games']
        for i,item in enumerate(sources):
            if not Path(item['path']).exists():
                target=J/'heldout-games'/f'{i:04d}';target.mkdir(parents=True,exist_ok=True)
                subprocess.run(['rsync','-a','--bwlimit=153600','--rsync-path=nice -n 19 taskset -c 63 rsync','127x03:'+item['path']+'/',str(target)+'/'],check=True)
                assert sha(target/'manifest.json')==item['manifest_sha256']
        for arm,host in (('R3a','127x09'),('R3b','127x16')):
            target=J/'fits'/arm;target.mkdir(parents=True,exist_ok=True)
            subprocess.run(['rsync','-a','--bwlimit=153600','--rsync-path=nice -n 10 taskset -c 126 rsync',host+':'+str(target/'step-00002500.pt'),str(target)+'/'],check=True)
            for name in (arm+'.json',arm+'-calibration.json',arm+'-proposals.npz'):
                (J/'offline').mkdir(exist_ok=True)
                subprocess.run(['rsync','-a',host+':'+str(J/'offline'/name),str(J/'offline')+'/'],check=True)
            off=json.loads((J/'offline'/f'{arm}.json').read_text());assert sha(target/'step-00002500.pt')==off['checkpoint_sha256']
        f=json.loads((J/'freeze.json').read_text());assert sha(J/'heldout-corpus/manifest.json')==f['heldout_manifest_sha256'] and sha(J/'inputs/main02.pt')==f['files']['inputs/main02.pt']
        heldout=json.loads((J/'heldout-corpus/manifest.json').read_text())
        for name,want in heldout['files'].items():assert sha(J/'heldout-corpus'/name)==want
        assert sha(J/'scorer-native/clasher_core.abi3.so')=='06d8e5397908b2addc5e0a8b2db0d837da79d56b8dd56aaa3491307da5fc0e10'
        assert sha(J/'k-native/clasher_core.abi3.so')=='44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2'
        snapshot=json.loads((J/'source-manifests.json').read_text())
        for prefix in ('source','scorer-source'):
            for name,want in snapshot[prefix].items():assert sha(J/prefix/name)==want,name
        result.update(passed=True,host=receipt['host'],checkpoint_sha256={a:sha(J/'fits'/a/'step-00002500.pt') for a in ('R3a','R3b')})
    finally:
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        result.update(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime+v.ru_utime+v.ru_stime,note='Local staging whole tree once; read-only remote sender CPU unmetered')
        (J/'CPU-STAGING.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
