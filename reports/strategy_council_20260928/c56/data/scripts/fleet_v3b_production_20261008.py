"""Recovered-hub production orchestration; unchanged extractor and row validators."""
import concurrent.futures
import datetime
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import shlex
import socket
import shutil
import traceback
import subprocess
import sys
import time
import fleet_v3b_production_worker_20261008 as f
import fleet_v3b_supervise as s

ROOT=s.ROOT; D=s.D; Q=f.Q; OUT=f.OUT; NODES=f.NODES
s.SCRIPT=D/'scripts/fleet_v3b_production_worker_20261008.py'
LABEL='c56-v3b-production-20261008'
SELF=Path(__file__)
_remote=s.remote
def remote(host, command):
    if host==socket.gethostname():
        return subprocess.check_output(['bash','-c',command],text=True,timeout=90)
    return _remote(host,command)
s.remote=remote

def command(mode, workers=4):
    return ['env', f'CLASHER_ROOT={D}/runtime-engine-v3b', f'PYTHONPATH={D}/runtime-engine-v3b/src',
            f'C56_FLEET_Q={Q}', 'OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','NUMEXPR_NUM_THREADS=1',
            str(ROOT/'.venv/bin/python'),'-B',str(SELF if mode in ('supervise','inventory','mirror','preserve-verify') else s.SCRIPT),
            mode, *([] if mode in ('supervise','inventory','mirror','preserve-verify') else ['--workers',str(workers)])]

def inventory():
    host=socket.gethostname(); plan=f.read(Q/'partition.json')
    completed={}; perspectives=rows=errors=0
    for key in plan['assignments'][host]:
        path=OUT/(key+'.json')
        if not path.exists(): continue
        side=f.read(path)
        completed[key]={'sidecar_sha256':f.cb.file_sha256(path),'npz_sha256':side['npz_sha256'],'bytes':side['bytes']}
        perspectives+=len(side['perspectives']); rows+=side['rows']; errors+=len(side['errors'])
    launch=f.read(Q/f'launch-{host}.json') if (Q/f'launch-{host}.json').exists() else {}
    status=f.read(Q/f'status-{host}.json') if (Q/f'status-{host}.json').exists() else {}
    cpu=0.; pid=launch.get('pid'); alive=False
    if pid and Path(f'/proc/{pid}/stat').exists():
        proc={}
        for p in Path('/proc').glob('[0-9]*/stat'):
            try:
                a=p.read_text().rsplit(')',1)[1].split(); proc[int(p.parent.name)]=(int(a[1]),int(a[11])+int(a[12]),int(a[13])+int(a[14]))
            except (OSError,ValueError): pass
        owned={pid}; previous=set()
        while previous!=owned:
            previous=owned.copy(); owned.update(p for p,v in proc.items() if v[0] in owned)
        cpu=(sum(proc[p][1] for p in owned if p in proc)+proc.get(pid,(0,0,0))[2])/os.sysconf('SC_CLK_TCK')
        alive=pid in proc
    done=Q/f'completed-{host}.json'
    if done.exists():
        end=f.read(done); cpu=end['cpu_seconds']; status['wall_seconds']=end['wall_seconds']
    return dict(utc=f.ex.utc(),host=host,files=completed,units=len(completed),perspectives=perspectives,rows=rows,errors=errors,
                launch=launch,status=status,cpu_seconds=cpu,driver_alive=alive,complete=done.exists())

def preserve_verify():
    host=socket.gethostname(); receipt=f.read(Q/f'v2-preservation-{host}.json')
    for name,info in receipt['files'].items():
        for root in ('source','destination'):
            assert f.cb.file_sha256(Path(receipt[root])/name)==info['sha256'],(host,root,name)
    result=dict(utc=f.ex.utc(),host=host,archives=receipt['archives'],originals_and_preserved_copies_verified=True)
    f.write(Q/f'v2-final-verification-{host}.json',result)
    return result


def mirror(final=False):
    # Snapshot only stable published output; no live lock transfer during extraction.
    files=[]
    for p in OUT.rglob('*'):
        if not p.is_file() or p.name.endswith('.tmp') or (not final and p.name in ('driver.lock','active.json','errors.jsonl')): continue
        if p.suffix=='.npz' and not p.with_suffix('.json').exists(): continue
        files.append(str(p.relative_to(OUT)))
    listing=Q/'mirror-files.txt'; listing.write_text('\n'.join(sorted(files))+'\n')
    s.sync(str(OUT)+'/',f'127x04:{OUT}/','--files-from='+str(listing))
    raw=subprocess.check_output(['rsync','-rcn','--out-format=%i %n','--files-from='+str(listing),str(OUT)+'/',f'127x04:{OUT}/'],text=True)
    assert not raw.strip(),raw
    result=dict(utc=f.ex.utc(),complete_corpus=final,files=len(files),bytes=sum((OUT/n).stat().st_size for n in files),checksum_differences=0,host='127x04',source=str(OUT))
    f.write(Q/'mirror-127x04.json',result)
    return result

def mirror_reports():
    # Explicit allowlist: no NPZ or bulk row-audit caches on command center.
    for name in ('PROGRESS.md','FLEET-RESULTS.md'):
        s.sync(D/name,f'127x05:{D}/{name}')
    subprocess.run(['ssh','127x05','mkdir','-p',str(Q)],check=True)
    s.sync(str(Q)+'/',f'127x05:{Q}/','--include=/*.json','--include=/*.txt','--include=/*.sh','--exclude=*')
    for name in ('fleet_v3b_production_worker_20261008.py',SELF.name):
        s.sync(D/'scripts'/name,f'127x05:{D}/scripts/{name}')

def checkpoint(nodes, validated, final=False):
    summaries=[]; errors=[]; rows=illegal=0
    for key in validated:
        result=f.read(Q/'unit-audits'/(key.replace('/','-')+'.json'))['result']
        summaries.extend(result['summaries']); errors.extend(result['errors']); rows+=result['rows']; illegal+=result['illegal']
    stats=f.aggregate(summaries)
    result=dict(utc=f.ex.utc(),complete=final,hub_validated_units=len(validated),hub_perspectives=len(summaries),hub_rows=rows,
                errors=len(errors),illegal_labels=illegal,stats=stats,nodes=nodes,
                fleet_extracted_units=811+sum(n['units'] for n in nodes.values()),
                output_bytes=sum(p.stat().st_size for p in OUT.glob('*/shard-*') if p.suffix in ('.npz','.json')))
    f.write(Q/'production-status.json',result)
    brief=f"{result['utc']}: {'COMPLETE' if final else 'RUNNING'}; fleet {result['fleet_extracted_units']}/1767 units; hub row-validated {len(validated)} units / {len(summaries):,} perspectives / {rows:,} rows; errors {len(errors)}, illegal labels {illegal}; available-corpus retention {100*stats['retention']:.4f}%."
    node_lines=[]
    for h,n in nodes.items():
        wall=n['status'].get('wall_seconds',0); rate=n['units']*3600/wall if wall else 0
        remaining=len(f.read(Q/'partition.json')['assignments'][h])-n['units']; eta=remaining/rate if rate else None
        node_lines.append(f"- {h}: {n['units']} assigned units done, {n['launch'].get('workers')} workers, driver {n['launch'].get('pid')}, wall {wall:.1f}s / CPU {n['cpu_seconds']:.1f}s; {rate:.1f} units/hour; ETA {eta:.2f} hours." if eta is not None else f"- {h}: awaiting first complete unit; driver {n['launch'].get('pid')}.")
    block='<!-- C56-PRODUCTION-STATUS -->\n'+brief+'\n\n'+'\n'.join(node_lines)+'\n\nStatus and resume receipts: `qa/fleet-v3b/production-20261008/`; detached labels `'+LABEL+'-extract` (each node) and the hub supervisor recorded in `supervisor.json`. Full retention/final QA remains pending unless COMPLETE.\n<!-- /C56-PRODUCTION-STATUS -->'
    for name in ('PROGRESS.md','FLEET-RESULTS.md'):
        p=D/name; text=p.read_text(); start=text.find('<!-- C56-PRODUCTION-STATUS -->'); end=text.find('<!-- /C56-PRODUCTION-STATUS -->')
        if start>=0: text=text[:start]+block+text[end+len('<!-- /C56-PRODUCTION-STATUS -->'):]
        else: text=text+'\n\n'+block+'\n'
        p.write_text(text)
    print(brief,flush=True)
    mirror_reports()
    return result

def main():
    assert socket.gethostname()=='127x01'
    f.cb.bind_runtime()
    assert f.cb.runtime_manifest()['sha256']=='1ec2c60c254fd9cc5579b163ef994a0e233a942bd97acda864d31d91442d3493'
    lock=(Q/'supervisor.lock').open('a+'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    f.write(Q/'supervisor.json',dict(pid=os.getpid(),utc=f.ex.utc(),label=os.environ.get('C56_JOB_LABEL',LABEL+'-supervise-r2')))
    plan=f.read(Q/'partition.json')
    assert f.read(Q/'equivalence.json')['complete']
    labels_path=Q/'launch-labels.json'
    if not labels_path.exists(): f.write(labels_path,{h:LABEL+'-extract' for h in NODES})
    labels=f.read(labels_path)
    # Launch receipts and partition already exist; preserve immutable assignment across resumes.
    for host in NODES:
        if host!='127x01':
            for name in ('fleet_v3b_production_worker_20261008.py',SELF.name): s.sync(D/'scripts'/name,f'{host}:{D}/scripts/{name}')
            for name in ('partition.json','equivalence.json','mac-base.json'): s.sync(Q/name,f'{host}:{Q}/{name}')
        users=s.remote(host,'who'); cap=16 if users.strip() else plan['workers'][host]
        workers=min(cap,plan['workers'][host])
        print(s.remote(host,shlex.join(['bash',str(s.FLEET),labels[host],*command('extract',workers)])),flush=True)
    validated=set(plan['base_units']); last_mirror=0
    # Base caches were freshly validated on the recovered hub; final audit rechecks hashes.
    with concurrent.futures.ProcessPoolExecutor(4,mp_context=multiprocessing.get_context('spawn')) as pool:
        while True:
            nodes={}; all_new=[]
            for host in NODES:
                n=inventory() if host=='127x01' else json.loads(s.remote(host,shlex.join(command('inventory'))))
                nodes[host]={k:v for k,v in n.items() if k!='files'}
                keys=sorted(set(n['files'])-validated)
                if host!='127x01' and keys:
                    growth=sum(n['files'][k]['bytes']+65536 for k in keys if not (OUT/(k+'.json')).exists())
                    free=shutil.disk_usage(D).free; used=f.ex.disk_bytes()
                    if free-growth < 12*2**30 or used+growth > 7.5*2**30:
                        f.write(Q/'collection-disk-paused.json',dict(utc=f.ex.utc(),free=free,used=used,projected_growth=growth,host=host))
                        raise RuntimeError('Collection disk guard: preserve all data and resume after capacity review')
                    listing=Q/f'collect-{host}.txt'
                    names=[key+suffix for key in keys for suffix in (('.json','.npz') if n['files'][key]['npz_sha256'] else ('.json',))]
                    listing.write_text('\n'.join(names)+'\n')
                    s.sync(f'{host}:{OUT}/',str(OUT)+'/', '--files-from='+str(listing))
                for key in keys:
                    info=n['files'][key]; assert f.cb.file_sha256(OUT/(key+'.json'))==info['sidecar_sha256']
                    if info['npz_sha256']: assert f.cb.file_sha256(OUT/(key+'.npz'))==info['npz_sha256']
                all_new.extend(keys)
                if n['complete'] and host!='127x01': s.sync(f'{host}:{Q}/completed-{host}.json',Q/f'completed-{host}.json')
                state=s.receipt(host,labels[host])
                assert state in ('pending','0'),(host,state)
                assert n['driver_alive'] or n['complete'] or not n['launch'],(host,'driver absent without completion')
            attempted=38134+sum(n['perspectives']+n['errors'] for n in nodes.values())
            failed=sum(n['errors'] for n in nodes.values())
            if failed*200>attempted:
                f.write(Q/'global-failure-stop.json',dict(utc=f.ex.utc(),attempted=attempted,failed=failed))
                for h in NODES[1:]: s.sync(Q/'global-failure-stop.json',f'{h}:{Q}/global-failure-stop.json')
                raise RuntimeError('Global perspective failure limit exceeded')
            for result in pool.map(f.audit_one,all_new):
                assert result['illegal']==0
                validated.add(result['key'])
            complete=all(n['complete'] for n in nodes.values())
            checkpoint(nodes,validated)
            if time.monotonic()-last_mirror>600 or complete:
                print(json.dumps(mirror()),flush=True); last_mirror=time.monotonic()
            if complete: break
            time.sleep(45)
    print(json.dumps(f.finalize(4)),flush=True)
    for host in NODES:
        result=preserve_verify() if host=='127x01' else json.loads(s.remote(host,shlex.join(command('preserve-verify'))))
        f.write(Q/f'v2-final-verification-{host}.json',result)
    print(json.dumps(mirror(final=True)),flush=True)
    f.write(Q/'production-completion.json',dict(utc=f.ex.utc(),complete=True,qa_sha256=f.cb.file_sha256(Q/'final-qa.json'),mirror=f.read(Q/'mirror-127x04.json'),nodes=nodes))
    checkpoint(nodes,validated,final=True)

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='inventory': print(json.dumps(inventory()))
    elif mode=='mirror': print(json.dumps(mirror()))
    elif mode=='preserve-verify': print(json.dumps(preserve_verify()))
    elif mode=='supervise':
        try: main()
        except BaseException:
            f.write(Q/('supervisor-failure-'+os.environ.get('C56_JOB_LABEL','unknown')+'.json'),dict(utc=f.ex.utc(),error=traceback.format_exc()))
            raise
    else: raise ValueError(mode)
