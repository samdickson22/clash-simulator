"""Complete-only, preregistered paired-matchup analysis."""
import bootstrap
from bootstrap import HERE
import hashlib,json,re
from collections import Counter
import numpy as np
from cells import CELLS,CHANNELS
from worker import jobs
from evaluate import verify,write
from diagnose import diagnose

def ci(values):
    a=np.asarray(values,dtype=float);rng=np.random.default_rng(9711100003)
    means=a[rng.integers(0,len(a),size=(10000,len(a)))].mean(axis=1)
    return [float(a.mean()),*map(float,np.quantile(means,[.025,.975]))]

def fmt(values,pp=False):
    a,b,c=[100*v for v in values]
    return f'{a:+.1f} pp [{b:+.1f}, {c:+.1f}]' if pp else f'{a:.1f}% [{b:.1f}, {c:.1f}]'

def main():
    manifest=json.loads((HERE/'evaluation-manifest.json').read_text());verify(manifest)
    sha=hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest()
    execution=json.loads((HERE/'execution.json').read_text())
    for host in ('127x04','127x08'):
        assert (HERE/'collected-status'/f'supervisor-{host}.exit').read_text().strip()=='0'
    for worker in execution['workers']:
        i=worker['index'];done=json.loads((HERE/'collected-status'/f'worker-{i}-done.json').read_text())
        assert done['complete'] and done['manifest']==sha
        assert (HERE/'collected-status'/f'worker-{i}.exit').read_text().strip()=='0'
    expected=jobs(json.loads((HERE/'schedule.json').read_text()));assert len(expected)==3584
    assert len(list((HERE/'confirmation').glob('*.json')))==len(expected)
    # All completeness checks precede any score access.
    rows=[];digest=hashlib.sha256()
    for index,(ep,cell,seat) in enumerate(expected):
        data=(HERE/'confirmation'/f'{index:05d}.json').read_bytes();r=json.loads(data)
        assert r['terminal'] and r['manifest']==sha and r['job']==index
        for key,want in [('seed',ep['seed']),('noise_seed',ep['noise_seed']),('pair',ep['pair']),('seat',seat),('variant',cell),('mode',ep['mode'])]:assert r[key]==want,(index,key)
        assert r['started']>=manifest['sealed_unix'] and r['host']['nice']>=10 and r['host']['native_threads']==1
        assert r['host']['hostname'].split('.')[0]==execution['workers'][index%len(execution['workers'])]['host']
        digest.update(hashlib.sha256(data).digest());rows.append(r)
    scores={};means={};families={};diagnostics={};timing={}
    family_of={ep['pair']:ep['family'] for ep,_,_ in expected}
    for cell in CELLS:
        subset=[r for r in rows if r['variant']==cell];assert len(subset)==256
        pairs={p:float(np.mean([r['score'] for r in subset if r['pair']==p])) for p in range(128)}
        means[cell]=np.array(list(pairs.values()))
        scores[cell]=dict(n=256,ci=ci(means[cell]),wins=sum(r['score']==1 for r in subset),draws=sum(r['score']==.5 for r in subset))
        families[cell]={f:ci([v for p,v in pairs.items() if family_of[p]==f]) for f in sorted(set(family_of.values()))}
        noise=Counter();derived=Counter()
        for r in subset:noise.update(r['perception']);derived.update(r['derived'])
        n=derived['scoring_samples'];truth=noise['truth_events'];pred=noise['matched_events']+noise['confused_events']+noise['spurious_events']
        diagnostics[cell]=dict(noise=noise,derived=derived,event_recall=noise['matched_events']/truth if truth else None,event_precision=noise['matched_events']/pred if pred else None,elixir_mae=derived['elixir_abs_error']/n if n else None,coverage=derived['covered']/n if n else None,interval_width=derived['interval_width']/n if n else None,hand_concentration_rate=derived['hand_concentrated']/n if n else None,concentrated_hand_accuracy=derived['hand_correct']/derived['hand_concentrated'] if derived['hand_concentrated'] else None)
        timing[cell]=dict(decisions=sum(r['timing']['decisions'] for r in subset),median_game_p50_seconds=float(np.median([r['timing']['p50'] for r in subset])),median_game_p99_seconds=float(np.median([r['timing']['p99'] for r in subset])))
    repair={c:ci(means['R-'+c]-means['Full']) for c in CHANNELS}
    add={c:dict(cost_A_minus_Add=ci(means['A']-means['A+'+c]),effect_Add_minus_A=ci(means['A+'+c]-means['A'])) for c in ('derived','board','hp','own','latency')}
    material={c:bool(repair[c][1]>0 or c in add and add[c]['effect_Add_minus_A'][2]<0) for c in CHANNELS}
    summed=sum((means['R-'+c]-means['Full'] for c in CHANNELS));gap=means['A']-means['Full']
    interactions=dict(repair_sum=ci(summed),clean_full_gap=ci(gap),sum_minus_gap=ci(summed-gap))
    family_contrasts={f:dict(repair={c:ci((means['R-'+c]-means['Full'])[[p for p in range(128) if family_of[p]==f]]) for c in CHANNELS},add_cost={c:ci((means['A']-means['A+'+c])[[p for p in range(128) if family_of[p]==f]]) for c in add}) for f in set(family_of.values())}
    compute=dict(game_cpu_hours=sum(r['cpu_seconds'] for r in rows)/3600,game_wall_hours=sum(r['elapsed'] for r in rows)/3600,elapsed_hours=(max(r['started']+r['elapsed'] for r in rows)-min(r['started'] for r in rows))/3600,hosts=dict(Counter(r['host']['hostname'] for r in rows)))
    cpu=lambda paths:sum(sum(float(x) for x in re.findall(r'(?:User time \(seconds\)|System time \(seconds\)):\s*([0-9.]+)',p.read_text())) for p in paths)/3600
    compute['successful_worker_cpu_hours_including_initialization']=cpu((HERE/'collected-status').glob('worker-*.log'))
    compute['supervisors_and_workers_cpu_hours']=cpu((HERE/'collected-status').glob('supervisor-*.log'))
    compute['preflight_cpu_hours']=json.loads((HERE/'preflight.json').read_text())['cpu_hours']
    diagnosis,document=diagnose(rows)
    result=dict(complete=True,games=len(rows),scores=scores,repair=repair,add=add,material=material,interaction=interactions,families=families,family_contrasts=family_contrasts,diagnostics=diagnostics,timing=timing,elt_diagnosis=diagnosis,compute=compute,manifest=sha,receipts_sha256=digest.hexdigest(),failed_taps=sum(r['failed_taps'] for r in rows),rejected=sum(r['rejected'][0] for r in rows))
    write(HERE/'result.json',result);(HERE/'ELT-DIAGNOSIS.md').write_text(document)
    lines=['# S2 results','',f'Complete: {len(rows):,} games. A−Full: {fmt(interactions["clean_full_gap"],True)}.','', '95% percentile intervals use 10,000 paired-matchup bootstrap resamples, both seats retained, RNG 9711100003. No outcome-based exclusions.','', '| Cell | Games | Score (95% CI) |','| --- | ---: | --- |']
    for cell in CELLS:lines.append(f'| {cell} | 256 | {fmt(scores[cell]["ci"])} |')
    lines+=['','## Repair gains (Repair−Full)','','| Channel | Gain (95% CI) | Material by either test |','| --- | --- | --- |']
    for c in sorted(repair,key=lambda c:-repair[c][0]):lines.append(f'| {c} | {fmt(repair[c],True)} | {material[c]} |')
    lines+=['','## Add costs','','| Channel | A−Add (95% CI) | Add−A (95% CI) |','| --- | --- | --- |']
    for c in sorted(add,key=lambda c:-add[c]['cost_A_minus_Add'][0]):lines.append(f'| {c} | {fmt(add[c]["cost_A_minus_Add"],True)} | {fmt(add[c]["effect_Add_minus_A"],True)} |')
    lines+=['', 'Materiality is repair LB>0 or Add−A UB<0; no multiplicity adjustment.','',f'Sum of repair gains: {fmt(interactions["repair_sum"],True)}. A−Full gap: {fmt(interactions["clean_full_gap"],True)}. Sum minus gap: {fmt(interactions["sum_minus_gap"],True)}.','',
            'R-events changes legacy posterior to ELT as explicitly requested, so its contrast mixes tracker and event effects. A+derived uses ELT, not the legacy posterior. Full already has zero injected tap failures, making R-taps a duplicate control. These qualifications also limit the interaction check.','',
            '## Derived-state diagnostics','','| Cell | Elixir MAE | Coverage | Width | Hand concentrated |','| --- | ---: | ---: | ---: | ---: |']
    for c,d in diagnostics.items():lines.append(f'| {c} | {d["elixir_mae"]:.3f} | {d["coverage"]:.3f} | {d["interval_width"]:.3f} | {d["hand_concentration_rate"]:.4f} |')
    lines+=['','## Hog 2.6 (descriptive)','','| Cell | Score (95% CI) |','| --- | --- |']
    for c in CELLS:lines.append(f'| {c} | {fmt(families[c]["Hog 2.6"])} |')
    lines+=['',f'Game CPU: {compute["game_cpu_hours"]:.2f} core-hours; successful workers including initialization: {compute["successful_worker_cpu_hours_including_initialization"]:.2f}; supervisors plus workers: {compute["supervisors_and_workers_cpu_hours"]:.2f}; preflight: {compute["preflight_cpu_hours"]:.2f}. These are overlapping totals, not additive. Confirmation elapsed: {compute["elapsed_hours"]:.2f} hours.', '',f'Manifest: {sha}. Receipt aggregate: {digest.hexdigest()}.', '', 'See ELT-DIAGNOSIS.md for event-aligned evidence; result.json contains all family contrasts, noise counts, decision timings and diagnostics. Raw receipts remain on the fleet.']
    (HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    print('complete-only analysis finished',len(rows),flush=True)
if __name__=='__main__':main()
