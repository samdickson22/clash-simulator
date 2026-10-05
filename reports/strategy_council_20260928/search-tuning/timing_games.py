"""Post-confirmation whole-game timing; outcomes never enter strength tests."""
from experiment import *


def main():
    complete=json.loads((HERE/'completion.json').read_text())
    assert complete['games_complete']
    probe=subprocess.run(['ps','-p',str(complete['pid']),'-o','pid='],capture_output=True,text=True)
    assert not probe.stdout.strip(), 'wait for the owned driver to exit before isolated timing'
    verify()
    result=json.loads((HERE/'result.json').read_text())
    cfg=Config(**result['winner'])
    assert json.loads((HERE/'confirmation-schedule.json').read_text())[0]['config']==asdict(cfg)
    base=BASE+12000000
    seeds={base,base+1009}
    scan=subprocess.Popen(['rg','--hidden','--no-ignore','--no-heading','--with-filename',
        '--only-matching',r'"[A-Za-z_]*seed"\s*:\s*(?:'+str(base)+'|'+str(base+1009)+r')\b',
        'reports','-g','*.json','-g','*.jsonl'],cwd=ROOT,stdout=subprocess.PIPE,text=True)
    matches=scan.communicate()[0];assert scan.returncode in (0,1)
    assert not matches,matches[:500]
    write(HERE/'timing-games-prereg.json',dict(created=datetime.now(timezone.utc).isoformat(),
        seeds=sorted(seeds),games_per_thread_setting=4,torch_threads=[1,4],
        roles=['holdout','holdout','hog26','hog26'],configuration=asdict(cfg),
        source_sha256=sha(Path(__file__)),experiment_sha256=sha(HERE/'manifest.json'),
        confirmation_manifest_sha256=sha(HERE/'confirmation-manifest.json'),
        scope='Timing only, identical paired seeds across thread settings; no outcomes enter confirmation or selection. Native search remains serial.'))
    out=dict(variants={},native_search_parallel=False,quiet_core_verified=False)
    ctx=Context();r=Resources(ctx)
    for threads in (1,4):
        torch.set_num_threads(threads)
        env,_=reset(ctx,'holdout',base,0,True)
        info=observe(env,0);p=Planner(r,prior(),cfg)
        mask=r.mask_builder.build(PublicActionMaskInput.from_confidence_observation(info.packet))
        p.policy_top(info,mask)  # Discard warmup recurrence before real games.
        before=host();rows=[]
        for game in range(4):
            spec=dict(stage=f'timing-{threads}',role='holdout' if game<2 else 'hog26',
                      style='search',game=game,seed=base)
            rec=play(ctx,r,cfg,spec)
            rec.update(torch_threads=threads,timing_only=True,
                       timing_manifest_sha256=sha(HERE/'timing-games-prereg.json'))
            write(HERE/'timing-games'/f'threads-{threads}-game-{game}.json',rec)
            rows.append(rec)
            progress(f'Descriptive timing: {threads} Torch threads, game {game+1}/4 complete. Outcome excluded from all strength tests.')
        out['variants'][str(threads)]=dict(winner=timing(rows),
            current=timing([dict(timings=[row['timings'][1],[]]) for row in rows]),
            host_before=before,host_after=host())
        write(HERE/'timing-games-summary.json',out)
    progress('Eight descriptive timing games complete. One/four Torch threads; native search remains serial. External host load recorded, no hard core-affinity claim.')


if __name__=='__main__':main()
