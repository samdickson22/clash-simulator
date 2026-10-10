"""Require complete sealed blocks; game-cluster and paired uncertainty, frozen gates."""
import argparse,json,resource,subprocess,time
from pathlib import Path
import numpy as np
from exit_r3.rows import sha,write_json


def bootstrap(values):
    v=np.asarray(values,float);rng=np.random.default_rng(80991013);ix=rng.integers(len(v),size=(5000,len(v)));samples=v[ix].mean(1)
    return dict(value=float(v.mean()),ci95=list(map(float,np.quantile(samples,[.025,.975]))))


def regret(j):
    from offline import intervals
    allrows=[];proof=[]
    for i in range(64):
        p=j/'regret/games'/f'{i:04d}.json';r=json.loads(p.read_text());data=p.with_suffix('.jsonl');assert r['complete'] and r['command_exact'] and r['jsonl_sha256']==sha(data)
        rows=[json.loads(l) for l in data.read_text().splitlines()];assert len(rows)==r['roots'] and all(v['seed']==4503601207370496+i for v in rows)
        allrows.extend(rows);proof.append(dict(index=i,sha256=sha(p),jsonl_sha256=sha(data)))
    assert len(allrows)==8088 and len({r['row'] for r in allrows})==8088
    games=np.array([r['seed'] for r in allrows]);plays=np.array([r['teacher_play'] for r in allrows]);out={}
    for arm in ('R3a','R3b'):
        positive=np.array([r[arm]['positive_regret'] for r in allrows]);signed=np.array([r[arm]['signed_regret'] for r in allrows]);m=dict(mean_positive=intervals(games,positive,np.ones(len(games))),mean_signed=intervals(games,signed,np.ones(len(games))),mean_positive_on_teacher_plays=intervals(games,positive*plays,plays.astype(float)),percentiles={str(p):float(np.quantile(positive,p)) for p in (.5,.9,.95,.99,1.)})
        p=j/'offline'/f'{arm}.json';r=json.loads(p.read_text());r.update(regret=m,stage1_complete=True)
        if m['mean_positive']['value']>.01:r['kill_reasons'].append('mean positive W-score regret >.010')
        r['survives']=not r['kill_reasons'];r['regret_game_proofs']=proof;r['regret_definition']='Best fully completed score among recorded W candidates versus best of legal studenttop8+WAIT/WAIT10, all on the same fresh reconstructed root; all64 command-exact replayed games.'
        write_json(p,r);out[arm]=r
    write_json(j/'stage1-results.json',out)


def qualify(j):
    stage=j/'stage3-sdefault-smoke';blocks=[]
    for i in (0,1):
        p=stage/'blocks'/f'{i:04d}.json';r=json.loads(p.read_text());assert r['complete'];blocks.append(dict(index=i,sha256=sha(p)))
        for spec in r['cases']:
            case=stage/'cases'/f"sdefault-{spec['arm']}-{i:04d}.json";assert sha(case)==spec['sha256'];v=json.loads(case.read_text());assert v['smoke'] and v['terminal'] and v['seed']==4503601917370496+i and v['smoke_checks']['timer_calls']>0
            if spec['arm'] not in ('C-v1','K0'):assert v['smoke_checks']['student_calls']>0
    write_json(j/'wrapper-qualification.json',dict(passed=True,excluded_smoke=True,blocks=blocks,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),evaluation_freeze_sha256=sha(j/'evaluation-freeze.json')))


def reporting(j):
    stage=j/'stage3-sdefault';losses={};counts={};arm_list=None;h=json.loads((j/'stage3-sdefault-addendum.json').read_text())
    for i in range(600):
        block=json.loads((stage/'blocks'/f'{i:04d}.json').read_text());assert block['complete'] and block['index']==i
        if arm_list is None:arm_list=block['arms']
        assert block['arms']==arm_list and block['arm_order']==arm_list[i%len(arm_list):]+arm_list[:i%len(arm_list)]
        assert block['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json') and not block['smoke']
        assert len(block['cases'])==len(arm_list) and [v['arm'] for v in block['cases']]==block['arm_order']
        assert block['context']['host'] in ('127x01','127x03') and len(block['context']['affinity'])==1
        assert block['context']['nice']==10 and block['context']['scheduler']==0
        pair_keys=[]
        for spec in block['cases']:
            p=stage/'cases'/f"sdefault-{spec['arm']}-{i:04d}.json";assert sha(p)==spec['sha256'];case=json.loads(p.read_text());assert not case['smoke'] and case['terminal'] and case['seed']==4503601907370496+i
            assert case['search_ab']['host'].split('.')[0]==block['context']['host'] and case['search_ab']['worker_affinity']==block['context']['affinity'] and case['scheduler']=='SCHED_OTHER' and case['nice']==10
            assert (case['mode'],case['arm'],case['index'],case['seat'])==('sdefault',spec['arm'],i,i%2)
            assert case['freeze_sha256']==sha(j/'freeze.json') and case['harness_sha256']==sha(j/'stage3-sdefault-addendum.json')
            assert case['adapter_sha256']==sha(j/'frozen-x/k_stage3_sdefault.py') and case['native_sha256']==h['native_sha256']
            assert case['r3_adapter_sha256']==sha(j/'eval-ops/game.py') and case['r3_proposals_sha256']==sha(j/'eval-ops/proposals.py')
            assert case['threads']==1 and case['coarse_horizon']==160 and case['opponent']=='v1-policy' and case['own_v1_poll']=='released v1'
            source='v1_polled' if spec['arm']=='C-v1' else 'K0_frozen' if spec['arm']=='K0' else 'student_argmax'
            assert case['default_source']==source and case['loss'] in (0,1)
            raw=stage/'k-raw'/spec['arm']/'games'/f"sim-{i:04d}-d27-{spec['arm']}.json"
            assert sha(raw)==case['raw_game_sha256'];record=json.loads(raw.read_text())
            assert record['metadata']['deadline_seconds']==.2 and record['metadata']['return_reserve_seconds']==.008
            for field in ('threads','coarse_horizon','default_source'):assert record[field]==case[field] and record['metadata'][field]==case[field]
            if spec['arm'] not in ('C-v1','K0'):
                off=json.loads((j/'offline'/f"{spec['arm']}.json").read_text());assert off['survives'] and case['student_checkpoint_sha256']==off['checkpoint_sha256']
                assert case['calibration_sha256']==sha(j/'offline'/f"{spec['arm']}-calibration.json")
            pair_keys.append((case['seed'],case['seat'],case['own_deck'],case['opponent_deck']))
            arm=spec['arm'];losses.setdefault(arm,[]).append(case['loss']);counts.setdefault(arm,dict(wins=0,losses=0,draws=0,deadline_calls=0,deadline_hits=0,wall_overruns=0,default_uses=0,proposal_seconds=[]))
            c=counts[arm];c['wins']+=case['win'];c['losses']+=case['loss'];c['draws']+=case['draw'];c['proposal_seconds'].extend(case['proposal_seconds'])
            for d in case['search_ab']['deadline_stats']:
                c['deadline_calls']+=1;c['deadline_hits']+=bool(d['hit']);c['wall_overruns']+=bool(d.get('wall_overrun'));c['default_uses']+=bool(d.get('default_used',d.get('fallback')))
        assert all(k==pair_keys[0] for k in pair_keys),'unpaired seed/seat/decks'
    assert all(len(v)==600 for v in losses.values());result={}
    for arm in arm_list:
        c=counts[arm];latencies=np.asarray(c.pop('proposal_seconds'));c['proposal_latency_median']=float(np.median(latencies)) if len(latencies) else None;c['proposal_latency_p95']=float(np.quantile(latencies,.95)) if len(latencies) else None
        r=dict(arm=arm,cases=600,terminal=600,loss=bootstrap(losses[arm]),counts=c)
        if arm not in ('C-v1','K0'):
            r.update(paired_loss_change_vs_Cv1=bootstrap(np.array(losses[arm])-losses['C-v1']),paired_loss_change_vs_K0=bootstrap(np.array(losses[arm])-losses['K0']))
            r['survives']=r['paired_loss_change_vs_Cv1']['ci95'][1]<0;r['kill_reason']=None if r['survives'] else 'upper paired95%CI(lossR3-lossC-v1)>=0'
        result[arm]=r
    write_json(j/'stage2-results.json',dict(arms=result,seed_base=4503601907370496,paired_seeds=600,bootstrap_seed=80991013,bootstrap_resamples=5000,lane='exploration; no multiplicity adjustment',evaluation_freeze_sha256=sha(j/'evaluation-freeze.json')))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--mode',choices=('regret','qualify','reporting'),required=True);a=p.parse_args();j=Path(a.job);start=time.monotonic()
    {'regret':regret,'qualify':qualify,'reporting':reporting}[a.mode](j)
    u=resource.getrusage(resource.RUSAGE_SELF);write_json(j/f'reduce-{a.mode}-meter.json',dict(cpu_seconds=u.ru_utime+u.ru_stime,wall_seconds=time.monotonic()-start,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()))
