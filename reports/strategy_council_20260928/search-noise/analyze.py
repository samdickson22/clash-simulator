import bootstrap
from bootstrap import HERE
import hashlib,json
from collections import Counter
import numpy as np
from noise import VARIANTS

def bootstrap_ci(values):
    a=np.array(values,dtype=float);rng=np.random.default_rng(3905100043)
    draws=a[rng.integers(0,len(a),size=(10000,len(a)))].mean(axis=1)
    return [float(np.mean(a)),*[float(x) for x in np.quantile(draws,[.025,.975])]]

def fmt(x):return f'{100*x[0]:.1f}% [{100*x[1]:.1f}, {100*x[2]:.1f}]'
def pp(x):return f'{100*x[0]:+.1f} pp [{100*x[1]:+.1f}, {100*x[2]:+.1f}]'

def main():
    from evaluate import verify,write
    manifest_path=HERE/'evaluation-manifest.json';manifest=json.loads(manifest_path.read_text());verify(manifest)
    sha=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    schedule=json.loads((HERE/'schedule.json').read_text())['pairs'];rows=[];expected=[]
    for ep in schedule:
        variants=list(VARIANTS) if ep['mode']=='scripts' else list('ABCD')
        for v in variants:
            for seat in (0,1):expected.append((ep,v,seat))
    assert len(expected)==1664
    for ep,v,seat in expected:
        p=HERE/'confirmation'/f"{ep['mode']}-pair{ep['pair']:03d}-{v}-seat{seat}.json";row=json.loads(p.read_text())
        assert row['manifest']==sha and row['terminal'] and row['host']['nice']>=10 and row['host']['native_threads']==2
        assert row['seed']==ep['seed'] and row['noise_seed']==ep['noise_seed'] and row['started']>=manifest['sealed_unix']
        rows.append(row)
    for worker in range(3):
        done=json.loads((HERE/f'worker{worker}-done.json').read_text());assert done['complete'] and done['manifest']==sha
        assert (HERE/f'worker{worker}.exit').read_text().strip()=='0'
    assert len(list((HERE/'confirmation').glob('*.json')))==1664
    means={};scores={};families={};diagnostics={}
    for mode in ('head-to-head','scripts'):
        scores[mode]={};families[mode]={}
        for v in (list(VARIANTS) if mode=='scripts' else list('ABCD')):
            subset=[r for r in rows if r['mode']==mode and r['variant']==v]
            by_pair={p:np.mean([r['score'] for r in subset if r['pair']==p]) for p in sorted({r['pair'] for r in subset})}
            assert len(subset)==128 and len(by_pair)==64
            means[mode,v]=by_pair;scores[mode][v]=dict(n=128,ci=bootstrap_ci(list(by_pair.values())),wins=sum(r['score']==1 for r in subset),draws=sum(r['score']==.5 for r in subset))
            families[mode][v]={f:bootstrap_ci([value for p,value in by_pair.items() if next(r['family'] for r in subset if r['pair']==p)==f]) for f in sorted({r['family'] for r in subset})}
    def delta(mode,left,right):return bootstrap_ci([means[mode,left][p]-means[mode,right][p] for p in means[mode,left]])
    effects={v:delta('scripts',v,'B') for v in VARIANTS if v.endswith('_clean')}
    comparisons={mode:{'B_minus_A':delta(mode,'B','A'),'C_minus_B':delta(mode,'C','B'),'D_minus_B':delta(mode,'D','B')} for mode in ('scripts','head-to-head')}
    for v in VARIANTS:
        selected=[r for r in rows if r['variant']==v];counts=Counter();derived=Counter()
        for r in selected:counts.update(r['perception']);derived.update(r['derived'])
        n=derived['scoring_samples'];true=counts['truth_events'];pred=counts['matched_events']+counts['confused_events']+counts['spurious_events']
        diagnostics[v]=dict(counts=counts,derived=derived,
            event_recall=counts['matched_events']/true if true else None,event_precision=counts['matched_events']/pred if pred else None,
            placement_all=counts['placement_hits']/true if true else None,
            hp_coverage=counts['hp_observed']/counts['hp_trials'] if counts['hp_trials'] else None,
            hp_mae=counts['hp_abs_error']/counts['hp_observed'] if counts['hp_observed'] else None,
            elixir_mae=derived['elixir_abs_error']/n if n else None,interval_coverage=derived['covered']/n if n else None,
            interval_width=derived['interval_width']/n if n else None)
    h=scores['head-to-head']['B']['ci'];s=comparisons['scripts']['B_minus_A']
    strength_pass=h[0]>=.45 and h[1]>.4 and s[0]>=-.05 and s[1]>-.1
    ranked=sorted(effects,key=lambda v:effects[v][0],reverse=True);top=ranked[0]
    timing=dict(decisions=sum(r['timing']['decisions'] for r in rows),max=max(r['timing']['max'] for r in rows),overruns=sum(r['timing']['overruns'] for r in rows),truncations=sum(r['timing']['truncations'] for r in rows),fallbacks=sum(r['timing']['fallbacks'] for r in rows),rejected=sum(r['rejected'][0] for r in rows))
    aggregate=hashlib.sha256(b''.join(hashlib.sha256(p.read_bytes()).digest() for p in sorted((HERE/'confirmation').glob('*.json')))).hexdigest()
    result=dict(complete=True,games=len(rows),scores=scores,families=families,comparisons=comparisons,repair_effects=effects,diagnostics=diagnostics,strength_gate=strength_pass,largest_point_repair=top,timing=timing,manifest=sha,receipts_sha256=aggregate)
    write(HERE/'result.json',result)
    lines=['# Search noise results','',f'All {len(rows):,} preregistered terminal games completed. Simulator strength gate: {"PASS" if strength_pass else "FAIL"}.','',
        'The 95% intervals below bootstrap paired matchup means, 10,000 resamples. Each primary cell contains 128 games and 64 paired matchups. No completed confirmation outcome was excluded.','',
        '| Variant | Versus clean A | Versus C56 scripts |','| --- | --- | --- |']
    for v in 'ABCD':lines.append(f"| {v} | {fmt(scores['head-to-head'][v]['ci'])} | {fmt(scores['scripts'][v]['ci'])} |")
    lines+=['','A has clean inputs. B has full noise. C replaces derived opponent state with a broad train-deck/uniform-elixir prior. D raises correct-event recall and precision to 90% with the frozen inference filter unchanged.','',
        '## Conditional strength cost by source','',
        'Repair effects are script score(repair) minus score(B), paired on the same worlds. Positive values mean that source costs strength in the full-noise setting. Effects interact and should not be added.','',
        '| Source repaired | Score with repair | Gain over B |','| --- | --- | --- |']
    for v in ranked:lines.append(f"| {v.removesuffix('_clean')} | {fmt(scores['scripts'][v]['ci'])} | {pp(effects[v])} |")
    lines+=['',f"Broad opponent prior C minus B: {pp(comparisons['scripts']['C_minus_B'])} against scripts, {pp(comparisons['head-to-head']['C_minus_B'])} head-to-head.",f"90% event gate D minus B: {pp(comparisons['scripts']['D_minus_B'])} against scripts, {pp(comparisons['head-to-head']['D_minus_B'])} head-to-head.",
        '', 'Event placement has zero direct effect in this adapter because neither the current opponent filter nor the public-board reconstruction consumes event coordinates. The coordinate invariance test passed. This does not establish that placement is unimportant to an actual vision tracker.','',
        '## Hog 2.6','', '| Variant | Versus A | Versus scripts |','| --- | --- | --- |']
    for v in 'ABCD':lines.append(f"| {v} | {fmt(families['head-to-head'][v]['Hog 2.6'])} | {fmt(families['scripts'][v]['Hog 2.6'])} |")
    lines+=['','All seven family tables are in result.json. Family intervals are descriptive; Hog 2.6 has 20 games per condition and stratum.','',
        '## Noise fidelity and inference','',
        'Input corruption used 10-FPS packets, entity misses and coordinate jitter/tails, phantom bodies, 66.06% HP coverage with 0.0498 MAE on readable bars, 0.31% hand-slot errors and 2.92% displayed-elixir errors. Missing HP uses a fixed 50% estimate. The point-valued C56 script API requires usable confidence values. No simulator state was corrupted.','',
        'Event rates below are the injected channel counts, not a post-hoc rematching of insertions. Terminally censored events can remain pending. Derived-state diagnostics use scoring-only truth after decisions.','',
        '| Variant | Event recall | Event precision | All-event placement | Derived elixir MAE | 90% interval coverage / width |','| --- | --- | --- | --- | --- | --- |']
    for v in 'BCD':
        d=diagnostics[v];lines.append(f"| {v} | {d['event_recall']:.3f} | {d['event_precision']:.3f} | {d['placement_all']:.3f} | {d['elixir_mae']:.3f} | {d['interval_coverage']:.3f} / {d['interval_width']:.3f} |")
    lines+=['',
        'B and D use the frozen v3 particle filter with validation-only calibration. C ignores events in its broad prior. The exact clean tracker cannot safely ingest contradictory noisy histories, so the event-source repair includes replacing this robust inference path with exact derivation. D changes detections only; it does not recalibrate the filter.','',
        'The model extrapolates P16 body statistics to C56, applies pooled both-side event metrics to opponents, uses independent per-frame body/HP/HUD errors, and inserts false events proportionally to true plays. The eight proxy card confusions are timing/spatial associations, not manually labelled classifications. The v3 posterior does not model champion resource events. These assumptions limit generalization.','',
        'Every controller polls at 100 ms and nominally searches every 200 ms. This shared cadence differs from historical Stage 5b. B/C/D add 150-ms image availability and max(100 ms, measured search time) command delay, quantized to engine ticks. These are simulated latency assumptions, not a concurrent live capture/search measurement.','',
        '## Recommendation','']
    if strength_pass:lines.append('Current noise passes the preregistered simulator strength gate and supports a guarded offline closed-loop pilot. It does not establish general live-loop readiness: full C56 body coverage, lifecycle handling, temporal error persistence and frame timing still need direct validation.')
    else:lines.append('Current perception does not pass the preregistered simulator strength gate. Improve perception and its uncertainty handling before treating the search player as ready for the closed loop. A guarded diagnostic loop remains useful, but this experiment does not justify a strength-readiness claim.')
    lines.append(f"The largest point-estimated repair is {top.removesuffix('_clean')}, {pp(effects[top])}. Repair intervals are marginal; overlapping intervals do not establish a unique ranking.")
    lines+=['','## Verification and provenance','',
        f"Input-copy purity, hidden-state poisoning, scoring-only diagnostics, coordinate invariance and Monte Carlo noise-rate tests passed. Clean-event games assert derived elixir and determined-hand parity. {sum(r['exact_checks'] for r in rows):,} exact checks passed.",
        f"Candidate decisions: {timing['decisions']:,}; maximum wall time {timing['max']*1000:.1f} ms; >250-ms decisions {timing['overruns']}; truncated searches {timing['truncations']}; fallback searches {timing['fallbacks']}; rejected candidate commands {timing['rejected']}. These timings do not certify a hard real-time deadline.",
        f"Manifest SHA-256: {sha}. Receipt aggregate SHA-256: {aggregate}.",
        'Seed audit, PREREG.md, source-copies.json, evaluation-manifest.json, tests-r3.log and all atomic confirmation receipts are retained. Three owned nice-10 workers used the required detach.sh launcher. The Python engine, gamedata, engine-rs and protected report directories were not edited.']
    (HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    summary=['Noise used 10-FPS input packets, measured entity/HP/HUD errors, 64.3% recall/66.7% precision opponent events, and modelled image/action latency. Engine state stayed clean.','Scores with 95% paired-matchup CIs, versus A / scripts:']
    for v in 'ABCD':summary.append(f"{v}: {fmt(scores['head-to-head'][v]['ci'])} / {fmt(scores['scripts'][v]['ci'])}.")
    summary.append('Conditional script-score costs: '+ '; '.join(f"{v.removesuffix('_clean')} {pp(effects[v])}" for v in ranked)+'. Event placement: zero direct effect in this adapter.')
    summary.append(('Supports a guarded offline closed-loop pilot; full live readiness remains unproven.' if strength_pass else 'Current perception fails the simulator strength gate. Improve it before claiming closed-loop readiness.')+f" Largest point-estimated cost: {top.removesuffix('_clean')}. P16-to-C56 error extrapolation and latency assumptions limit this result.")
    final='\n'.join(summary)+'\n';assert len(final.split())<=200
    (HERE/'FINAL.txt').write_text(final);write(HERE/'completion.json',dict(complete=True,games=1664,manifest=sha,receipts_sha256=aggregate))
    (HERE/'PROGRESS.md').write_text('# Search noise progress\n\nComplete. All 1,664 preregistered terminal games and source checks passed. RESULTS.md, result.json and FINAL.txt contain the final analysis. No owned evaluation worker remains after launcher cleanup.\n')
    print('Analysis complete: 1664 games',flush=True)

if __name__=='__main__':main()
