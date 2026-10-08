"""Complete-only paired analysis. Never call while any partition is unfinished."""
import bootstrap
from bootstrap import HERE
import hashlib,json,re
from collections import Counter
from pathlib import Path
import numpy as np
from cells import CELLS,H2H
from worker import jobs
from evaluate import verify,write


def ci(values):
    a=np.asarray(values,dtype=float);rng=np.random.default_rng(7611100003)
    means=a[rng.integers(0,len(a),size=(10000,len(a)))].mean(axis=1)
    return [float(a.mean()),*map(float,np.quantile(means,[.025,.975]))]


def fmt(values,pp=False):
    a,b,c=[100*v for v in values]
    return f'{a:+.1f} pp [{b:+.1f}, {c:+.1f}]' if pp else f'{a:.1f}% [{b:.1f}, {c:.1f}]'


def main():
    manifest=json.loads((HERE/'evaluation-manifest.json').read_text());verify(manifest)
    sha=hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest()
    execution=json.loads((HERE/'execution.json').read_text())
    for worker in execution['workers']:
        i=worker['index'];done=json.loads((HERE/'collected-status'/f'worker-{i}-done.json').read_text())
        assert done['complete'] and done['manifest']==sha
        assert (HERE/'collected-status'/f'worker-{i}.exit').read_text().strip()=='0'
    expected=jobs(json.loads((HERE/'schedule.json').read_text()))
    assert len(expected)==4992
    rows=[];digest=hashlib.sha256()
    for index,(ep,cell,seat) in enumerate(expected):
        path=HERE/'confirmation'/f'{index:05d}.json';data=path.read_bytes();r=json.loads(data)
        assert r['terminal'] and r['manifest']==sha and r['job']==index
        for key,want in [('seed',ep['seed']),('noise_seed',ep['noise_seed']),('pair',ep['pair']),('seat',seat),('variant',cell),('mode',ep['mode'])]:assert r[key]==want,(index,key)
        assert r['started']>=manifest['sealed_unix'] and r['host']['nice']>=10 and r['host']['native_threads']==1
        assigned=execution['workers'][index%len(execution['workers'])]
        assert r['host']['hostname'].split('.')[0]==assigned['host']
        digest.update(hashlib.sha256(data).digest());rows.append(r)
    assert len(list((HERE/'confirmation').glob('*.json')))==len(expected)
    scores={};means={};families={};diagnostics={}
    for mode in ('scripts','head-to-head'):
        scores[mode]={};families[mode]={}
        for cell in (CELLS if mode=='scripts' else H2H):
            subset=[r for r in rows if r['mode']==mode and r['variant']==cell]
            pairs={p:float(np.mean([r['score'] for r in subset if r['pair']==p])) for p in sorted({r['pair'] for r in subset})}
            assert len(subset)==(256 if mode=='scripts' else 128)
            assert len(pairs)*2==len(subset)
            means[mode,cell]=pairs
            scores[mode][cell]={'n':len(subset),'ci':ci(list(pairs.values())),'wins':sum(r['score']==1 for r in subset),'draws':sum(r['score']==.5 for r in subset)}
            families[mode][cell]={f:ci([value for p,value in pairs.items() if next(r['family'] for r in subset if r['pair']==p)==f]) for f in sorted({r['family'] for r in subset})}
    def delta(a,b):return ci([means['scripts',a][p]-means['scripts',b][p] for p in means['scripts',a]])
    primary=delta('E4-N64','B-N64')
    gates={q:delta('E4-'+q,'A') for q in ('N90','N97')}
    gate=next((q for q,v in gates.items() if v[0]>=-.05 and v[1]>-.10),None)
    for cell in CELLS:
        subset=[r for r in rows if r['variant']==cell];noise=Counter();derived=Counter()
        for r in subset:noise.update(r['perception']);derived.update(r['derived'])
        n=derived['scoring_samples'];truth=noise['truth_events'];pred=noise['matched_events']+noise['confused_events']+noise['spurious_events']
        diagnostics[cell]=dict(noise=noise,derived=derived,event_recall=noise['matched_events']/truth if truth else None,event_precision=noise['matched_events']/pred if pred else None,elixir_mae=derived['elixir_abs_error']/n if n else None,coverage=derived['covered']/n if n else None,interval_width=derived['interval_width']/n if n else None)
    compute=dict(game_cpu_hours=sum(r['cpu_seconds'] for r in rows)/3600,game_wall_hours=sum(r['elapsed'] for r in rows)/3600,elapsed_hours=(max(r['started']+r['elapsed'] for r in rows)-min(r['started'] for r in rows))/3600,hosts=dict(Counter(r['host']['hostname'] for r in rows)))
    total_cpu=0.
    for p in (HERE/'collected-status').glob('worker-*.log'):
        total_cpu+=sum(float(x) for x in re.findall(r'(?:User time \(seconds\)|System time \(seconds\)):\s*([0-9.]+)',p.read_text()))
    compute['successful_worker_cpu_hours_including_initialization']=total_cpu/3600
    compute['preconfirmation_linux_cpu_hours']=json.loads((HERE/'preflight.json').read_text())['preconfirmation_linux_cpu_hours']
    comparisons={cell:delta(cell,'B-N64' if cell.endswith('N64') else 'E4-N90') for cell in CELLS if cell!='A'}
    result=dict(complete=True,games=len(rows),primary=dict(ci=primary,passed=primary[1]>0),event_gate_comparisons=gates,recommended_event_gate=gate or '95/95 provisional; further decision work required',scores=scores,families=families,diagnostics=diagnostics,comparisons=comparisons,compute=compute,manifest=sha,receipts_sha256=digest.hexdigest(),failures=sum(r['failed_taps'] for r in rows),rejected=sum(r['rejected'][0] for r in rows))
    write(HERE/'result.json',result)
    lines=['# S1 results','',f'All {len(rows):,} preregistered games completed. Primary E4 minus B at N64: {fmt(primary,True)}. Primary test: {"PASS" if primary[1]>0 else "FAIL"}.','',f'Recommended event gate: {result["recommended_event_gate"]}.','', '95% intervals use 10,000 paired-matchup bootstrap resamples, retaining both seats. No completed game was excluded.','', '| Script cell | Games | Score and 95% CI |','| --- | ---: | --- |']
    for cell,s in scores['scripts'].items():lines.append(f'| {cell} | {s["n"]} | {fmt(s["ci"])} |')
    lines+=['','| Against clean A | Games | Score and 95% CI |','| --- | ---: | --- |']
    for cell,s in scores['head-to-head'].items():lines.append(f'| {cell} | {s["n"]} | {fmt(s["ci"])} |')
    lines+=['',f'N90 E4 minus clean: {fmt(gates["N90"],True)}. N97: {fmt(gates["N97"],True)}.','', '| Hog 2.6 script cell | Score and descriptive 95% CI |','| --- | --- |']
    for cell in CELLS:lines.append(f'| {cell} | {fmt(families["scripts"][cell]["Hog 2.6"])} |')
    lines+=['',f'Game compute: {compute["game_cpu_hours"]:.2f} core-hours. Confirmation elapsed: {compute["elapsed_hours"]:.2f} hours. Successful worker CPU including initialization: {compute["successful_worker_cpu_hours_including_initialization"]:.2f} core-hours. Preconfirmation Linux tests and pilots: {compute["preconfirmation_linux_cpu_hours"]:.2f} core-hours. Node-supervisor warmup and unmetered Mac calibration are additional.','',
        'The shared native build retains the documented Electro Spirit and Fisherman defects. This study compares beliefs under that build; it does not certify engine parity or live-client strength.',
        'The fixed total rollout budget reduces candidate coverage as root count rises. ELT uses the legacy point-identity event adapter, a fixed age estimate and validation-calibrated existence probabilities. Own action verification is an idealized next-tick public HUD cue. See PREREG.md for these predeclared assumptions and the reused target-latency cell.',
        '',f'Manifest: {sha}. Receipt aggregate: {digest.hexdigest()}.',
        'Detailed family, noise, derived-state and compute data are in result.json. Raw receipts remain on the fleet hub.']
    (HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    (HERE/'PROGRESS.md').open('a').write(f'\nCompleted all {len(rows)} games; complete-only analysis wrote RESULTS.md and result.json.\n')
    print('complete',len(rows))

if __name__=='__main__':main()
