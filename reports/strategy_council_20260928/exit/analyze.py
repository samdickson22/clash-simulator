"""Paired acceptance statistics and per-iteration report."""
from common import *
from evaluate import search_specs,identifier


def summary(scores):
    a=np.asarray(scores,float);assert len(a)%2==0
    pairs=a.reshape(-1,2).mean(-1);rng=np.random.default_rng(770061)
    boot=pairs[rng.integers(0,len(pairs),(10000,len(pairs)))].mean(-1)
    return dict(games=len(a),score=float(a.sum()),rate=float(a.mean()),ci95=np.quantile(boot,[.025,.975]).tolist())

def paired_test(diffs):
    pairs=np.asarray(diffs).reshape(-1,2).mean(-1)
    units=np.rint(pairs*4).astype(int);assert np.allclose(units,pairs*4)
    counts={0:1}
    for mag in np.abs(units):
        nxt={}
        for v,n in counts.items():
            for sign in (-1,1):nxt[v+sign*int(mag)]=nxt.get(v+sign*int(mag),0)+n
        counts=nxt
    p=sum(n for v,n in counts.items() if v<=int(units.sum()))/2**len(units)
    return dict(delta=float(pairs.mean()),one_sided_drop_p=p,pairs=len(pairs))

def analyze(iteration):
    verify();out=folder(iteration);pol={};diffs=[];cells=[]
    for role in ('holdout','hog26'):
        by={name:[] for name in ('initial','student')}
        for style in STYLES:
            name=f'{role}-nominal-{style}'
            a,b=[json.loads((HERE/'evaluation'/f'exit-it{iteration}-{who}'/f'{name}.games.json').read_text()) for who in by]
            assert len(a)==len(b)==32
            for x,y in zip(a,b):
                for key in ('game','matchup','matchup_seed','candidate_player','candidate_deck','opponent_deck','candidate_card_levels','opponent_card_levels'):
                    assert x[key]==y[key],(name,key)
                assert x['terminated'] and y['terminated'] and not x['truncated'] and not y['truncated']
            scores=[[{'win':1.,'draw':.5,'loss':0.}[x['outcome']] for x in rows] for rows in (a,b)]
            for who,s in zip(by,scores):by[who].extend(s)
            diffs.extend(np.subtract(scores[1],scores[0]).tolist())
            cells.append(dict(cell=name,initial=summary(scores[0]),student=summary(scores[1])))
        pol[role]={who:summary(s) for who,s in by.items()}
    pol['all']={who:dict(games=192,score=sum(pol[r][who]['score'] for r in ('holdout','hog26')),
        rate=sum(pol[r][who]['score'] for r in ('holdout','hog26'))/192) for who in ('initial','student')}
    test=paired_test(diffs)
    search={};h2h=[]
    for role in ('holdout','hog26'):
        search[role]={}
        for mode,who in [('scripts','initial'),('scripts','student'),('h2h','student')]:
            specs=[s for s in search_specs(iteration) if s['role']==role and s['mode']==mode and s['which']==who]
            records=[json.loads((out/'search'/f'{identifier(s)}.json').read_text()) for s in specs]
            assert len(records)==32
            scores=[r['score'] for r in records];search[role][f'{mode}_{who}']=summary(scores)
            search[role][f'{mode}_{who}']['failed_plays']=sum(r['failed_plays'] for r in records)
            if mode=='h2h':h2h.extend(scores)
    search['h2h_all']=summary(h2h)
    search['scripts_all']={who:dict(games=64,score=sum(search[r][f'scripts_{who}']['score'] for r in ('holdout','hog26')),
        rate=sum(search[r][f'scripts_{who}']['score'] for r in ('holdout','hog26'))/64) for who in ('initial','student')}
    accepted=test['one_sided_drop_p']>.1 and search['h2h_all']['rate']>=.5
    result=dict(iteration=iteration,policy=pol,cells=cells,paired=test,search=search,accepted=accepted,
        targets=json.loads((out/'targets.json').read_text()),fit=json.loads((out/'fit.json').read_text()))
    write_json(out/'result.json',result);report();log(dict(iteration=iteration,accepted=accepted,policy=pol['all'],paired=test,h2h=search['h2h_all']))
    return accepted

def report():
    results=[json.loads(p.read_text()) for p in sorted(HERE.glob('it*/result.json'))]
    lines=['# ExIt results','','Scores count wins as 1 and draws as 0.5. Intervals resample complete seat pairs. The historical 88/192 is not reused as a fresh control.','',
        '| Iteration | Policy initial / student, 192 games | Policy Hog26 initial / student, 96 games | Paired drop p | Search H2H, 64 games | Accepted |',
        '|---|---|---|---:|---|---|']
    for r in results:
        p=r['policy'];s=r['search'];lines.append(f"| {r['iteration']} | {p['all']['initial']['score']:g} / {p['all']['student']['score']:g} | {p['hog26']['initial']['score']:g} / {p['hog26']['student']['score']:g} | {r['paired']['one_sided_drop_p']:.5g} | {s['h2h_all']['score']:g}/64 | {r['accepted']} |")
    for r in results:
        t=r['targets'];lines.extend(['',f"## Iteration {r['iteration']}",'',f"Tau {t['tau']:.8g}; raw-gap normalizer {t['weight_normalizer']:.8g}. Training median entropy {t['groups']['training']['entropy_quantiles'][2]:.6g} nat. No hard margin filter.",
            f"Weight quantiles at {QUANTILES_TEXT}: {t['groups']['all']['weight_quantiles']}. Zero-weight fraction {t['groups']['all']['zero_weight_fraction']:.4%}; effective sample size {t['groups']['all']['effective_sample_size']:.1f}.",'',
            '| Role | Initial search vs scripts | New search vs scripts | New vs initial search H2H |','|---|---|---|---|'])
        for role in ('holdout','hog26'):
            def fmt(k):
                x=r['search'][role][k];return f"{x['score']:g}/{x['games']} = {x['rate']:.3f} [{x['ci95'][0]:.3f}, {x['ci95'][1]:.3f}]"
            lines.append(f"| {role} | {fmt('scripts_initial')} | {fmt('scripts_student')} | {fmt('h2h_student')} |")
        before,after=r['fit']['curves'][0]['heldout'],r['fit']['curves'][-1]['heldout']
        lines+=['',f"Held-out candidate CE {before['all']['ce']:.6g} -> {after['all']['ce']:.6g}; weighted CE {before['all']['weighted_ce']:.6g} -> {after['all']['weighted_ce']:.6g}; final KL {after['all']['kl']:.6g}. Full-prefix BC, one epoch."]
        lines+=['',f"Hog26 held-out CE {before['hog26']['ce']:.6g} -> {after['hog26']['ce']:.6g}; final KL {after['hog26']['kl']:.6g}."]
        failures=sum(r['search'][role][key]['failed_plays'] for role in ('holdout','hog26') for key in ('scripts_initial','scripts_student','h2h_student'))
        lines+=['',f'Engine-rejected search-player plays: {failures}. All games remain in the reported outcomes.']
        collection_path=folder(r['iteration'])/'collection-summary.json'
        if collection_path.exists():
            c=json.loads(collection_path.read_text())
            lines+=['','| Collection deck | Games | Search-player score | Searched decisions | Rejected plays |','|---|---:|---:|---:|---:|']
            for role in ('training','hog26'):
                x=c[role];lines.append(f"| {role} | {x['games']} | {x['score']:g}/{x['games']} | {x['searched']} | {x['rejected_plays']} |")
        if (folder(r['iteration'])/'checkpoint-provenance.json').exists():
            lines+=['','Checkpoint provenance: checkpoint-provenance.json binds the complete corpus and actual soft-target objective to the evaluated checkpoint hash. The generic serializer fields imitation.corpus_samples and imitation.objective retain a last-game count and its default exact label. The sidecar states the actual fit; checkpoint bytes and policy tensors remain as evaluated.']
    if results:
        accepted=[r['iteration'] for r in results if r['accepted']]
        lines+=['',f'Accepted iterations: {accepted}.', 'Recommendation: retain the latest accepted policy for further validation.' if accepted else 'Recommendation: retain the initial s2902 policy; this ExIt run did not meet acceptance.']
    else:lines+=['','No iteration has completed evaluation.']
    lines+=['','Implementation and artifacts are confined to exit/. Public planner/support/derived-state files are copies of srp-public; training reuses the repository full-prefix BC helpers and DAgger soft-target formula. No engine or source experiment was edited.']
    (HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n')
QUANTILES_TEXT='0, 25, 50, 75, 90, 99, 100 percent'
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--iteration',type=int,required=True);analyze(p.parse_args().iteration)
