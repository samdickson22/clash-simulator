"""Bounded detached orchestration, complete-stage selection and reporting."""
from experiment import *
import math
import traceback


def jobs_for(configs,stage,n):
    return [dict(config=asdict(c),spec=s) for s in stage_specs(stage,n) for c in configs]


def run_jobs(jobs,label):
    schedule=HERE/f'{label}-schedule.json';write(schedule,jobs)
    processes=[]
    for i in range(3):
        cmd=[str(ROOT/'reports/strategy_council_20260928/pilot/detach.sh'),
             str(HERE/'logs'/f'{label}-{i}.log'),'nice','-n','10',
             str(ROOT/'.venv/bin/python'),'-B',str(HERE/'experiment.py'),'worker',
             '--schedule',str(schedule),'--worker',str(i)]
        pid=int(subprocess.check_output(cmd,cwd=ROOT,text=True).strip())
        processes.append(pid)
    write(HERE/f'{label}-launch.json',dict(pids=processes,started=datetime.now(timezone.utc).isoformat(),host=host()))
    progress(f'{label} launched owned worker PIDs {processes}; {len(jobs)} games planned.')
    while True:
        running=[]
        for pid in processes:
            try:os.kill(pid,0);running.append(pid)
            except ProcessLookupError:pass
        complete=sum((HERE/'games'/str(j['spec']['stage'])/(key(Config(**j['config']),j['spec'])+'.json')).exists() for j in jobs)
        write(HERE/'status.json',dict(stage=label,complete=complete,planned=len(jobs),running=running,updated=datetime.now(timezone.utc).isoformat()))
        if not running:break
        time.sleep(20)
    assert complete==len(jobs),f'{label}: only {complete}/{len(jobs)} games; inspect logs'
    verify();progress(f'{label} complete: {complete}/{len(jobs)} games; all owned workers exited.')


def records(jobs):
    out=[]
    for j in jobs:
        c=Config(**j['config']);s=j['spec'];p=HERE/'games'/str(s['stage'])/(key(c,s)+'.json')
        rec=json.loads(p.read_text())
        assert rec['spec']==s and rec['config']==asdict(c)
        assert rec['manifest_sha256']==sha(HERE/'manifest.json')
        if s['stage']=='confirm':
            assert rec['confirmation_manifest_sha256']==sha(HERE/'confirmation-manifest.json')
        assert rec['matchup_seed']==s['seed']+s['game']//2*1009
        assert rec['seat']==s['game']%2 and not any(rec['failed'])
        out.append(rec)
    grouped=defaultdict(list)
    for rec in out:
        s=rec['spec'];grouped[(rec['config']['name'],s['role'],s['style'],s.get('which'),rec['matchup_seed'])].append(rec)
    for pair in grouped.values():
        assert len(pair)==2 and {r['seat'] for r in pair}=={0,1}
        if pair[0]['spec']['style']=='search':assert pair[0]['world_decks']==pair[1]['world_decks']
    return out


def report(result):
    lines=['# Search tuning results','',f"Status: {result['status']}",'',
           '| Stage | Candidate | Games | Score | Hog26 score | Search core-s | Decision wall p99 | Wall max | Overruns |',
           '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for stage,rows in result.get('stages',{}).items():
        for x in rows:
            t=x['timing'];lines.append(f"| {stage} | {x['name']} | {x['all']['n']} | {x['all']['score']:.4f} | {x['hog26']['score']:.4f} | {t['search_cpu_mean']:.5f} | {t['wall_p99']:.5f} | {t['wall_max']:.5f} | {t['overruns']} |")
    if 'confirmation' in result:
        c=result['confirmation'];lines += ['',f"Confirmation: {c['verdict']}",f"H2H: {c['h2h']}",f"Hog26 H2H: {c['hog26']}"]
        for role,x in c['scripts'].items():lines += [f"{role} scripts: {x}"]
    lines += ['', 'Initial timing and concurrent host load: benchmark.json. Full-game timings are stored per decision in receipts. All tables require complete seat pairs.',
              'Quiet-core winner timing and four-thread descriptive timing are required before a new deployment recommendation. No confirmation result is inferred from a tournament score.']
    (HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n');write(HERE/'result.json',result)


def prereg(winner):
    specs=confirmation_specs();jobs=[dict(config=asdict(CURRENT if s['which']=='current' else winner),spec=s) for s in specs]
    if (HERE/'confirmation-manifest.json').exists():
        pins=json.loads((HERE/'confirmation-manifest.json').read_text())
        assert pins['prereg_sha256']==sha(HERE/'PREREG.md')
        assert pins['schedule_sha256']==sha(HERE/'confirmation-schedule.json')
        assert pins['experiment_sha256']==sha(HERE/'manifest.json')
        assert json.loads((HERE/'confirmation-schedule.json').read_text())==jobs
        return jobs
    write(HERE/'confirmation-schedule.json',jobs)
    text=f'''# Search tuning confirmation preregistration

Frozen UTC {datetime.now(timezone.utc).isoformat()}, before any confirmation game.
Winner: {json.dumps(asdict(winner),sort_keys=True)}
Current: {json.dumps(asdict(CURRENT),sort_keys=True)}
Experiment manifest SHA256: {sha(HERE/'manifest.json')}
Checkpoint SHA256: {sha(CHECKPOINT)}
Confirmation schedule SHA256: {sha(HERE/'confirmation-schedule.json')}

The 256 H2H games use seed {BASE+3000000} plus pair index times 1009, paired world decks and swapped controllers. There are 86 Hog26 games and 170 holdout games. Score is win 1, draw .5, loss 0. Primary PASS requires score >= .55 and lower 95% matchup-cluster bootstrap bound > .50. Bootstrap uses copied statistics.boot, 10,000 resamples and seed 20261001, retaining both seats. No optional stopping, outcome exclusions, retuning or second confirmation attempt.

Secondary winner/current script comparisons use identical seeds/decks, each 128 holdout games across balanced/pressure/defense 44/42/42 and each 64 Hog26 games across 22/22/20. Report every style and role. A pooled role drop greater than .05 blocks recommendation. Head-to-head statistical pass is reported separately from secondary and latency gates. Any candidate wall decision > .25 seconds blocks one-core deployment recommendation. Warmup precedes every worker's games, with recurrence reset for every game. Report full p99/max and concurrent load; remeasure the winner without concurrent tuning workers. Four-thread results are descriptive only.

All 640 games and complete pairs must be present for a final verdict. Source/data/native/checkpoint pins are verified for every receipt. Unexpected failures retain their artifacts and block completion. Seed audit precedes all experiments; confirmation seeds are disjoint from tournament and probe seeds. No confirmation outcome has been observed at registration.
'''
    (HERE/'PREREG.md').write_text(text)
    write(HERE/'confirmation-manifest.json',dict(prereg_sha256=sha(HERE/'PREREG.md'),schedule_sha256=sha(HERE/'confirmation-schedule.json'),experiment_sha256=sha(HERE/'manifest.json')))
    progress(f'Confirmation preregistered for {winner.name}; no confirmation games started.')
    return jobs


def confirmation(rows):
    h=[r for r in rows if r['spec']['style']=='search'];hstat=summary(h)
    scripts={}
    for role in ('holdout','hog26'):
        groups={who:[r for r in rows if r['spec']['style']!='search' and r['spec']['role']==role and r['spec']['which']==who] for who in ('winner','current')}
        a,b=groups.values()
        for x,y in zip(a,b):
            assert (x['matchup_seed'],x['seat'],x['world_decks'])==(y['matchup_seed'],y['seat'],y['world_decks'])
        scripts[role]={who:summary(group) for who,group in groups.items()}
        scripts[role]['drop']=scripts[role]['current']['score']-scripts[role]['winner']['score']
        scripts[role]['by_style']={style:{who:summary([r for r in group if r['spec']['style']==style]) for who,group in groups.items()} for style in STYLES}
    primary=hstat['score']>=.55 and hstat['ci95'][0]>.5
    return dict(verdict='PASS' if primary else 'FAIL',h2h=hstat,
                hog26=summary([r for r in h if r['spec']['role']=='hog26']),scripts=scripts,
                secondary_pass=all(x['drop']<=.05 for x in scripts.values()),
                timing=timing([r for r in rows if r['spec']['which']=='winner']))


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    verify();assert json.loads((HERE/'validation.json').read_text())['passed']
    bench=json.loads((HERE/'benchmark.json').read_text())
    candidates=[c for c in configurations() if bench['configs'][c.name]['eligible']]
    result=dict(status='tournament running',stages={})
    for stage,n in ((1,48),(2,96),(3,192)):
        assert len(candidates)>=2,'fewer than two latency-eligible candidates'
        jobs=jobs_for(candidates,stage,n);run_jobs(jobs,f'stage{stage}');rows=records(jobs)
        table=[]
        for cfg in candidates:
            group=[r for r in rows if r['config']['name']==cfg.name]
            table.append(dict(name=cfg.name,all=summary(group),hog26=summary([r for r in group if r['spec']['role']=='hog26']),timing=timing(group)))
        table.sort(key=lambda x:(-x['all']['score'],-x['hog26']['score'],x['name']))
        result['stages'][stage]=table;report(result)
        eligible=[x for x in table if x['timing']['overruns']==0]
        count=max(2,len(eligible)//2) if stage==1 else min(3,max(2,len(eligible)//2)) if stage==2 else 1
        names=[x['name'] for x in eligible[:count]]
        candidates=[next(c for c in candidates if c.name==name) for name in names]
        progress(f'Stage {stage} ranked. Advancing {names}.')
    winner=candidates[0];result['winner']=asdict(winner);result['status']='confirmation running';report(result)
    jobs=prereg(winner);run_jobs(jobs,'confirmation');rows=records(jobs)
    result['confirmation']=confirmation(rows);result['status']='games complete; winner timing pending';report(result)
    from winner_timing import measure
    result['winner_timing']=measure(winner)
    result['status']='games and isolated-worker timing complete; quiet-core verification unavailable'
    report(result)
    write(HERE/'completion.json',dict(games_complete=True,timing_complete=True,quiet_core_verified=False,pid=os.getpid(),created=datetime.now(timezone.utc).isoformat()))
    progress('Tournament, confirmation and isolated-worker one/four-thread timing complete. No verified quiet-core measurement; external processes untouched.')


if __name__=='__main__':
    try:main()
    except BaseException:
        write(HERE/'error.json',dict(traceback=traceback.format_exc(),pid=os.getpid()))
        progress('ERROR: see error.json. No success claim.');raise
