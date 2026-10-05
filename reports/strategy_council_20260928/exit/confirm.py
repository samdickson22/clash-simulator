"""Confirmation and conditional ExIt, reusing frozen collection/fit/search helpers."""
import argparse
import subprocess
import time
import traceback
import evaluate
from common import *
from analyze import summary

OUT = HERE/'confirm'
BASE = 610000003

def specs(iteration):
    base = BASE+(iteration-1)*10000000
    for g in range(256 if iteration==1 else 128):
        yield dict(mode='h2h',which='student',role='hog26' if (g//2)%3==0 else 'holdout',
                   style='search',game=g,seed=base)
    for role, offset, counts in [('holdout',1000000,(44,42,42) if iteration==1 else (22,22,20)),
                                 ('hog26',5000000,(22,22,20) if iteration==1 else (0,0,0))]:
        for j,(style,n) in enumerate(zip(STYLES,counts)):
            for g in range(n):
                for which in ('initial','student'):
                    yield dict(mode='scripts',which=which,role=role,style=style,game=g,seed=base+offset+j*1000000)

def checkpoints(iteration):
    return dict(initial=CHECKPOINT if iteration==1 else HERE/f'it{iteration-1}'/'student.pt',
                student=HERE/f'it{iteration}'/'student.pt')

def reset_pair(ctx,role,seed,seat,*,symmetric=False):
    if not symmetric:return reset(ctx,role,seed,seat)
    env=ctx.envs(role,seed)[seat]
    a,b=ctx.pools(role)
    decks=cl_eval._sample_paired_ordered_decks(a,a if role=='hog26' else b,matchup_seed=seed)
    with maybe_silence_stdio(True):env.reset(seed=seed,ordered_decks=decks)
    return env,decks

def verify_confirm():
    verify()
    manifest=json.loads((OUT/'manifest.json').read_text())
    for rel,expected in manifest['sha256'].items():
        assert sha(ROOT/rel)==expected, 'confirmation dependency drift: '+rel
    return sha(OUT/'manifest.json')

def freeze():
    verify();audit=json.loads((OUT/'seed-audit.json').read_text());assert audit['passed'] and not audit['overlap']
    assert not (OUT/'manifest.json').exists()
    files=[HERE/'PREREG-CONFIRM.md', HERE/'manifest.json', HERE/'confirm.py', HERE/'confirm_seed_audit.py',
           HERE/'test_confirm.py', OUT/'seed-audit.json',*checkpoints(1).values()]
    write_json(OUT/'manifest.json',dict(created=datetime.now(timezone.utc).isoformat(),
        sha256={str(p.relative_to(ROOT)):sha(p) for p in files}))
    progress('preregistered; no games launched',[],[])

def game_path(iteration,spec):return OUT/f'it{iteration}'/'games'/(evaluate.identifier(spec)+'.json')

def validate_record(rec,spec,pins,manifest):
    assert rec['spec']==spec
    assert rec['confirmation_manifest_sha256']==manifest and rec['checkpoint_sha256']==pins
    assert rec['matchup_seed']==spec['seed']+(spec['game']//2)*1009
    assert rec['seat']==spec['game']%2
    assert rec['score']=={'win':1.,'draw':.5,'loss':0.}[rec['outcome']]
    assert 0 < rec['ticks'] <= 6010

def worker(iteration,index):
    manifest=verify_confirm(); paths=checkpoints(iteration);pins={n:sha(p) for n,p in paths.items()}
    contexts={n:Context(p) for n,p in paths.items()};resources={n:Resources(c) for n,c in contexts.items()}
    evaluate.reset=reset_pair
    for spec in list(specs(iteration))[index::3]:
        path=game_path(iteration,spec)
        verify_confirm()
        assert all(sha(paths[n])==pin for n,pin in pins.items())
        if path.exists():validate_record(json.loads(path.read_text()),spec,pins,manifest);continue
        rec=evaluate.search_game(contexts,resources,spec)
        rec.update(confirmation_manifest_sha256=manifest,checkpoint_sha256=pins,pid=os.getpid())
        verify_confirm();validate_record(rec,spec,pins,manifest)
        write_json(path,rec);log(dict(id=evaluate.identifier(spec),wall_s=rec['wall_s']))

def gates(iteration,h2h,drop):
    primary=h2h['rate'] >= (.55 if iteration==1 else .5) and h2h['ci95'][0] > (.5 if iteration==1 else .45)
    secondary=drop['rate']<=.05 and (iteration!=1 or drop['ci95'][1]<.10)
    return dict(primary=bool(primary),secondary=bool(secondary),accepted=bool(primary and secondary))

def analyze_confirmation(iteration):
    manifest=verify_confirm();pins={n:sha(p) for n,p in checkpoints(iteration).items()};records=[]
    for spec in specs(iteration):
        rec=json.loads(game_path(iteration,spec).read_text());validate_record(rec,spec,pins,manifest);records.append(rec)
    h2h=[r for r in records if r['spec']['mode']=='h2h']
    for a,b in zip(h2h[::2],h2h[1::2]):
        assert a['matchup_seed']==b['matchup_seed'] and a['world_decks']==b['world_decks'] and (a['seat'],b['seat'])==(0,1)
    result=dict(iteration=iteration,h2h=summary([r['score'] for r in h2h]),
        h2h_by_role={role:summary([r['score'] for r in h2h if r['spec']['role']==role]) for role in ('holdout','hog26')},scripts={})
    for role in ('holdout','hog26') if iteration==1 else ('holdout',):
        who={name:[r for r in records if r['spec']['mode']=='scripts' and r['spec']['role']==role and r['spec']['which']==name] for name in ('initial','student')}
        a,b=who.values()
        for x,y in zip(a,b):
            assert all(x[k]==y[k] for k in ('matchup_seed','seat','world_decks'))
            assert {k:v for k,v in x['spec'].items() if k!='which'}=={k:v for k,v in y['spec'].items() if k!='which'}
        assert len(a)==len(b)==(128 if role=='holdout' and iteration==1 else 64)
        result['scripts'][role]={n:summary([r['score'] for r in rows]) for n,rows in who.items()}
        result['scripts'][role]['drop']=summary([x['score']-y['score'] for x,y in zip(a,b)])
        result['scripts'][role]['styles']={style:{n:summary([r['score'] for r in rows if r['spec']['style']==style]) for n,rows in who.items()} for style in STYLES}
    result.update(gates(iteration,result['h2h'],result['scripts']['holdout']['drop']))
    result.update(games=len(records),checkpoint_sha256=pins,confirmation_manifest_sha256=manifest,
        failed_plays=sum(r['failed_plays'] for r in records),decision_wall_max=max(r['decision_wall_max'] for r in records),
        timing_scope='Candidate planner only, unchanged evaluate.py instrumentation',bytes=budget())
    write_json(OUT/f'it{iteration}'/'result.json',result);report();return result

def report():
    results=[json.loads(p.read_text()) for p in sorted(OUT.glob('it*/result.json'))]
    def fmt(v):return f"{v['score']:g}/{v['games']} = {v['rate']:.6f}, 95% CI [{v['ci95'][0]:.6f}, {v['ci95'][1]:.6f}]"
    lines=['# Proposal-network confirmation','','Preregistered in PREREG-CONFIRM.md. Intervals resample complete matchup pairs.']
    best=CHECKPOINT
    for r in results:
        lines+=['',f"## {'Confirmation' if r['iteration']==1 else 'Iteration '+str(r['iteration'])}: {'PASS' if r['accepted'] else 'FAIL'}",'',
                'Student search head-to-head: '+fmt(r['h2h']),f"Primary gate: {r['primary']}; required script gate: {r['secondary']}."]
        for role,v in r['h2h_by_role'].items():lines.append(f'H2H {role}: '+fmt(v))
        for role,c in r['scripts'].items():
            lines+=['',f'{role} scripts, previous: '+fmt(c['initial']),f'{role} scripts, student: '+fmt(c['student'])]
            d=c['drop'];lines.append(f"Paired drop, previous minus student: {d['rate']:.6f}, 95% CI [{d['ci95'][0]:.6f}, {d['ci95'][1]:.6f}].")
            for style,v in c['styles'].items():lines.append(f"{style}: previous {v['initial']['score']:g}/{v['initial']['games']}, student {v['student']['score']:g}/{v['student']['games']}.")
        lines+=['',f"All {r['games']} planned games included. Candidate rejected plays: {r['failed_plays']}. Maximum measured candidate decision wall time: {r['decision_wall_max']:.6f}s. Timing does not include the opposing H2H planner."]
        if r['accepted']:best=HERE/f"it{r['iteration']}"/'student.pt'
        if r['iteration']>1:
            fit=json.loads((HERE/f"it{r['iteration']}"/'fit.json').read_text())
            lines.append(f"Fit: {fit['updates']} updates; held-out before/after: {fit['curves'][0]['heldout']} / {fit['curves'][-1]['heldout']}.")
    lines+=['','Policy-alone is descriptive and was not rerun: initial 83/192, iteration-1 student 64/192; Hog26 32/96 and 18/96.', '', 'Recommended proposer: '+str(best)]
    if results and not results[-1]['accepted']:lines+=['','Stopped at the first failed gate. No later iteration is authorized by this protocol. Retain the last accepted proposer; consider a separately preregistered change before another experiment.']
    (HERE/'CONFIRM.md').write_text('\n'.join(lines)+'\n')

def progress(stage,pids,commands):
    old=HERE/'PROGRESS.md'
    original=old.read_text().split('\n## Proposal-network confirmation')[0]
    counts={i:len(list((OUT/f'it{i}'/'games').glob('*.json'))) for i in (1,2,3)}
    text=original+'\n## Proposal-network confirmation\n\n'+f'Updated UTC: {datetime.now(timezone.utc).isoformat()}\nActive confirmation stage: {stage}\nDriver PID: {os.getpid()}\nOwned running child PIDs: {pids}\nGame receipts: {counts}\n'
    text+='Original iteration-1 status above is historical. Current confirmation status is this section.\n'
    text+='\n'.join('Command: '+' '.join(c) for c in commands)+'\n'
    tmp=HERE/'PROGRESS.confirm.tmp.md';tmp.write_text(text);tmp.replace(old)

def run(stage,commands):
    processes=[];handles=[]
    try:
        for j,cmd in enumerate(commands):
            f=(OUT/f'{stage}-{j}.log').open('a');handles.append(f)
            processes.append(subprocess.Popen(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT))
        write_json(OUT/f'{stage}-launch.json',dict(stage=stage,pids=[p.pid for p in processes],commands=commands))
        while any(p.poll() is None for p in processes):
            progress(stage,[p.pid for p in processes if p.poll() is None],commands);time.sleep(10)
        codes=[p.returncode for p in processes]
        write_json(OUT/f'{stage}-completion.json',dict(pids=[p.pid for p in processes],commands=commands,returncodes=codes))
        if any(codes):raise RuntimeError(f'{stage}: {codes}; see logs')
        verify_confirm();progress(stage+' complete',[],[])
    finally:
        for p in processes:p.wait()
        for f in handles:f.close()

def cmd(script,*args):return [str(ROOT/'.venv/bin/python'),'-B',str(HERE/script),*map(str,args)]

def driver():
    verify_confirm();assert os.getpriority(os.PRIO_PROCESS,0)>=10
    for iteration in (1,2,3):
        existing=OUT/f'it{iteration}'/'result.json'
        if existing.exists():
            if not json.loads(existing.read_text())['accepted']:break
            continue
        if iteration>1:
            assert json.loads((OUT/f'it{iteration-1}'/'result.json').read_text())['accepted']
            run(f'it{iteration}-collect',[cmd('collect.py','--iteration',iteration,'--worker',w,'--workers',3) for w in range(3)])
            if not (HERE/f'it{iteration}'/'fit.json').exists():run(f'it{iteration}-fit',[cmd('fit.py','--iteration',iteration)])
        run(f'it{iteration}-evaluate',[cmd('confirm.py','worker','--iteration',iteration,'--worker',w) for w in range(3)])
        r=analyze_confirmation(iteration);progress(f"iteration {iteration} {'PASS' if r['accepted'] else 'FAIL'}",[],[])
        if not r['accepted']:break
    verify_confirm();report();write_json(OUT/'completion.json',dict(complete=True,pid=os.getpid(),created=datetime.now(timezone.utc).isoformat(),bytes=budget()))
    progress('COMPLETE; see CONFIRM.md',[],[])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','driver','worker','analyze']);p.add_argument('--iteration',type=int,default=1);p.add_argument('--worker',type=int,default=0);a=p.parse_args()
    try:
        if a.mode=='freeze':freeze()
        elif a.mode=='driver':driver()
        elif a.mode=='worker':worker(a.iteration,a.worker)
        else:analyze_confirmation(a.iteration)
    except BaseException:
        if a.mode=='driver':
            write_json(OUT/'error.json',dict(pid=os.getpid(),traceback=traceback.format_exc()))
            progress('ERROR; see confirm/error.json',[],[])
        raise
